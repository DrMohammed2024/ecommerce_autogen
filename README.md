# ecommerce_autogen

مشروع محلي لبناء منظومة تجارة إلكترونية متعددة الوكلاء باستخدام AutoGen لاحقًا.

## الوضع الحالي

- Python 3.11
- SQLite محلي
- Mock Mode مفعّل
- لا توجد خدمات خارجية
- لا توجد مدفوعات
- لا توجد مفاتيح API

## التشغيل

```powershell
Set-Location C:\Projects\ecommerce_autogen
.\.venv\Scripts\Activate.ps1
```

## الاختبارات

```powershell
python -m pytest
```

## الفحص

```powershell
python -m ruff check app tests
python -m mypy app
```
