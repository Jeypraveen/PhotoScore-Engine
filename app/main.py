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
from datetime import datetime, timezone
from fastapi import FastAPI, Request, UploadFile, File, Query, HTTPException, Depends, Security, BackgroundTasks
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import JSONResponse
import hmac
import hashlib
import re
import time
import razorpay

def verify_sig(secret: str, raw: bytes, header: str) -> bool:
    if not secret or not header:
        return False
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(expected.encode(), header.replace("sha256=", "").encode())
    except TypeError:
        return False


from app.cv_engine import analyze_photo, load_image_from_bytes
from app.whatsapp import (
    extract_all_messages,
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
    get_supabase,
    claim_event,
    release_event,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PhotoScore",
    description="Multilingual product photo quality checker for e-commerce sellers",
    version="1.0.0",
)

# WhatsApp verification token (set in Meta dashboard)
VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN")
META_APP_SECRET = os.environ.get("META_APP_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")

# Pricing by region (for display in messages)
PRICING = {
    "default": "₹299",
}


# Security & Authentication
API_KEY = os.environ.get("PHOTOSCORE_API_KEY", "")
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if not API_KEY:
        logger.critical("PHOTOSCORE_API_KEY is not configured! Endpoint access denied.")
        raise HTTPException(status_code=500, detail="Server misconfiguration")
    
    if not api_key_header:
        raise HTTPException(status_code=403, detail="Could not validate API key")
        
    # Use compare_digest to prevent timing attacks safely on bytes
    try:
        if hmac.compare_digest(api_key_header.encode('utf-8'), API_KEY.encode('utf-8')):
            return api_key_header
    except Exception:
        pass
        
    raise HTTPException(status_code=403, detail="Could not validate API key")


@app.on_event("startup")
def startup():
    """Initialize database and configurations on startup."""
    try:
        init_db()
        logger.info("PhotoScore Database initialized ✅")
        if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
            logger.warning("RAZORPAY_KEY_ID or RAZORPAY_KEY_SECRET is not configured! Payment links will fall back to placeholder.")
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
    if not VERIFY_TOKEN:
        logger.critical("WHATSAPP_VERIFY_TOKEN is not configured.")
        raise HTTPException(status_code=500, detail="Server misconfiguration")

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


import json
from concurrent.futures import ThreadPoolExecutor
import os
import asyncio

CV_N = int(os.environ.get("CV_CONCURRENCY", "2"))
CV_SEM = asyncio.Semaphore(CV_N)
CV_POOL = ThreadPoolExecutor(max_workers=CV_N)
MAX_BODY = 1_000_000

