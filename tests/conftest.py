import os
import pytest

os.environ.setdefault("META_APP_SECRET", "test-meta")
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET", "test-rzp")
os.environ.setdefault("PHOTOSCORE_API_KEY", "testkey123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test-verify")
