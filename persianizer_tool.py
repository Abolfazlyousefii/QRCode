#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
فارسی‌ساز ساده برای فایل‌های سورس و متنی

کاربرد:
- فارسی‌کردن متن‌های رابط کاربری داخل فایل‌های سورس
- پشتیبانی از فایل یا پوشه
- ساخت نسخه پشتیبان
- تعریف جایگزینی‌های سفارشی
- استخراج متن‌های قابل ترجمه از فایل‌های پایتون

نکته:
این ابزار برای فایل‌های متنی/سورس مناسب است و برای EXE یا برنامه‌های کامپایل‌شده
مستقیماً کاربرد ندارد.
"""

from __future__ import annotations

import csv
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText


COMMON_REPLACEMENTS: list[tuple[str, str]] = [
    ("QR Product Generator", "سازنده کیوآرکد محصولات"),
    ("Preview", "پیش‌نمایش"),
    ("Save PNG", "ذخیره تصویر"),
    ("Output folder", "پوشه خروجی"),
    ("Choose folder", "انتخاب پوشه"),
    ("Choose file", "انتخاب فایل"),
    ("Product URL", "لینک محصول"),
    ("File name", "نام فایل"),
    ("Error correction", "میزان تصحیح خطا"),
    ("Font size", "اندازه فونت"),
    ("Font color", "رنگ متن"),
    ("Text direction", "جهت نوشتار"),
    ("Text font", "فونت متن"),
    ("Logo", "لوگو"),
    ("Choose logo", "انتخاب لوگو"),
    ("Clear logo", "پاک کردن لوگو"),
    ("Border", "کادر"),
    ("Border width", "ضخامت کادر"),
    ("Show caption", "نمایش متن"),
    ("Single link", "تک‌لینک"),
    ("Batch links", "چند‌لینک"),
    ("Paste", "چسباندن"),
    ("Paste link", "چسباندن لینک"),
    ("Done", "انجام شد"),
    ("Error", "خطا"),
    ("Ready", "آماده"),
    ("Select font", "انتخاب فونت"),
    ("Default font", "فونت پیش‌فرض"),
    ("Generate", "ساخت"),
    ("Create", "ساخت"),
    ("Settings", "تنظیمات"),
    ("Image output settings", "تنظیمات خروجی تصویر"),
    ("Choose color", "انتخاب رنگ"),
    ("Light", "روشن"),
    ("Dark", "تیره"),
    ("Open", "باز کردن"),
    ("Close", "بستن"),
    ("Apply", "اعمال"),
    ("Cancel", "لغو"),
    ("Help", "راهنما"),
    ("Search", "جستجو"),
    ("Name", "نام"),
    ("Title", "عنوان"),
    ("Description", "توضیحات"),
    ("Status", "وضعیت"),
    ("Save", "ذخیره"),
    ("Delete", "حذف"),
    ("Edit", "ویرایش"),
    ("Language", "زبان"),
    ("English", "انگلیسی"),
    ("Persian", "فارسی"),
    ("Right to left", "راست‌به‌چپ"),
    ("Left to right", "چپ‌به‌راست"),
    ("Auto", "خودکار"),
    ("Products", "محصولات"),
    ("Loading", "در حال بارگذاری"),
    ("Select", "انتخاب"),
    ("Folder", "پوشه"),
    ("File", "فایل"),
]

DEFAULT_EXTENSIONS = ".py,.txt,.json,.js,.ts,.jsx,.tsx,.html,.css,.md,.ini,.cfg,.yaml,.yml"


@dataclass
class ApplyResult:
    path: Path
    changed: bool
    replacements: int
    error: str = ""


def parse_custom_replacements(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        if "=>" not in raw:
            continue
        left, right = raw.split("=>", 1)
        left = left.strip()
        right = right.strip()
        if left:
            pairs.append((left, right))
    return pairs


def build_replacements(custom_text: str) -> list[tuple[str, str]]:
    result = list(COMMON_REPLACEMENTS)
    result.extend(parse_custom_replacements(custom_text))
    # طولانی‌ترها اول جایگزین شوند
    result.sort(key=lambda x: len(x[0]), reverse=True)
    return result


def parse_extensions(ext_text: str) -> set[str]:
    items = [x.strip().lower() for x in ext_text.split(",") if x.strip()]
    out: set[str] = set()
    for item in items:
        if not item.startswith("."):
            item = "." + item
        out.add(item)
    return out


def iter_target_files(target: Path, recursive: bool, extensions: set[str]) -> Iterable[Path]:
    if target.is_file():
        if not extensions or target.suffix.lower() in extensions:
            yield target
        return

    walker = target.rglob("*") if recursive else target.glob("*")
    for p in walker:
        if p.is_file() and (not extensions or p.suffix.lower() in extensions):
            yield p


def apply_rtl_layout_fixes(text: str) -> tuple[str, int]:
    replacements = 0
    rules = [
        ('justify="left"', 'justify="right"'),
        ("justify='left'", "justify='right'"),
        ('anchor="w"', 'anchor="e"'),
        ("anchor='w'", "anchor='e'"),
        # موارد خیلی رایج در برچسب‌ها و گرید
        ('sticky="w"', 'sticky="e"'),
        ("sticky='w'", "sticky='e'"),
        ('side="left"', 'side="right"'),
        ("side='left'", "side='right'"),
    ]
    for old, new in rules:
        count = text.count(old)
        if count:
            text = text.replace(old, new)
            replacements += count
    return text, replacements


def safe_read_text(path: Path) -> str:
    encodings = ["utf-8", "utf-8-sig", "cp1256", "windows-1252"]
    last_error = None
    for enc in encodings:
        try:
            return path.read_text(encoding=enc)
        except Exception as exc:
            last_error = exc
    raise last_error or RuntimeError(f"خواندن فایل ناموفق بود: {path}")


def safe_write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def process_file(
    path: Path,
    replacements: list[tuple[str, str]],
    create_backup: bool,
    apply_rtl_fixes: bool,
) -> ApplyResult:
    try:
        original = safe_read_text(path)
        updated = original
        total = 0

        for old, new in replacements:
            count = updated.count(old)
            if count:
                updated = updated.replace(old, new)
                total += count

        if apply_rtl_fixes:
            updated, rtl_count = apply_rtl_layout_fixes(updated)
            total += rtl_count

        changed = updated != original
        if changed:
            if create_backup:
                backup_path = path.with_suffix(path.suffix + ".bak")
                shutil.copy2(path, backup_path)
            safe_write_text(path, updated)

        return ApplyResult(path=path, changed=changed, replacements=total)
    except Exception as exc:
        return ApplyResult(path=path, changed=False, replacements=0, error=str(exc))


EXTRACT_PATTERNS = [
    re.compile(r'text\s*=\s*["\']([^"\']+)["\']'),
    re.compile(r'title\(\s*["\']([^"\']+)["\']\s*\)'),
    re.compile(r'help\s*=\s*["\']([^"\']+)["\']'),
    re.compile(r'messagebox\.\w+\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']'),
]


def extract_strings_from_python(path: Path) -> list[str]:
    text = safe_read_text(path)
    found: list[str] = []
    for pattern in EXTRACT_PATTERNS:
        for match in pattern.finditer(text):
            for group in match.groups():
                if group and group.strip():
                    found.append(group.strip())
    # حذف تکراری‌ها با حفظ ترتیب
    unique = list(dict.fromkeys(found))
    return unique


class PersianizerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("فارسی‌ساز ساده")
        self.root.geometry("1100x760")
        self.root.minsize(960, 680)

        self.target_var = tk.StringVar()
        self.extensions_var = tk.StringVar(value=DEFAULT_EXTENSIONS)
        self.backup_var = tk.BooleanVar(value=True)
        self.recursive_var = tk.BooleanVar(value=True)
        self.rtl_fixes_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="آماده")

        self._build_ui()

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=12, pady=12)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        top = ttk.LabelFrame(main, text="انتخاب فایل یا پوشه")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="مسیر هدف").grid(row=0, column=0, sticky="e", padx=8, pady=8)
        ttk.Entry(top, textvariable=self.target_var, justify="right").grid(row=0, column=1, sticky="ew", padx=8, pady=8)
        ttk.Button(top, text="انتخاب فایل", command=self.choose_file).grid(row=0, column=2, padx=8, pady=8)
        ttk.Button(top, text="انتخاب پوشه", command=self.choose_folder).grid(row=0, column=3, padx=8, pady=8)

        ttk.Label(top, text="پسوندها").grid(row=1, column=0, sticky="e", padx=8, pady=8)
        ttk.Entry(top, textvariable=self.extensions_var, justify="right").grid(row=1, column=1, sticky="ew", padx=8, pady=8)
        ttk.Checkbutton(top, text="ساخت نسخه پشتیبان", variable=self.backup_var).grid(row=1, column=2, sticky="w", padx=8, pady=8)
        ttk.Checkbutton(top, text="جست‌وجوی بازگشتی در پوشه", variable=self.recursive_var).grid(row=1, column=3, sticky="w", padx=8, pady=8)
        ttk.Checkbutton(top, text="اصلاح چیدمان راست‌به‌چپ برای Tkinter", variable=self.rtl_fixes_var).grid(row=2, column=1, sticky="w", padx=8, pady=(0, 8))

        tabs = ttk.Notebook(main)
        tabs.grid(row=1, column=0, sticky="nsew")

        self.auto_tab = ttk.Frame(tabs)
        self.extract_tab = ttk.Frame(tabs)
        tabs.add(self.auto_tab, text="فارسی‌سازی خودکار")
        tabs.add(self.extract_tab, text="استخراج متن‌ها")

        self._build_auto_tab()
        self._build_extract_tab()

        status = ttk.Label(self.root, textvariable=self.status_var, anchor="w")
        status.pack(fill="x", padx=12, pady=(0, 8))

    def _build_auto_tab(self) -> None:
        self.auto_tab.columnconfigure(0, weight=1)
        self.auto_tab.rowconfigure(1, weight=1)

        info = ttk.LabelFrame(self.auto_tab, text="راهنمای جایگزینی سفارشی")
        info.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        info.columnconfigure(0, weight=1)

        help_text = (
            "هر خط را به این شکل بنویس:\n"
            "متن انگلیسی => متن فارسی\n\n"
            "مثال:\n"
            "Settings => تنظیمات\n"
            "Save PNG => ذخیره تصویر\n"
            "Preview => پیش‌نمایش"
        )
        ttk.Label(info, text=help_text, justify="right").grid(row=0, column=0, sticky="w", padx=10, pady=10)

        editor = ttk.LabelFrame(self.auto_tab, text="جایگزینی‌های سفارشی")
        editor.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        editor.columnconfigure(0, weight=1)
        editor.rowconfigure(0, weight=1)

        self.custom_text = ScrolledText(editor, wrap="word", height=14)
        self.custom_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.custom_text.insert(
            "1.0",
            "# این بخش اختیاری است\n"
            "Preview => پیش‌نمایش\n"
            "Save => ذخیره\n"
            "Close => بستن\n"
        )

        actions = ttk.Frame(self.auto_tab)
        actions.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        ttk.Button(actions, text="اجرای فارسی‌سازی", command=self.run_apply).pack(side="right")
        ttk.Button(actions, text="نمایش جایگزینی‌های پیش‌فرض", command=self.show_defaults).pack(side="right", padx=(0, 8))

        result_box = ttk.LabelFrame(self.auto_tab, text="گزارش اجرا")
        result_box.grid(row=3, column=0, sticky="nsew", padx=8, pady=(0, 8))
        result_box.columnconfigure(0, weight=1)
        result_box.rowconfigure(0, weight=1)

        self.result_text = ScrolledText(result_box, wrap="word", height=12)
        self.result_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

    def _build_extract_tab(self) -> None:
        self.extract_tab.columnconfigure(0, weight=1)
        self.extract_tab.rowconfigure(1, weight=1)

        info = ttk.LabelFrame(self.extract_tab, text="استخراج متن‌های قابل ترجمه از فایل پایتون")
        info.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        ttk.Label(
            info,
            text="این بخش متن‌هایی مثل text= ، title(...) ، help= و پیام‌های messagebox را از فایل پایتون استخراج می‌کند.",
            justify="right",
        ).grid(row=0, column=0, sticky="w", padx=10, pady=10)

        result_box = ttk.LabelFrame(self.extract_tab, text="خروجی استخراج")
        result_box.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        result_box.columnconfigure(0, weight=1)
        result_box.rowconfigure(0, weight=1)

        self.extract_text = ScrolledText(result_box, wrap="word", height=20)
        self.extract_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        actions = ttk.Frame(self.extract_tab)
        actions.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        ttk.Button(actions, text="استخراج از فایل انتخاب‌شده", command=self.run_extract).pack(side="right")
        ttk.Button(actions, text="ذخیره CSV", command=self.save_extract_csv).pack(side="right", padx=(0, 8))

    def choose_file(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[
                ("Supported files", "*.py *.txt *.json *.js *.ts *.jsx *.tsx *.html *.css *.md *.ini *.cfg *.yaml *.yml"),
                ("All files", "*.*"),
            ]
        )
        if path:
            self.target_var.set(path)

    def choose_folder(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.target_var.set(path)

    def show_defaults(self) -> None:
        text = "\n".join(f"{a} => {b}" for a, b in COMMON_REPLACEMENTS)
        messagebox.showinfo("جایگزینی‌های پیش‌فرض", text)

    def run_apply(self) -> None:
        target_text = self.target_var.get().strip()
        if not target_text:
            messagebox.showerror("خطا", "اول فایل یا پوشه را انتخاب کنید.")
            return

        target = Path(target_text)
        if not target.exists():
            messagebox.showerror("خطا", "مسیر انتخاب‌شده وجود ندارد.")
            return

        replacements = build_replacements(self.custom_text.get("1.0", "end"))
        extensions = parse_extensions(self.extensions_var.get().strip())
        files = list(iter_target_files(target, self.recursive_var.get(), extensions))

        if not files:
            messagebox.showerror("خطا", "هیچ فایل مناسبی پیدا نشد.")
            return

        self.result_text.delete("1.0", "end")
        changed_count = 0
        touched_replacements = 0
        error_count = 0

        for file_path in files:
            result = process_file(
                file_path,
                replacements=replacements,
                create_backup=self.backup_var.get(),
                apply_rtl_fixes=self.rtl_fixes_var.get(),
            )
            if result.error:
                error_count += 1
                self.result_text.insert("end", f"خطا: {result.path}\n{result.error}\n\n")
                continue

            if result.changed:
                changed_count += 1
                touched_replacements += result.replacements
                self.result_text.insert("end", f"ویرایش شد: {result.path} | تعداد جایگزینی: {result.replacements}\n")
            else:
                self.result_text.insert("end", f"بدون تغییر: {result.path}\n")

        self.result_text.insert(
            "end",
            f"\nپایان کار\n"
            f"فایل‌های بررسی‌شده: {len(files)}\n"
            f"فایل‌های ویرایش‌شده: {changed_count}\n"
            f"تعداد کل جایگزینی‌ها: {touched_replacements}\n"
            f"تعداد خطاها: {error_count}\n",
        )
        self.status_var.set("فارسی‌سازی انجام شد.")

    def run_extract(self) -> None:
        target_text = self.target_var.get().strip()
        if not target_text:
            messagebox.showerror("خطا", "اول یک فایل پایتون انتخاب کنید.")
            return

        path = Path(target_text)
        if not path.exists() or not path.is_file():
            messagebox.showerror("خطا", "فقط یک فایل پایتون را انتخاب کنید.")
            return

        if path.suffix.lower() != ".py":
            messagebox.showerror("خطا", "استخراج متن فعلاً فقط برای فایل‌های پایتون فعال است.")
            return

        try:
            items = extract_strings_from_python(path)
        except Exception as exc:
            messagebox.showerror("خطا", str(exc))
            return

        self.extract_text.delete("1.0", "end")
        if not items:
            self.extract_text.insert("1.0", "متنی برای استخراج پیدا نشد.")
            self.status_var.set("چیزی پیدا نشد.")
            return

        for item in items:
            self.extract_text.insert("end", item + "\n")

        self.status_var.set(f"{len(items)} متن استخراج شد.")

    def save_extract_csv(self) -> None:
        content = self.extract_text.get("1.0", "end").strip()
        if not content or content == "متنی برای استخراج پیدا نشد.":
            messagebox.showerror("خطا", "اول استخراج را انجام بده.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["source_text", "persian_text"])
            for line in lines:
                writer.writerow([line, ""])

        self.status_var.set("فایل CSV ذخیره شد.")
        messagebox.showinfo("انجام شد", "CSV ذخیره شد.")

def main() -> None:
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass
    PersianizerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
