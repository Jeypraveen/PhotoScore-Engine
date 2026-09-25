"""
PhotoScore Multilingual System.

All user-facing text in 10 languages. Easily extendable to more.
Each language has complete message templates for the WhatsApp bot flow.
"""

# Supported languages with display names
SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "हिंदी",
    "pt": "Português",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "tr": "Türkçe",
    "ar": "العربية",
    "id": "Bahasa Indonesia",
    "bn": "বাংলা",
}

# Language selection menu (sent on first contact)
LANGUAGE_MENU = """🌍 *Welcome to PhotoScore!* 📸

Choose your language / अपनी भाषा चुनें:

1. English
2. हिंदी
3. Português
4. Español
5. Français
6. Deutsch
7. Türkçe
8. العربية
9. Bahasa Indonesia
10. বাংলা

_Reply with the number_ 👆"""

# Map number replies to language codes
NUMBER_TO_LANG = {
    "1": "en", "2": "hi", "3": "pt", "4": "es", "5": "fr",
    "6": "de", "7": "tr", "8": "ar", "9": "id", "10": "bn",
}

# ─────────────────────────────────────────────
# COMPLETE MESSAGE TEMPLATES PER LANGUAGE
# ─────────────────────────────────────────────

MESSAGES = {
    "en": {
        "welcome": "Hello! 📸 I'm *PhotoScore*\nSend me your product photo and I'll tell you if it will sell!\n\nWhich marketplace?\n1. Amazon\n2. Flipkart\n3. Meesho\n4. Etsy\n5. eBay\n6. Shopify\n7. Other / Instagram",
        "marketplace_set": "✅ *{marketplace}* selected!\nNow send me your product photo 📸",
        "send_photo": "Please send me a product photo to analyze 📸",
        "analyzing": "🔍 Analyzing your photo...",
        "score_header": "📊 *PhotoScore: {score}/100* {emoji}",
        "category_bg": "🔲 Background ({score}/25)",
        "category_sharp": "🔍 Sharpness ({score}/20)",
        "category_frame": "🎯 Framing ({score}/20)",
        "category_light": "💡 Lighting ({score}/20)",
        "category_comply": "📋 Compliance ({score}/15)",
        "marketplace_result": "\n*Marketplace Ready:*\n{results}",
        "free_remaining": "\n━━━━━━━━━━━━\n📊 {remaining}/{total} free checks left today",
        "limit_reached": "⚠️ You've used all your free checks today!\n\nUnlimited checks: *{price}/month*\n💳 Pay now: {payment_link}\n\nYour plan activates instantly after payment ✅",
        "fix_and_retry": "\n*To improve the quality of the photo, do these steps:*",
        "photo_great": "\n🎉 *Great photo! This will sell!*",
        # Issue messages
        "bg_not_white": "→ Background is not pure white\n→ Fix: Use a white sheet or white wall",
        "bg_cluttered": "→ Background is cluttered/messy\n→ Fix: Use a clean, solid color background",
        "photo_blurry": "→ Photo is blurry\n→ Fix: Hold phone steady, use good lighting",
        "photo_soft": "→ Photo is slightly soft\n→ Fix: Tap on product to focus before shooting",
        "too_dark": "→ Photo is too dark\n→ Fix: Take photo near a window with natural light",
        "too_bright": "→ Photo is overexposed/washed out\n→ Fix: Avoid direct sunlight, use diffused light",
        "low_contrast": "→ Low contrast — product doesn't stand out\n→ Fix: Improve lighting or use contrasting background",
        "product_too_small": "→ Product is too small in the frame\n→ Fix: Move camera closer to the product",
        "not_centered": "→ Product is not centered\n→ Fix: Place product in the center of the frame",
        "has_text_watermark": "→ Text or watermark detected\n→ Fix: Remove all text, logos, and watermarks",
        "low_resolution": "→ Image resolution too low\n→ Fix: Use higher camera resolution settings",
    },
    "hi": {
        "welcome": "नमस्ते! 📸 मैं *PhotoScore* हूं\nअपनी product photo भेजो, मैं बताऊंगा कि ये sell करेगी या नहीं!\n\nकौन सा marketplace?\n1. Amazon\n2. Flipkart\n3. Meesho\n4. Etsy\n5. eBay\n6. Shopify\n7. Other / Instagram",
        "marketplace_set": "✅ *{marketplace}* selected!\nअब अपनी product photo भेजो 📸",
        "send_photo": "Product photo भेजो analyze करने के लिए 📸",
        "analyzing": "🔍 Photo check हो रही है...",
        "score_header": "📊 *PhotoScore: {score}/100* {emoji}",
        "category_bg": "🔲 Background ({score}/25)",
        "category_sharp": "🔍 Clarity ({score}/20)",
        "category_frame": "🎯 Framing ({score}/20)",
        "category_light": "💡 Lighting ({score}/20)",
        "category_comply": "📋 Rules ({score}/15)",
        "marketplace_result": "\n*Marketplace Ready:*\n{results}",
        "free_remaining": "\n━━━━━━━━━━━━\n📊 आज {remaining}/{total} free checks बचे हैं",
        "limit_reached": "⚠️ आज के free checks खत्म हो गए!\n\nUnlimited checks: *{price}/month*\n💳 Pay करो: {payment_link}\n\nPayment के बाद तुरंत activate हो जाएगा ✅",
        "fix_and_retry": "\n*Photo की quality improve करने के लिए ये steps follow करें:*",
        "photo_great": "\n🎉 *बहुत अच्छी photo! ये sell करेगी!*",
        "bg_not_white": "→ Background white नहीं है\n→ Fix: White sheet या white wall use करो",
        "bg_cluttered": "→ Background गंदा/cluttered है\n→ Fix: साफ, एक रंग का background use करो",
        "photo_blurry": "→ Photo blurry है\n→ Fix: Phone steady रखो, अच्छी light में photo लो",
        "photo_soft": "→ Photo थोड़ा soft है\n→ Fix: Photo लेने से पहले product पर tap करके focus करो",
        "too_dark": "→ Photo बहुत dark है\n→ Fix: Window के पास natural light में photo लो",
        "too_bright": "→ Photo बहुत bright/washed out है\n→ Fix: Direct sunlight avoid करो",
        "low_contrast": "→ Product clearly नहीं दिख रहा\n→ Fix: Lighting improve करो",
        "product_too_small": "→ Product frame में बहुत छोटा है\n→ Fix: Camera product के पास लेकर जाओ",
        "not_centered": "→ Product center में नहीं है\n→ Fix: Product को frame के बीच में रखो",
        "has_text_watermark": "→ Text या watermark detect हुआ\n→ Fix: सारे text, logo, watermark हटाओ",
        "low_resolution": "→ Image resolution कम है\n→ Fix: Camera settings में high resolution select करो",
    },
    "pt": {
        "welcome": "Olá! 📸 Eu sou o *PhotoScore*\nEnvie a foto do seu produto e eu direi se ela vai vender!\n\nQual marketplace?\n1. Amazon\n2. Mercado Livre\n3. Shopee\n4. Etsy\n5. eBay\n6. Shopify",
        "marketplace_set": "✅ *{marketplace}* selecionado!\nAgora envie a foto do seu produto 📸",
        "send_photo": "Envie uma foto do produto para análise 📸",
        "analyzing": "🔍 Analisando sua foto...",
        "score_header": "📊 *PhotoScore: {score}/100* {emoji}",
        "category_bg": "🔲 Fundo ({score}/25)",
        "category_sharp": "🔍 Nitidez ({score}/20)",
        "category_frame": "🎯 Enquadramento ({score}/20)",
        "category_light": "💡 Iluminação ({score}/20)",
        "category_comply": "📋 Conformidade ({score}/15)",
        "marketplace_result": "\n*Pronto para marketplace:*\n{results}",
        "free_remaining": "\n━━━━━━━━━━━━\n📊 {remaining}/{total} verificações grátis restantes hoje",
        "limit_reached": "⚠️ Suas verificações grátis acabaram!\n\nVerificações ilimitadas: *{price}/mês*\n💳 Pague agora: {payment_link}\n\nAtivação instantânea após pagamento ✅",
        "fix_and_retry": "\nCorreija e envie novamente! 💪",
        "photo_great": "\n🎉 *Ótima foto! Essa vai vender!*",
        "bg_not_white": "→ Fundo não é branco puro\n→ Correção: Use um lençol ou parede branca",
        "bg_cluttered": "→ Fundo está poluído\n→ Correção: Use um fundo limpo de cor sólida",
        "photo_blurry": "→ Foto está borrada\n→ Correção: Segure o celular firme, use boa iluminação",
        "photo_soft": "→ Foto levemente fora de foco\n→ Correção: Toque no produto para focar antes de tirar a foto",
        "too_dark": "→ Foto muito escura\n→ Correção: Tire a foto perto de uma janela com luz natural",
        "too_bright": "→ Foto superexposta\n→ Correção: Evite luz solar direta",
        "low_contrast": "→ Baixo contraste\n→ Correção: Melhore a iluminação",
        "product_too_small": "→ Produto muito pequeno no quadro\n→ Correção: Aproxime a câmera do produto",
        "not_centered": "→ Produto não está centralizado\n→ Correção: Coloque o produto no centro",
        "has_text_watermark": "→ Texto ou marca d'água detectada\n→ Correção: Remova todos os textos e logos",
        "low_resolution": "→ Resolução da imagem muito baixa\n→ Correção: Use configurações de alta resolução",
    },
    "es": {
        "welcome": "¡Hola! 📸 Soy *PhotoScore*\nEnvíame la foto de tu producto y te diré si se venderá.\n\nQué marketplace?\n1. Amazon\n2. Mercado Libre\n3. Shopee\n4. Etsy\n5. eBay\n6. Shopify",
        "marketplace_set": "✅ *{marketplace}* seleccionado!\nAhora envía tu foto de producto 📸",
        "send_photo": "Envía una foto del producto para analizar 📸",
        "analyzing": "🔍 Analizando tu foto...",
        "score_header": "📊 *PhotoScore: {score}/100* {emoji}",
        "category_bg": "🔲 Fondo ({score}/25)",
        "category_sharp": "🔍 Nitidez ({score}/20)",
        "category_frame": "🎯 Encuadre ({score}/20)",
        "category_light": "💡 Iluminación ({score}/20)",
        "category_comply": "📋 Cumplimiento ({score}/15)",
        "marketplace_result": "\n*Listo para marketplace:*\n{results}",
        "free_remaining": "\n━━━━━━━━━━━━\n📊 {remaining}/{total} verificaciones gratis restantes hoy",
        "limit_reached": "⚠️ Tus verificaciones gratis se acabaron!\n\nVerificaciones ilimitadas: *{price}/mes*\n💳 Paga ahora: {payment_link}\n\nActivación instantánea ✅",
        "fix_and_retry": "\n¡Corrige y envía de nuevo! 💪",
        "photo_great": "\n🎉 *¡Gran foto! ¡Esto se venderá!*",
        "bg_not_white": "→ Fondo no es blanco puro\n→ Solución: Usa una sábana o pared blanca",
        "bg_cluttered": "→ Fondo desordenado\n→ Solución: Usa un fondo limpio de color sólido",
        "photo_blurry": "→ Foto borrosa\n→ Solución: Mantén el teléfono firme",
        "photo_soft": "→ Foto ligeramente desenfocada\n→ Solución: Toca el producto para enfocar",
        "too_dark": "→ Foto demasiado oscura\n→ Solución: Toma la foto cerca de una ventana",
        "too_bright": "→ Foto sobreexpuesta\n→ Solución: Evita la luz solar directa",
        "low_contrast": "→ Bajo contraste\n→ Solución: Mejora la iluminación",
        "product_too_small": "→ Producto muy pequeño en el cuadro\n→ Solución: Acerca la cámara al producto",
        "not_centered": "→ Producto no está centrado\n→ Solución: Coloca el producto en el centro",
        "has_text_watermark": "→ Texto o marca de agua detectada\n→ Solución: Elimina todo texto y logos",
        "low_resolution": "→ Resolución de imagen muy baja\n→ Solución: Usa configuración de alta resolución",
    },
    "fr": {
        "welcome": "Bonjour! 📸 Je suis *PhotoScore*\nEnvoyez-moi votre photo produit et je vous dirai si elle se vendra!\n\nQuel marketplace?\n1. Amazon\n2. Cdiscount\n3. Leboncoin\n4. Etsy\n5. eBay\n6. Shopify",
        "marketplace_set": "✅ *{marketplace}* sélectionné!\nEnvoyez maintenant votre photo produit 📸",
        "send_photo": "Envoyez une photo produit à analyser 📸",
        "analyzing": "🔍 Analyse en cours...",
        "score_header": "📊 *PhotoScore: {score}/100* {emoji}",
        "category_bg": "🔲 Fond ({score}/25)",
        "category_sharp": "🔍 Netteté ({score}/20)",
        "category_frame": "🎯 Cadrage ({score}/20)",
        "category_light": "💡 Éclairage ({score}/20)",
        "category_comply": "📋 Conformité ({score}/15)",
        "marketplace_result": "\n*Prêt pour le marketplace:*\n{results}",
        "free_remaining": "\n━━━━━━━━━━━━\n📊 {remaining}/{total} vérifications gratuites restantes aujourd'hui",
        "limit_reached": "⚠️ Vos vérifications gratuites sont épuisées!\n\nVérifications illimitées: *{price}/mois*\n💳 Payez maintenant: {payment_link}\n\nActivation instantanée ✅",
        "fix_and_retry": "\nCorrigez et renvoyez! 💪",
        "photo_great": "\n🎉 *Super photo! Ça va se vendre!*",
        "bg_not_white": "→ Le fond n'est pas blanc pur\n→ Solution: Utilisez un drap ou mur blanc",
        "bg_cluttered": "→ Fond encombré\n→ Solution: Utilisez un fond propre et uni",
        "photo_blurry": "→ Photo floue\n→ Solution: Tenez le téléphone stable",
        "photo_soft": "→ Photo légèrement floue\n→ Solution: Touchez le produit pour faire la mise au point",
        "too_dark": "→ Photo trop sombre\n→ Solution: Prenez la photo près d'une fenêtre",
        "too_bright": "→ Photo surexposée\n→ Solution: Évitez la lumière directe du soleil",
        "low_contrast": "→ Faible contraste\n→ Solution: Améliorez l'éclairage",
        "product_too_small": "→ Produit trop petit dans le cadre\n→ Solution: Rapprochez l'appareil du produit",
        "not_centered": "→ Produit pas centré\n→ Solution: Placez le produit au centre",
        "has_text_watermark": "→ Texte ou filigrane détecté\n→ Solution: Supprimez tout texte et logo",
        "low_resolution": "→ Résolution d'image trop faible\n→ Solution: Utilisez une résolution plus élevée",
    },
}

