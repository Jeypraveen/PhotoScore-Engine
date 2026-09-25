"""
PhotoScore — Main FastAPI Application.

Endpoints:
- POST /webhook          → WhatsApp incoming messages (Meta Cloud API)
- GET  /webhook           → WhatsApp verification (Meta setup)
- POST /api/analyze       → Direct API (for testing / future Shopify app)
- GET  /health            → Health check
- GET  /stats             → Admin stats
"""

import os
import logging
import asyncio
from fastapi import FastAPI, Request, UploadFile, File, Query, HTTPException, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import JSONResponse
import hmac
import hashlib


from app.cv_engine import analyze_photo, load_image_from_bytes
from app.whatsapp import (
    extract_message_data,
    send_whatsapp_message,
    download_whatsapp_media,
    MARKETPLACE_MAP,
)
from app.languages import (
    LANGUAGE_MENU,
    NUMBER_TO_LANG,
    SUPPORTED_LANGUAGES,
    get_message,
    format_score_report,
)
from app.database import (
    init_db,
    get_or_create_user,
    set_user_language,
    set_user_marketplace,
    record_usage,
    get_remaining_checks,
    can_check,
    get_total_users,
    get_total_checks,
    get_paid_users,
    set_user_paid,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PhotoScore",
    description="Multilingual product photo quality checker for e-commerce sellers",
    version="1.0.0",
)

# WhatsApp verification token (set in Meta dashboard)
VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "photoscore-verify-2026")
META_APP_SECRET = os.environ.get("META_APP_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")

# Pricing by region (for display in messages)
PRICING = {
    "default": "$4.99",
    "91": "₹299",      # India
    "55": "R$29",       # Brazil
    "52": "$99 MXN",    # Mexico
}


# Security & Authentication
API_KEY = os.environ.get("PHOTOSCORE_API_KEY", "default-dev-key")
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if not API_KEY or API_KEY == "default-dev-key":
        logger.warning("Using default API key or API key is unset!")
    
    # Use compare_digest to prevent timing attacks
    if hmac.compare_digest(str(api_key_header), str(API_KEY)):
        return api_key_header
    raise HTTPException(status_code=403, detail="Could not validate API key")


@app.on_event("startup")
def startup():
    """Initialize database and configurations on startup."""
    try:
        init_db()
        logger.info("PhotoScore Database initialized ✅")
        logger.info("PhotoScore Server started successfully 🚀")
    except Exception as e:
        logger.critical(f"Failed to initialize database during startup: {e}")
        raise e



# ─────────────────────────────────────────────
# WHATSAPP WEBHOOK (Core Bot Logic)
# ─────────────────────────────────────────────

