QR Product Generator

این ابزار برای ساخت QR Code لینک محصولات و تحویل خروجی PNG آماده شده.

ویژگی‌ها:
- ساخت QR برای یک لینک
- ساخت گروهی از روی CSV / TXT
- خروجی PNG
- امکان ساخت ZIP از همه PNGها
- تنظیم کیفیت، حاشیه، و Error Correction

اجرای GUI:
python qr_product_generator.py

اجرای تک‌لینک از خط فرمان:
python qr_product_generator.py --url "https://example.com/product/123" --name "product-123"

اجرای گروهی از فایل CSV:
python qr_product_generator.py --batch-file products.csv --zip

نمونه CSV:
name,url
product-1,https://example.com/p/1
product-2,https://example.com/p/2

نمونه TXT:
product-1,https://example.com/p/1
product-2,https://example.com/p/2
https://example.com/p/3