# For languages not yet fully translated, fall back to English
_FALLBACK_LANG = "en"


def get_message(lang: str, key: str, **kwargs) -> str:
    """Get a translated message with variable substitution."""
    messages = MESSAGES.get(lang, MESSAGES[_FALLBACK_LANG])
    template = messages.get(key, MESSAGES[_FALLBACK_LANG].get(key, key))
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


def get_score_emoji(score: int) -> str:
    """Get emoji based on score."""
    if score >= 80:
        return "✅"
    elif score >= 50:
        return "⚠️"
    else:
        return "❌"


def format_score_report(result, lang: str = "en", remaining: int = 5, total: int = 5, price: str = "₹299", marketplace: str = "amazon") -> str:
    """Format a complete score report message for WhatsApp."""
    emoji = get_score_emoji(result.total_score)
    lines = []

    # Header
    lines.append(get_message(lang, "score_header", score=result.total_score, emoji=emoji))
    lines.append("")

    # Category scores
    lines.append(get_message(lang, "category_bg", score=result.background.score))
    for issue in result.issues:
        if issue["type"] == "background":
            lines.append(get_message(lang, issue["detail_key"]))

    lines.append(get_message(lang, "category_sharp", score=result.sharpness.score))
    for issue in result.issues:
        if issue["type"] == "sharpness":
            lines.append(get_message(lang, issue["detail_key"]))

    lines.append(get_message(lang, "category_frame", score=result.product.score))
    for issue in result.issues:
        if issue["type"] == "framing":
            lines.append(get_message(lang, issue["detail_key"]))

    lines.append(get_message(lang, "category_light", score=result.lighting.score))
    for issue in result.issues:
        if issue["type"] == "lighting":
            lines.append(get_message(lang, issue["detail_key"]))

    lines.append(get_message(lang, "category_comply", score=result.text_detection.score))
    for issue in result.issues:
        if issue["type"] in ("compliance", "resolution"):
            lines.append(get_message(lang, issue["detail_key"]))

    # Marketplace results
    mp_lines = []
    for mp, passed in result.marketplace_pass.items():
        mp_lines.append(f"{'✅' if passed else '❌'} {mp.capitalize()}")
    lines.append(get_message(lang, "marketplace_result", results="\n".join(mp_lines)))

    # Verdict and Strategies
    passed_own_marketplace = result.marketplace_pass.get(marketplace, False)
    if passed_own_marketplace:
        lines.append(get_message(lang, "photo_great"))
    elif len(result.issues) > 0:
        lines.append(get_message(lang, "fix_and_retry"))

    # Free tier counter
    lines.append(get_message(lang, "free_remaining", remaining=remaining, total=total))

    return "\n".join(lines)