@app.get("/webhook")
async def verify_webhook(request: Request):
    """WhatsApp webhook verification (required by Meta during setup)."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verified ✅")
        try:
            return int(challenge)
        except (ValueError, TypeError):
            raise HTTPException(status_code=403, detail="Invalid challenge format")
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def handle_webhook(request: Request):
    """Handle incoming WhatsApp messages — main bot logic."""
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "").replace("sha256=", "")
    
    if not META_APP_SECRET:
        logger.critical("META_APP_SECRET is not configured. Webhooks are locked down.")
        raise HTTPException(status_code=500, detail="Server misconfiguration")

    expected_sig = hmac.new(
        bytes(META_APP_SECRET, "utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected_sig, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    body = await request.json()
    msg_data = extract_message_data(body)

    if not msg_data:
        return JSONResponse({"status": "no message"})

    phone = msg_data["phone"]
    msg_type = msg_data["type"]

    # Get or create user
    user = get_or_create_user(phone)
    lang = user.get("language", "en")
    marketplace = user.get("marketplace", "amazon")

    # ── TEXT MESSAGE ──
    if msg_type == "text":
        text = msg_data["text_body"].lower().strip()
        await handle_text_message(phone, text, user, lang)

    # ── IMAGE MESSAGE ──
    elif msg_type == "image":
        await handle_image_message(phone, msg_data["media_id"], user, lang, marketplace)

    return JSONResponse({"status": "ok"})


async def handle_text_message(phone: str, text: str, user: dict, lang: str):
    """Handle text messages — language selection, marketplace selection, etc."""

    # Check if it's a language selection (number 1-10)
    if text in NUMBER_TO_LANG:
        new_lang = NUMBER_TO_LANG[text]
        set_user_language(phone, new_lang)
        await send_whatsapp_message(
            phone, get_message(new_lang, "welcome")
        )
        return

    # Check if it's a marketplace selection
    if text in MARKETPLACE_MAP:
        mp = MARKETPLACE_MAP[text]
        set_user_marketplace(phone, mp)
        await send_whatsapp_message(
            phone, get_message(lang, "marketplace_set", marketplace=mp.capitalize())
        )
        return

    # Any other text — check if user has language set
    if not user.get("language") or user["language"] == "en":
        # First time user or unset — show language menu
        await send_whatsapp_message(phone, LANGUAGE_MENU)
    else:
        # User has language set — ask for photo
        await send_whatsapp_message(
            phone, get_message(lang, "send_photo")
        )


async def handle_image_message(
    phone: str, media_id: str, user: dict, lang: str, marketplace: str
):
    """Handle image messages — download, analyze, and reply with score."""

    # Check usage limits
    if not can_check(phone):
        price = get_price_for_phone(phone)
        await send_whatsapp_message(
            phone,
            get_message(
                lang, "limit_reached",
                price=price,
                payment_link="https://photoscore.app/pay",  # Replace with real link
            ),
        )
        return

    # Send "analyzing" message
    await send_whatsapp_message(phone, get_message(lang, "analyzing"))

    # Download image from WhatsApp
    image_bytes = await download_whatsapp_media(media_id)
    if not image_bytes:
        await send_whatsapp_message(phone, get_message(lang, "send_photo"))
        return

    # Analyze with CV engine (Offloaded to a thread to prevent blocking event loop)
    img = load_image_from_bytes(image_bytes)
    if img is None:
        await send_whatsapp_message(phone, get_message(lang, "send_photo"))
        return
        
    result = await asyncio.to_thread(analyze_photo, img, marketplace)

    # Record usage
    record_usage(phone, result.total_score)

    # Get remaining checks
    remaining, total = get_remaining_checks(phone)

    # Format and send report
    price = get_price_for_phone(phone)
    report = format_score_report(
        result, lang=lang, remaining=remaining, total=total, price=price
    )
    await send_whatsapp_message(phone, report)


def get_price_for_phone(phone: str) -> str:
    """Get localized price based on phone country code."""
    for code, price in PRICING.items():
        if code != "default" and phone.startswith(code):
            return price
    return PRICING["default"]


# ─────────────────────────────────────────────
# DIRECT API (for testing and future Shopify app)
# ─────────────────────────────────────────────

@app.post("/api/analyze")
async def analyze_endpoint(
    file: UploadFile = File(...),
    marketplace: str = Query("amazon", description="Target marketplace"),
    api_key: str = Depends(get_api_key),
):
    """
    Direct API endpoint — upload image file, get quality analysis.
    
    For testing and future integrations (Shopify app, etc.)
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    contents = await file.read()
    img = load_image_from_bytes(contents)
    if img is None:
        raise HTTPException(status_code=400, detail="Could not read image")

    result = await asyncio.to_thread(analyze_photo, img, marketplace)

    return {
        "score": result.total_score,
        "scores": {
            "background": result.background.score,
            "sharpness": result.sharpness.score,
            "framing": result.product.score,
            "lighting": result.lighting.score,
            "compliance": result.text_detection.score,
        },
        "marketplace_pass": result.marketplace_pass,
        "resolution": {
            "width": result.resolution_width,
            "height": result.resolution_height,
            "meets_requirement": result.resolution_ok,
        },
        "issues": [
            {
                "type": issue["type"],
                "severity": issue["severity"],
                "code": issue["code"],
            }
            for issue in result.issues
        ],
        "details": {
            "background_white_pct": result.background.white_percentage,
            "sharpness_variance": result.sharpness.laplacian_variance,
            "brightness": result.lighting.brightness,
            "product_fill_pct": result.product.product_fill_percent,
            "product_centered": result.product.is_centered,
            "has_text": result.text_detection.has_watermark_or_text,
        },
    }


# ─────────────────────────────────────────────
# PAYMENT WEBHOOK (Razorpay)
# ─────────────────────────────────────────────

@app.post("/payment/webhook")
async def razorpay_webhook(request: Request):
    """
    Receives automated webhook from Razorpay when a user successfully pays.
    Automatically upgrades their account to unlimited checks.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    
    if not RAZORPAY_WEBHOOK_SECRET:
        logger.critical("RAZORPAY_WEBHOOK_SECRET is not configured.")
        raise HTTPException(status_code=500, detail="Server misconfiguration")

    expected_sig = hmac.new(
        bytes(RAZORPAY_WEBHOOK_SECRET, "utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected_sig, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
            
    body = await request.json()
    
    event = body.get("event")
    if event == "payment.captured":
        payload = body.get("payload", {}).get("payment", {}).get("entity", {})
        
        # We assume you pass the user's phone number in the payment notes during checkout
        notes = payload.get("notes", {})
        phone = notes.get("phone_number")
        
        if phone:
            # 30 days from now
            from datetime import datetime, timedelta
            paid_until = (datetime.now() + timedelta(days=30)).isoformat()
            
            # Upgrade user in the database
            set_user_paid(phone, paid_until)
            
            # Send them a success message on WhatsApp
            await send_whatsapp_message(
                phone, 
                "🎉 *Payment Successful!*\nYour PhotoScore Pro plan is now active for 30 days. You have UNLIMITED checks! Send a photo to begin 📸"
            )
            
            logger.info(f"Account upgraded to PRO for {phone}")
            
    return JSONResponse({"status": "ok"})


# ─────────────────────────────────────────────
# HEALTH & STATS
# ─────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "PhotoScore", "version": "1.0.0"}


@app.get("/stats")
async def stats(api_key: str = Depends(get_api_key)):
    """Admin stats endpoint."""
    return {
        "total_users": get_total_users(),
        "total_checks": get_total_checks(),
        "paid_users": get_paid_users(),
    }
