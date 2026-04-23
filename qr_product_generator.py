#!/usr/bin/env python3
"""
QR Product Generator

A reusable QR code generator for product links.
- GUI mode (default): paste one or multiple links, preview, save PNG files
- CLI mode: generate one QR or a batch from CSV/TXT

Requires: qrcode, Pillow (already available in many Python environments)
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import qrcode
from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H
from PIL import Image, ImageTk

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter.scrolledtext import ScrolledText
except Exception:  # pragma: no cover
    tk = None
    filedialog = None
    messagebox = None
    ttk = None
    ScrolledText = None


ERROR_LEVELS = {
    "L": ERROR_CORRECT_L,
    "M": ERROR_CORRECT_M,
    "Q": ERROR_CORRECT_Q,
    "H": ERROR_CORRECT_H,
}


@dataclass
class QRJob:
    name: str
    url: str


def is_valid_url(value: str) -> bool:
    value = value.strip()
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def sanitize_filename(name: str, fallback: str = "qr_code") -> str:
    name = (name or "").strip()
    if not name:
        name = fallback
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"_+", "_", name).strip("._")
    return name[:120] or fallback


def build_qr_image(
    data: str,
    *,
    box_size: int = 10,
    border: int = 4,
    error_level: str = "M",
    fill_color: str = "black",
    back_color: str = "white",
) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_LEVELS[error_level],
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fill_color, back_color=back_color)
    if hasattr(img, "get_image"):
        img = img.get_image()
    return img.convert("RGBA")


def save_qr_png(job: QRJob, output_dir: Path, *, box_size: int, border: int, error_level: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = sanitize_filename(job.name or "qr_code") + ".png"
    out_path = output_dir / filename
    image = build_qr_image(job.url, box_size=box_size, border=border, error_level=error_level)
    image.save(out_path, format="PNG")
    return out_path


def parse_batch_lines(text: str) -> List[QRJob]:
    jobs: List[QRJob] = []
    for idx, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        if "," in line:
            left, right = line.split(",", 1)
            name = left.strip()
            url = right.strip()
        else:
            name = f"product_{idx}"
            url = line

        if not is_valid_url(url):
            raise ValueError(f"خط {idx}: لینک نامعتبر است -> {url}")

        jobs.append(QRJob(name=sanitize_filename(name, fallback=f"product_{idx}"), url=url))

    if not jobs:
        raise ValueError("هیچ لینک معتبری وارد نشده است.")
    return jobs


def parse_batch_file(path: Path) -> List[QRJob]:
    suffix = path.suffix.lower()
    jobs: List[QRJob] = []

    if suffix in {".csv", ".tsv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            headers = {h.lower().strip(): h for h in (reader.fieldnames or [])}
            name_key = headers.get("name") or headers.get("title") or headers.get("product")
            url_key = headers.get("url") or headers.get("link") or headers.get("href")
            if not url_key:
                raise ValueError("فایل CSV/TSV باید ستون url یا link داشته باشد.")
            for i, row in enumerate(reader, start=1):
                url = (row.get(url_key) or "").strip()
                name = (row.get(name_key) or f"product_{i}").strip() if name_key else f"product_{i}"
                if not is_valid_url(url):
                    raise ValueError(f"ردیف {i}: لینک نامعتبر است -> {url}")
                jobs.append(QRJob(name=sanitize_filename(name, fallback=f"product_{i}"), url=url))
    else:
        jobs = parse_batch_lines(path.read_text(encoding="utf-8-sig"))

    if not jobs:
        raise ValueError("هیچ موردی برای ساخت QR پیدا نشد.")
    return jobs


def zip_pngs(files: Iterable[Path], zip_path: Path) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file in files:
            zf.write(file, arcname=file.name)
    return zip_path


class QRApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("QR Product Generator")
        self.root.geometry("980x700")
        self.root.minsize(900, 620)

        self.preview_photo: Optional[ImageTk.PhotoImage] = None

        self.single_url_var = tk.StringVar()
        self.single_name_var = tk.StringVar(value="product_qr")
        self.box_size_var = tk.IntVar(value=10)
        self.border_var = tk.IntVar(value=4)
        self.error_var = tk.StringVar(value="M")
        self.output_dir_var = tk.StringVar(value=str(Path.cwd() / "qr_output"))
        self.batch_file_var = tk.StringVar()
        self.status_var = tk.StringVar(value="آماده")

        self._build_ui()

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 8}

        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=12, pady=10)

        options = ttk.LabelFrame(top, text="تنظیمات خروجی PNG")
        options.pack(fill="x")

        ttk.Label(options, text="کیفیت / box size").grid(row=0, column=0, sticky="w", **pad)
        ttk.Spinbox(options, from_=4, to=40, textvariable=self.box_size_var, width=8).grid(row=0, column=1, sticky="w", **pad)

        ttk.Label(options, text="حاشیه / border").grid(row=0, column=2, sticky="w", **pad)
        ttk.Spinbox(options, from_=1, to=20, textvariable=self.border_var, width=8).grid(row=0, column=3, sticky="w", **pad)

        ttk.Label(options, text="Error correction").grid(row=0, column=4, sticky="w", **pad)
        ttk.Combobox(options, values=["L", "M", "Q", "H"], textvariable=self.error_var, width=6, state="readonly").grid(row=0, column=5, sticky="w", **pad)

        ttk.Label(options, text="پوشه خروجی").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(options, textvariable=self.output_dir_var).grid(row=1, column=1, columnspan=4, sticky="ew", **pad)
        ttk.Button(options, text="انتخاب پوشه", command=self.choose_output_dir).grid(row=1, column=5, sticky="ew", **pad)

        options.columnconfigure(1, weight=1)
        options.columnconfigure(2, weight=0)
        options.columnconfigure(3, weight=0)
        options.columnconfigure(4, weight=0)

        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left = ttk.Notebook(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        single_tab = ttk.Frame(left)
        batch_tab = ttk.Frame(left)
        left.add(single_tab, text="تک لینک")
        left.add(batch_tab, text="چند لینک")

        self._build_single_tab(single_tab)
        self._build_batch_tab(batch_tab)

        preview_frame = ttk.LabelFrame(body, text="پیش‌نمایش")
        preview_frame.grid(row=0, column=1, sticky="nsew")
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)

        self.preview_label = ttk.Label(preview_frame, text="برای دیدن پیش‌نمایش، یک لینک وارد کنید.", anchor="center")
        self.preview_label.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

        status = ttk.Label(self.root, textvariable=self.status_var, anchor="w")
        status.pack(fill="x", padx=12, pady=(0, 8))

    def _build_single_tab(self, parent: ttk.Frame) -> None:
        pad = {"padx": 10, "pady": 8}
        frame = ttk.LabelFrame(parent, text="ساخت PNG برای یک محصول")
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="نام فایل").grid(row=0, column=0, sticky="w", **pad)
        name_row = ttk.Frame(frame)
        name_row.grid(row=0, column=1, sticky="ew", **pad)
        name_row.columnconfigure(0, weight=1)
        name_entry = ttk.Entry(name_row, textvariable=self.single_name_var)
        name_entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(name_row, text="چسباندن", command=lambda: self.paste_to_stringvar(self.single_name_var)).grid(row=0, column=1, padx=(8, 0))
        name_entry.bind("<Control-v>", lambda _e: (self.paste_to_stringvar(self.single_name_var), "break")[1])
        name_entry.bind("<Shift-Insert>", lambda _e: (self.paste_to_stringvar(self.single_name_var), "break")[1])

        ttk.Label(frame, text="لینک محصول").grid(row=1, column=0, sticky="nw", **pad)
        url_row = ttk.Frame(frame)
        url_row.grid(row=1, column=1, sticky="ew", **pad)
        url_row.columnconfigure(0, weight=1)
        url_entry = ttk.Entry(url_row, textvariable=self.single_url_var)
        url_entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(url_row, text="چسباندن لینک", command=lambda: self.paste_to_stringvar(self.single_url_var, preview_after=True)).grid(row=0, column=1, padx=(8, 0))
        url_entry.bind("<KeyRelease>", lambda _e: self.safe_preview())
        url_entry.bind("<Control-v>", lambda _e: (self.paste_to_stringvar(self.single_url_var, preview_after=True), "break")[1])
        url_entry.bind("<Shift-Insert>", lambda _e: (self.paste_to_stringvar(self.single_url_var, preview_after=True), "break")[1])

        actions = ttk.Frame(frame)
        actions.grid(row=2, column=0, columnspan=2, sticky="w", **pad)
        ttk.Button(actions, text="پیش‌نمایش", command=self.preview_single).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="ذخیره PNG", command=self.save_single).pack(side="left")

        help_text = (
            "لینک باید با http:// یا https:// شروع شود.\n"
            "اگر Ctrl+V کار نکرد، از دکمه‌های چسباندن استفاده کنید.\n"
            "نام فایل اختیاری است؛ اگر کاراکتر نامعتبر داشته باشد، خودکار اصلاح می‌شود."
        )
        ttk.Label(frame, text=help_text, justify="left").grid(row=3, column=0, columnspan=2, sticky="w", **pad)

    def _build_batch_tab(self, parent: ttk.Frame) -> None:
        pad = {"padx": 10, "pady": 8}

        frame = ttk.LabelFrame(parent, text="ساخت گروهی PNG")
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(2, weight=1)

        ttk.Label(frame, text="فایل CSV/TXT").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.batch_file_var).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(frame, text="انتخاب فایل", command=self.choose_batch_file).grid(row=0, column=2, sticky="ew", **pad)

        batch_header = ttk.Frame(frame)
        batch_header.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=(8, 0))
        batch_header.columnconfigure(0, weight=1)
        ttk.Label(batch_header, text="یا لیست را اینجا بچسبانید").grid(row=0, column=0, sticky="w")
        ttk.Button(batch_header, text="چسباندن از کلیپ‌بورد", command=lambda: self.paste_to_text(self.batch_text)).grid(row=0, column=1, sticky="e")

        self.batch_text = ScrolledText(frame, wrap="word", height=16)
        self.batch_text.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=10, pady=(8, 10))
        self.batch_text.bind("<Control-v>", lambda _e: (self.paste_to_text(self.batch_text), "break")[1])
        self.batch_text.bind("<Shift-Insert>", lambda _e: (self.paste_to_text(self.batch_text), "break")[1])
        self.batch_text.insert(
            "1.0",
            "نمونه:\n"
            "product-1,https://example.com/products/1\n"
            "product-2,https://example.com/products/2\n\n"
            "یا فقط لینک:\n"
            "https://example.com/products/3\n",
        )

        actions = ttk.Frame(frame)
        actions.grid(row=3, column=0, columnspan=3, sticky="w", **pad)
        ttk.Button(actions, text="ساخت همه PNGها", command=self.generate_batch).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="ساخت PNGها + ZIP", command=self.generate_batch_zip).pack(side="left")

        help_text = (
            "فرمت پیشنهادی CSV: ستون‌های name و url\n"
            "فرمت متن ساده: هر خط به صورت name,url یا فقط url"
        )
        ttk.Label(frame, text=help_text, justify="left").grid(row=4, column=0, columnspan=3, sticky="w", **pad)


    def paste_to_stringvar(self, var: tk.StringVar, *, append: bool = False, preview_after: bool = False) -> None:
        try:
            value = self.root.clipboard_get()
        except Exception:
            self.status_var.set("کلیپ‌بورد خالی است یا قابل خواندن نیست.")
            return
        if not append:
            var.set(value.strip())
        else:
            current = var.get().strip()
            var.set((current + value).strip())
        if preview_after:
            self.safe_preview()
        self.status_var.set("متن از کلیپ‌بورد چسبانده شد.")

    def paste_to_text(self, widget: tk.Text, *, replace: bool = False) -> None:
        try:
            value = self.root.clipboard_get()
        except Exception:
            self.status_var.set("کلیپ‌بورد خالی است یا قابل خواندن نیست.")
            return
        if replace:
            widget.delete("1.0", "end")
        widget.insert(widget.index("insert"), value)
        self.status_var.set("متن از کلیپ‌بورد چسبانده شد.")

    def choose_output_dir(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.output_dir_var.get() or str(Path.cwd()))
        if folder:
            self.output_dir_var.set(folder)

    def choose_batch_file(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("TSV files", "*.tsv"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        if path:
            self.batch_file_var.set(path)

    def current_options(self) -> Tuple[int, int, str]:
        box_size = max(4, int(self.box_size_var.get()))
        border = max(1, int(self.border_var.get()))
        error_level = self.error_var.get().strip().upper() or "M"
        if error_level not in ERROR_LEVELS:
            error_level = "M"
        return box_size, border, error_level

    def safe_preview(self) -> None:
        url = self.single_url_var.get().strip()
        if is_valid_url(url):
            try:
                self.preview_single()
            except Exception:
                pass

    def preview_single(self) -> None:
        url = self.single_url_var.get().strip()
        if not is_valid_url(url):
            self.status_var.set("لینک تک‌محصول معتبر نیست.")
            return

        box_size, border, error_level = self.current_options()
        image = build_qr_image(url, box_size=box_size, border=border, error_level=error_level)

        preview = image.copy()
        preview.thumbnail((420, 420))
        self.preview_photo = ImageTk.PhotoImage(preview)
        self.preview_label.configure(image=self.preview_photo, text="")
        self.status_var.set("پیش‌نمایش به‌روزرسانی شد.")

    def save_single(self) -> None:
        url = self.single_url_var.get().strip()
        name = self.single_name_var.get().strip() or "product_qr"
        if not is_valid_url(url):
            messagebox.showerror("خطا", "لینک محصول معتبر نیست.")
            return

        box_size, border, error_level = self.current_options()
        out_dir = Path(self.output_dir_var.get()).expanduser()
        path = save_qr_png(QRJob(name=name, url=url), out_dir, box_size=box_size, border=border, error_level=error_level)
        self.status_var.set(f"فایل ذخیره شد: {path}")
        messagebox.showinfo("انجام شد", f"PNG ذخیره شد:\n{path}")

    def _collect_batch_jobs(self) -> List[QRJob]:
        file_path = self.batch_file_var.get().strip()
        pasted = self.batch_text.get("1.0", "end").strip()

        if file_path:
            return parse_batch_file(Path(file_path))

        return parse_batch_lines(pasted)

    def generate_batch(self) -> None:
        try:
            jobs = self._collect_batch_jobs()
            box_size, border, error_level = self.current_options()
            out_dir = Path(self.output_dir_var.get()).expanduser()
            files = [save_qr_png(job, out_dir, box_size=box_size, border=border, error_level=error_level) for job in jobs]
            self.status_var.set(f"{len(files)} فایل PNG ساخته شد.")
            messagebox.showinfo("انجام شد", f"{len(files)} فایل PNG ساخته شد در:\n{out_dir}")
        except Exception as e:
            messagebox.showerror("خطا", str(e))
            self.status_var.set(f"خطا: {e}")

    def generate_batch_zip(self) -> None:
        try:
            jobs = self._collect_batch_jobs()
            box_size, border, error_level = self.current_options()
            out_dir = Path(self.output_dir_var.get()).expanduser()
            files = [save_qr_png(job, out_dir, box_size=box_size, border=border, error_level=error_level) for job in jobs]
            zip_path = zip_pngs(files, out_dir / "qr_codes_bundle.zip")
            self.status_var.set(f"{len(files)} فایل PNG ساخته شد و ZIP ایجاد شد.")
            messagebox.showinfo("انجام شد", f"ZIP ساخته شد:\n{zip_path}")
        except Exception as e:
            messagebox.showerror("خطا", str(e))
            self.status_var.set(f"خطا: {e}")


def run_cli(args: argparse.Namespace) -> int:
    box_size = max(4, args.box_size)
    border = max(1, args.border)
    error_level = args.error_correction.upper()
    if error_level not in ERROR_LEVELS:
        raise SystemExit("error_correction must be one of: L, M, Q, H")

    output_dir = Path(args.output_dir).expanduser()

    if args.url:
        if not is_valid_url(args.url):
            raise SystemExit("URL is not valid. It must start with http:// or https://")
        name = args.name or "product_qr"
        path = save_qr_png(QRJob(name=name, url=args.url), output_dir, box_size=box_size, border=border, error_level=error_level)
        print(path)
        return 0

    if args.batch_file:
        jobs = parse_batch_file(Path(args.batch_file).expanduser())
        files = [save_qr_png(job, output_dir, box_size=box_size, border=border, error_level=error_level) for job in jobs]
        if args.zip:
            zip_path = zip_pngs(files, output_dir / "qr_codes_bundle.zip")
            print(zip_path)
        else:
            for file in files:
                print(file)
        return 0

    raise SystemExit("Use --url for one QR or --batch-file for batch mode. Without arguments the GUI is launched.")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate product QR codes as PNG files")
    parser.add_argument("--url", help="Single product URL")
    parser.add_argument("--name", help="Output filename without extension")
    parser.add_argument("--batch-file", help="CSV/TXT input file for batch generation")
    parser.add_argument("--output-dir", default="qr_output", help="Output folder for PNG files")
    parser.add_argument("--box-size", type=int, default=10, help="QR box size (default: 10)")
    parser.add_argument("--border", type=int, default=4, help="QR border (default: 4)")
    parser.add_argument("--error-correction", default="M", choices=["L", "M", "Q", "H"], help="Error correction level")
    parser.add_argument("--zip", action="store_true", help="Create ZIP bundle in batch mode")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    if len(sys.argv) > 1:
        return run_cli(args)

    if tk is None:
        parser.print_help()
        return 1

    root = tk.Tk()
    app = QRApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