@app.post("/webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle incoming WhatsApp messages — main bot logic."""
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > MAX_BODY:
        raise HTTPException(status_code=413, detail="Payload too large")
        
    raw_body = await request.body()
    if len(raw_body) > MAX_BODY:
        raise HTTPException(status_code=413, detail="Payload too large")
        
    signature = request.headers.get("X-Hub-Signature-256", "")
    
    if not META_APP_SECRET:
        logger.critical("META_APP_SECRET is not configured. Webhooks are locked down.")
        raise HTTPException(status_code=500, detail="Server misconfiguration")

    if not verify_sig(META_APP_SECRET, raw_body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    body = json.loads(raw_body)
    
    for msg_data in extract_all_messages(body):
        wamid = msg_data.get("wamid")
        if wamid:
            try:
                is_new = await asyncio.to_thread(claim_event, wamid)
                if not is_new:
                    continue
            except Exception as e:
                logger.error(f"Database error during wamid claim: {e}")
                raise HTTPException(status_code=503, detail="Database error")
                
        background_tasks.add_task(process_whatsapp_message, msg_data)

    return JSONResponse({"status": "ok"})


async def process_whatsapp_message(msg_data: dict):
    try:
        phone = msg_data["phone"]
        msg_type = msg_data["type"]
    
        # Get or create user
        user = await asyncio.to_thread(get_or_create_user, phone)
        lang = user.get("language") or "en"
        marketplace = user.get("marketplace", "amazon")
    
        # ── TEXT MESSAGE ──
        if msg_type == "text":
            text = msg_data["text_body"].lower().strip()
            await handle_text_message(phone, text, user, lang)
    
        # ── IMAGE MESSAGE ──
        elif msg_type == "image":
            await handle_image_message(phone, msg_data["media_id"], user, lang, marketplace)
    except Exception as e:
        logger.error(f"Failed to process background WhatsApp message: {e}")


async def handle_text_message(phone: str, text: str, user: dict, lang: str):
    """Handle text messages — language selection, marketplace selection, etc."""

    if user.get("language") is None:
        if text in NUMBER_TO_LANG:
            new_lang = NUMBER_TO_LANG[text]
            await asyncio.to_thread(set_user_language, phone, new_lang)
            await send_whatsapp_message(phone, get_message(new_lang, "welcome"))
        else:
            await send_whatsapp_message(phone, LANGUAGE_MENU)
        return

    if text in ("lang", "language"):
        await asyncio.to_thread(set_user_language, phone, None)
        await send_whatsapp_message(phone, LANGUAGE_MENU)
        return

    if text in MARKETPLACE_MAP:
        mp = MARKETPLACE_MAP[text]
        await asyncio.to_thread(set_user_marketplace, phone, mp)
        await send_whatsapp_message(phone, get_message(lang, "marketplace_set", marketplace=mp.capitalize()))
        return

    await send_whatsapp_message(phone, get_message(lang, "send_photo"))


async def handle_image_message(
    phone: str, media_id: str, user: dict, lang: str, marketplace: str
):
    """Handle image messages — download, analyze, and reply with score."""
    try:
        # Check usage limits
        if not can_check(phone):
            price = get_price_for_phone(phone)
            await send_whatsapp_message(
                phone,
                get_message(
                    lang, "limit_reached",
                    price=price,
                    payment_link=await asyncio.to_thread(create_razorpay_link, phone),
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

        # Analyze with CV engine (Offloaded to a thread pool with concurrency limits)
        loop = asyncio.get_running_loop()
        async with CV_SEM:
            result_tuple = await loop.run_in_executor(CV_POOL, load_image_from_bytes, image_bytes)
            if result_tuple is None:
                await send_whatsapp_message(phone, get_message(lang, "send_photo"))
                return
                
            img, size = result_tuple
            result = await asyncio.wait_for(
                loop.run_in_executor(CV_POOL, analyze_photo, img, marketplace, size), timeout=25
            )

        # Record usage
        await asyncio.to_thread(record_usage, phone, result.total_score)

        # Get remaining checks
        remaining, total = await asyncio.to_thread(get_remaining_checks, phone)

        # Format and send report
        price = get_price_for_phone(phone)
        report = format_score_report(
            result, lang=lang, remaining=remaining, total=total, price=price, marketplace=marketplace
        )
        await send_whatsapp_message(phone, report)
    except Exception as e:
        logger.exception(f"Failed to process image for {phone}: {e}")
        await send_whatsapp_message(phone, get_message(lang, "send_photo"))


def get_price_for_phone(phone: str) -> str:
    """Get localized price based on phone country code."""
    for code, price in PRICING.items():
        if code != "default" and phone.startswith(code):
            return price
    return PRICING["default"]


_PAYMENT_LINK_CACHE = {}

def create_razorpay_link(phone: str, amount_paise: int = 29900) -> str:
    """Create a dynamic Razorpay payment link with the user's phone attached and cached."""
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        return "https://photoscore.app/pay"
        
    now = time.time()
    # Check cache (expire locally after 23 hours to be safe)
    if phone in _PAYMENT_LINK_CACHE:
        link, expiry = _PAYMENT_LINK_CACHE[phone]
        if now < expiry:
            return link
        
    try:
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        expire_by = int(now + 86400) # 24 hours
        reference_id = f"ps_{phone}_{int(now)}"
        contact = f"+{phone}" if not phone.startswith('+') else phone
        
        data = {
            "amount": amount_paise,
            "currency": "INR",
            "description": "PhotoScore Pro (30 Days)",
            "reference_id": reference_id,
            "customer": {
                "contact": contact
            },
            "notify": {
                "sms": False,
                "email": False
            },
            "expire_by": expire_by,
            "notes": {
                "phone_number": phone
            }
        }
        payment_link = client.payment_link.create(data)
        url = payment_link.get("short_url", "https://photoscore.app/pay")
        
        _PAYMENT_LINK_CACHE[phone] = (url, now + 82800) # cache for 23 hours locally
        return url
    except Exception as e:
        logger.error(f"Failed to create Razorpay link for {phone}: {e}")
        return "https://photoscore.app/pay"

# ─────────────────────────────────────────────
# DIRECT API (for testing and future Shopify app)
# ─────────────────────────────────────────────

@app.post("/api/analyze")
async def analyze_endpoint(
    request: Request,
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

    content_length = request.headers.get("content-length")
    try:
        if content_length and int(content_length) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Content-Length")

    contents = await file.read(10 * 1024 * 1024 + 1)
    if len(contents) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=413, detail="File too large")
        
    result_tuple = load_image_from_bytes(contents)
    if result_tuple is None:
        raise HTTPException(status_code=400, detail="Could not read image")

    img, size = result_tuple
    result = await asyncio.wait_for(
        asyncio.to_thread(analyze_photo, img, marketplace, size), timeout=20
    )

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
async def razorpay_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receives automated webhook from Razorpay when a user successfully pays.
    Automatically upgrades their account to unlimited checks.
    """
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > MAX_BODY:
        raise HTTPException(status_code=413, detail="Payload too large")
        
    raw_body = await request.body()
    if len(raw_body) > MAX_BODY:
        raise HTTPException(status_code=413, detail="Payload too large")
        
    signature = request.headers.get("X-Razorpay-Signature", "")
    event_id = request.headers.get("X-Razorpay-Event-Id", "")
    
    if not RAZORPAY_WEBHOOK_SECRET:
        logger.critical("RAZORPAY_WEBHOOK_SECRET is not configured.")
        raise HTTPException(status_code=500, detail="Server misconfiguration")

    if not verify_sig(RAZORPAY_WEBHOOK_SECRET, raw_body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
        
    if event_id:
        try:
            is_new = await asyncio.to_thread(claim_event, event_id)
            if not is_new:
                return JSONResponse({"status": "ok"})
        except Exception as e:
            logger.error(f"Database error during Razorpay event claim: {e}")
            raise HTTPException(status_code=503, detail="Database error")
            
    try:
        body = await request.json()
        PLAN_PAISE = 29900  # ₹299
        
        event = body.get("event")
        if event in ("payment.captured", "payment_link.paid"):
            payload = body.get("payload", {})
            pay_entity = (payload.get("payment") or {}).get("entity", {})
            link_entity = (payload.get("payment_link") or {}).get("entity", {})
            
            if event == "payment.captured":
                src, status_expected = pay_entity, "captured"
            else:
                src, status_expected = link_entity, "paid"
                
            payment_id = pay_entity.get("id") or link_entity.get("id")
            
            # The phone number can be in the notes of the link or the payment
            notes = src.get("notes") if isinstance(src.get("notes"), dict) else pay_entity.get("notes")
            notes = notes if isinstance(notes, dict) else {}
            
            digits = re.sub(r"\D", "", str(notes.get("phone_number", "")))
            phone = "91" + digits if len(digits) == 10 else digits
            
            status = src.get("status")
            amount = src.get("amount")
            currency = src.get("currency")
            
            if status == status_expected and amount == PLAN_PAISE and currency == "INR" and phone and payment_id:
                # Dedupe on the actual payment/payment_link entity ID to prevent double-delivery double-crediting
                dedupe_key = f"pay:{payment_id}"
                try:
                    is_new_payment = await asyncio.to_thread(claim_event, dedupe_key)
                    if not is_new_payment:
                        logger.info(f"Payment {payment_id} already processed. Skipping.")
                        return JSONResponse({"status": "ok"})
                except Exception as e:
                    logger.error(f"Database error during Razorpay payment claim: {e}")
                    raise HTTPException(status_code=503, detail="Database error")
                    
                try:
                    user = await asyncio.to_thread(get_or_create_user, phone)
                    current_paid_until = user.get("paid_until")
                    
                    from datetime import timedelta
                    now = datetime.now(timezone.utc)
                    
                    if current_paid_until and datetime.fromisoformat(current_paid_until.replace("Z", "+00:00")) > now:
                        new_paid_until = (datetime.fromisoformat(current_paid_until.replace("Z", "+00:00")) + timedelta(days=30)).isoformat()
                    else:
                        new_paid_until = (now + timedelta(days=30)).isoformat()
                    
                    # Upgrade user in the database
                    updated = await asyncio.to_thread(set_user_paid, phone, new_paid_until)
                    
                    if updated:
                        await send_whatsapp_message(
                            phone, 
                            "🎉 *Payment Successful!*\nYour PhotoScore Pro plan is now active for 30 days. You have UNLIMITED checks! Send a photo to begin 📸"
                        )
                        logger.info(f"Account upgraded to PRO for {phone}")
                    else:
                        logger.error(f"Paid but no matching user for phone: {phone}")
                except Exception:
                    # Release the payment claim if something fails during the upgrade
                    await asyncio.to_thread(release_event, dedupe_key)
                    raise
            else:
                logger.warning(
                    "Ignored %s for %s: status=%s amount=%s currency=%s phone=%s payment_id=%s",
                    event, event_id, status, amount, currency, bool(phone), payment_id
                )
                    
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.error(f"Failed to process Razorpay webhook: {e}")
        if event_id:
            await asyncio.to_thread(release_event, event_id)
        raise HTTPException(status_code=500, detail="Internal Server Error")


# ─────────────────────────────────────────────
# HEALTH & STATS
# ─────────────────────────────────────────────

@app.get("/health")
async def health():
    """Shallow health check endpoint for load balancers."""
    return {"status": "ok", "service": "PhotoScore", "version": "1.0.0"}


@app.get("/stats")
async def stats(api_key: str = Depends(get_api_key)):
    """Admin stats endpoint."""
    return {
        "total_users": get_total_users(),
        "total_checks": get_total_checks(),
        "paid_users": get_paid_users(),
    }
