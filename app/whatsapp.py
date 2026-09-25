"""
PhotoScore WhatsApp Integration — Meta Cloud API webhook handler.

Handles: incoming messages, image downloads, conversation flow.
"""

import httpx
import os
import logging

logger = logging.getLogger(__name__)

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID", "")
WHATSAPP_API_URL = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_ID}/messages"

MARKETPLACE_MAP = {
    "1": "amazon",
    "2": "flipkart",
    "3": "meesho",
    "4": "etsy",
    "5": "ebay",
    "6": "shopify",
    "7": "other",
    # Also accept text names
    "amazon": "amazon",
    "flipkart": "flipkart",
    "meesho": "meesho",
    "etsy": "etsy",
    "ebay": "ebay",
    "shopify": "shopify",
}


async def send_whatsapp_message(to: str, text: str):
    """Send a text message via WhatsApp Cloud API."""
    if not WHATSAPP_TOKEN:
        logger.warning("WhatsApp token not configured — message not sent")
        return

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(WHATSAPP_API_URL, json=payload, headers=headers)
            if resp.status_code != 200:
                logger.error(f"WhatsApp send failed: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"WhatsApp send error: {e}")


async def download_whatsapp_media(media_id: str) -> bytes | None:
    """Download media (image) from WhatsApp using media ID."""
    if not WHATSAPP_TOKEN:
        logger.warning("WhatsApp token not configured")
        return None

    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}

    async with httpx.AsyncClient() as client:
        # Step 1: Get media URL from media ID
        try:
            resp = await client.get(
                f"https://graph.facebook.com/v20.0/{media_id}",
                headers=headers,
            )
            if resp.status_code != 200:
                logger.error(f"Media URL fetch failed: {resp.text}")
                return None

            media_url = resp.json().get("url")
            if not media_url:
                return None

            # Step 2: Download the actual media file
            media_resp = await client.get(media_url, headers=headers)
            if media_resp.status_code == 200:
                return media_resp.content
            else:
                logger.error(f"Media download failed: {media_resp.status_code}")
                return None

        except Exception as e:
            logger.error(f"Media download error: {e}")
            return None


def extract_message_data(body: dict) -> dict | None:
    """
    Extract relevant data from incoming WhatsApp webhook payload.
    
    Returns dict with: phone, type (text/image), text_body, media_id
    """
    try:
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return None

        msg = messages[0]
        phone = msg.get("from", "")
        msg_type = msg.get("type", "")

        data = {
            "phone": phone,
            "type": msg_type,
            "text_body": "",
            "media_id": "",
        }

        if msg_type == "text":
            data["text_body"] = msg.get("text", {}).get("body", "").strip()
        elif msg_type == "image":
            data["media_id"] = msg.get("image", {}).get("id", "")

        return data

    except (IndexError, KeyError, TypeError) as e:
        logger.error(f"Failed to parse webhook: {e}")
        return None
