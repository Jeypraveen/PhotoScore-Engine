"""
PhotoScore CV Engine — Core image quality analysis.

All detection is pure OpenCV math. Zero AI/LLM dependency.
Each function analyzes one aspect of product photo quality.
"""

import cv2
import numpy as np
from dataclasses import dataclass, field


@dataclass
class BackgroundResult:
    """Results from background analysis."""
    white_percentage: float = 0.0
    color_uniformity: float = 0.0
    is_white_bg: bool = False
    is_clean_bg: bool = False
    dominant_color: tuple = (0, 0, 0)
    score: int = 0  # out of 25


@dataclass
class ProductResult:
    """Results from product/foreground detection."""
    product_found: bool = False
    product_fill_percent: float = 0.0
    is_well_framed: bool = False
    is_centered: bool = False
    center_offset: float = 0.0
    bounding_box: tuple = (0, 0, 0, 0)  # x, y, w, h
    score: int = 0  # out of 20


@dataclass
class SharpnessResult:
    """Results from sharpness/blur analysis."""
    laplacian_variance: float = 0.0
    is_sharp: bool = False
    is_blurry: bool = False
    score: int = 0  # out of 20


@dataclass
class LightingResult:
    """Results from lighting/brightness analysis."""
    brightness: float = 0.0
    contrast: float = 0.0
    overexposed_pct: float = 0.0
    underexposed_pct: float = 0.0
    is_good_lighting: bool = False
    score: int = 0  # out of 20


@dataclass
class TextDetectionResult:
    """Results from text/watermark detection."""
    text_regions_count: int = 0
    has_watermark_or_text: bool = False
    score: int = 0  # out of 15


@dataclass
class PhotoScoreResult:
    """Complete photo quality analysis result."""
    total_score: int = 0
    background: BackgroundResult = field(default_factory=BackgroundResult)
    product: ProductResult = field(default_factory=ProductResult)
    sharpness: SharpnessResult = field(default_factory=SharpnessResult)
    lighting: LightingResult = field(default_factory=LightingResult)
    text_detection: TextDetectionResult = field(default_factory=TextDetectionResult)
    resolution_ok: bool = False
    resolution_width: int = 0
    resolution_height: int = 0
    marketplace_pass: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)


def load_image(image_path: str) -> np.ndarray | None:
    """Load image from file path. Returns None if loading fails."""
    img = cv2.imread(image_path)
    if img is None:
        return None
    return img


def load_image_from_bytes(image_bytes: bytes) -> np.ndarray | None:
    """Load image from raw bytes (for WhatsApp media downloads)."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return img


# ─────────────────────────────────────────────
# 1. BACKGROUND DETECTION
# ─────────────────────────────────────────────

def analyze_background(img: np.ndarray) -> BackgroundResult:
    """
    Detect if the image has a white/clean background.
    
    Method: Sample corner and edge pixels (always background),
    check if they're white (RGB > 240) and uniform (low std dev).
    """
    result = BackgroundResult()
    h, w = img.shape[:2]
    corner_size = max(int(min(h, w) * 0.10), 10)

    # Sample all 4 corner regions
    corners = [
        img[0:corner_size, 0:corner_size],
        img[0:corner_size, w - corner_size:w],
        img[h - corner_size:h, 0:corner_size],
        img[h - corner_size:h, w - corner_size:w],
    ]

    # Also sample edge strips (top, bottom, left, right)
    edge_strip = max(int(min(h, w) * 0.05), 5)
    edges = [
        img[0:edge_strip, :],          # Top strip
        img[h - edge_strip:h, :],      # Bottom strip
        img[:, 0:edge_strip],          # Left strip
        img[:, w - edge_strip:w],      # Right strip
    ]

    # Combine all background samples
    all_bg_pixels = np.concatenate(
        [c.reshape(-1, 3) for c in corners] + [e.reshape(-1, 3) for e in edges]
    )

    # Convert BGR to RGB for intuitive color checking
    all_bg_rgb = all_bg_pixels[:, ::-1]

    # Check whiteness: all channels > 240
    white_mask = np.all(all_bg_rgb > 240, axis=1)
    result.white_percentage = round(float(np.mean(white_mask) * 100), 1)
    result.is_white_bg = result.white_percentage > 80

    # Check uniformity: low standard deviation = uniform color
    std_per_channel = np.std(all_bg_rgb.astype(np.float32), axis=0)
    avg_std = float(std_per_channel.mean())
    result.color_uniformity = round(max(0, 100 - avg_std * 2), 1)
    result.is_clean_bg = avg_std < 30

    # Dominant background color
    mean_color = all_bg_rgb.mean(axis=0).astype(int)
    result.dominant_color = tuple(mean_color.tolist())

    # Score (out of 25)
    if result.is_white_bg:
        result.score = min(25, int(result.white_percentage / 4))
    elif result.is_clean_bg:
        result.score = min(20, int(result.color_uniformity / 5))
    else:
        result.score = max(0, min(10, int(result.color_uniformity / 10)))

    return result


# ─────────────────────────────────────────────
# 2. PRODUCT/FOREGROUND DETECTION
# ─────────────────────────────────────────────

def analyze_product(img: np.ndarray) -> ProductResult:
    """
    Detect the main product in the image using GrabCut segmentation.
    
    Calculates: product location, frame fill percentage, centering.
    """
    result = ProductResult()
    h, w = img.shape[:2]

    # GrabCut initialization — assume product is in the center area
    margin_x = int(w * 0.05)
    margin_y = int(h * 0.05)
    rect = (margin_x, margin_y, w - margin_x * 2, h - margin_y * 2)

    mask = np.zeros((h, w), np.uint8)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)

    try:
        cv2.grabCut(img, mask, rect, bgd_model, fgd_model, 3, cv2.GC_INIT_WITH_RECT)
    except cv2.error:
        # GrabCut can fail on very small or uniform images — fallback
        return _fallback_product_detection(img)

    # Create binary mask: foreground = 1
    fg_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1, 0).astype(np.uint8)

    # Find product pixels
    product_pixels = np.where(fg_mask == 1)
    if len(product_pixels[0]) == 0:
        return _fallback_product_detection(img)

    result.product_found = True

    # Bounding box of the product
    y_min, y_max = int(product_pixels[0].min()), int(product_pixels[0].max())
    x_min, x_max = int(product_pixels[1].min()), int(product_pixels[1].max())
    result.bounding_box = (x_min, y_min, x_max - x_min, y_max - y_min)

    # Product fill percentage
    product_area = float(fg_mask.sum())
    total_area = float(h * w)
    result.product_fill_percent = round((product_area / total_area) * 100, 1)
    result.is_well_framed = result.product_fill_percent > 50

    # Centering check
    product_cx = (x_min + x_max) / 2
    product_cy = (y_min + y_max) / 2
    offset_x = abs(product_cx - w / 2) / w * 100
    offset_y = abs(product_cy - h / 2) / h * 100
    result.center_offset = round(max(offset_x, offset_y), 1)
    result.is_centered = result.center_offset < 15

    # Score (out of 20)
    fill_score = min(10, int(result.product_fill_percent / 10))
    center_score = max(0, 10 - int(result.center_offset / 2))
    result.score = fill_score + center_score

    return result


def _fallback_product_detection(img: np.ndarray) -> ProductResult:
    """Fallback using contour detection when GrabCut fails."""
    result = ProductResult()
    h, w = img.shape[:2]

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Adaptive threshold to find object
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
    )

    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        result.product_found = False
        result.score = 5
        return result

    # Largest contour is likely the product
    largest = max(contours, key=cv2.contourArea)
    x, y, cw, ch = cv2.boundingRect(largest)
    area = cv2.contourArea(largest)

    result.product_found = True
    result.bounding_box = (x, y, cw, ch)
    result.product_fill_percent = round((area / (h * w)) * 100, 1)
    result.is_well_framed = result.product_fill_percent > 30

    product_cx = x + cw / 2
    product_cy = y + ch / 2
    offset_x = abs(product_cx - w / 2) / w * 100
    offset_y = abs(product_cy - h / 2) / h * 100
    result.center_offset = round(max(offset_x, offset_y), 1)
    result.is_centered = result.center_offset < 15

    fill_score = min(10, int(result.product_fill_percent / 10))
    center_score = max(0, 10 - int(result.center_offset / 2))
    result.score = fill_score + center_score

    return result


# ─────────────────────────────────────────────
# 3. SHARPNESS / BLUR DETECTION
# ─────────────────────────────────────────────

def analyze_sharpness(img: np.ndarray) -> SharpnessResult:
    """
    Detect if image is sharp or blurry using Laplacian variance.
    
    Higher variance = more edges detected = sharper image.
    """
    result = SharpnessResult()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Laplacian edge detection
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    variance = float(laplacian.var())

    result.laplacian_variance = round(variance, 1)
    result.is_sharp = variance > 100
    result.is_blurry = variance < 50

    # Score (out of 20)
    if variance > 200:
        result.score = 20
    elif variance > 100:
        result.score = 16
    elif variance > 50:
        result.score = 10
    elif variance > 25:
        result.score = 5
    else:
        result.score = 2

    return result


# ─────────────────────────────────────────────
# 4. LIGHTING / BRIGHTNESS ANALYSIS
# ─────────────────────────────────────────────

def analyze_lighting(img: np.ndarray) -> LightingResult:
    """
    Check if image has good lighting — not too dark, not too bright.
    
    Also checks contrast and exposure distribution.
    """
    result = LightingResult()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    result.brightness = round(float(gray.mean()), 1)
    result.contrast = round(float(gray.std()), 1)

    # Check overexposure (too many pure white pixels that aren't background)
    result.overexposed_pct = round(float((gray > 250).mean() * 100), 1)
    result.underexposed_pct = round(float((gray < 10).mean() * 100), 1)

    # Good lighting: brightness 100-210, contrast 40-100
    good_brightness = 100 <= result.brightness <= 210
    good_contrast = result.contrast > 30
    not_overexposed = result.overexposed_pct < 40
    not_underexposed = result.underexposed_pct < 10

    result.is_good_lighting = good_brightness and good_contrast and not_overexposed and not_underexposed

    # Score (out of 20)
    score = 0
    if good_brightness:
        score += 8
    else:
        # Partial credit based on how far from ideal
        deviation = min(abs(result.brightness - 155), 100)
        score += max(0, 8 - int(deviation / 15))

    if good_contrast:
        score += 5
    else:
        score += 2

    if not_overexposed:
        score += 4
    if not_underexposed:
        score += 3

    result.score = min(20, score)
    return result


# ─────────────────────────────────────────────
# 5. TEXT / WATERMARK DETECTION
# ─────────────────────────────────────────────

def analyze_text_watermark(img: np.ndarray) -> TextDetectionResult:
    """
    Detect text or watermark overlays using MSER (Maximally Stable Extremal Regions).
    
    Marketplaces like Amazon/eBay reject images with text, logos, or watermarks.
    """
    result = TextDetectionResult()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]

    # MSER detects stable text-like regions
    mser = cv2.MSER_create(
        delta=5,
        min_area=30,
        max_area=int(h * w * 0.01),  # Max 1% of image
    )

    try:
        regions, _ = mser.detectRegions(gray)
    except cv2.error:
        result.score = 15  # Assume no text if detection fails
        return result

    # Filter for text-like shapes
    text_like_count = 0
    for region in regions:
        x, y, rw, rh = cv2.boundingRect(region)
        aspect_ratio = rw / max(rh, 1)
        area = rw * rh
        # Text characters: small, reasonable aspect ratio
        if 20 < area < 3000 and 0.2 < aspect_ratio < 5:
            text_like_count += 1

    result.text_regions_count = text_like_count

    # Threshold: if many text-like regions cluster → likely has text
    # Typical product photo without text: < 15 regions
    # Photo with watermark/text: > 30 regions
    result.has_watermark_or_text = text_like_count > 25

    # Score (out of 15)
    if not result.has_watermark_or_text:
        result.score = 15
    elif text_like_count > 50:
        result.score = 0  # Lots of text
    else:
        result.score = max(0, 15 - int(text_like_count / 3))

    return result


# ─────────────────────────────────────────────
# 6. RESOLUTION CHECK
# ─────────────────────────────────────────────

def check_resolution(img: np.ndarray, marketplace: str = "amazon") -> tuple[bool, int, int]:
    """Check if image resolution meets marketplace requirements."""
    h, w = img.shape[:2]

    min_requirements = {
        "amazon": 1000,
        "flipkart": 500,
        "meesho": 500,
        "etsy": 2000,
        "ebay": 1600,
        "shopify": 2048,
    }

    min_px = min_requirements.get(marketplace, 1000)
    longest_side = max(h, w)
    meets_requirement = longest_side >= min_px

    return meets_requirement, w, h


# ─────────────────────────────────────────────
# 7. MARKETPLACE PASS/FAIL RULES
# ─────────────────────────────────────────────

def check_marketplace_compliance(
    bg: BackgroundResult,
    product: ProductResult,
    sharpness: SharpnessResult,
    lighting: LightingResult,
    text: TextDetectionResult,
    resolution_ok: bool,
    marketplace: str = "amazon",
) -> bool:
    """Check if photo passes a specific marketplace's requirements."""
    rules = {
        "amazon": (
            bg.is_white_bg
            and product.product_fill_percent > 80
            and not text.has_watermark_or_text
            and resolution_ok
            and sharpness.is_sharp
        ),
        "flipkart": (
            bg.is_clean_bg
            and not text.has_watermark_or_text
            and resolution_ok
            and not sharpness.is_blurry
        ),
        "meesho": (
            bg.is_white_bg
            and resolution_ok
            and not sharpness.is_blurry
        ),
        "etsy": (
            sharpness.is_sharp
            and lighting.is_good_lighting
            and resolution_ok
        ),
        "ebay": (
            not text.has_watermark_or_text
            and resolution_ok
            and not sharpness.is_blurry
        ),
        "shopify": (
            sharpness.is_sharp
            and resolution_ok
            and lighting.is_good_lighting
        ),
        "other": (
            sharpness.is_sharp
            and bg.is_clean_bg
            and resolution_ok
        ),
    }
    return rules.get(marketplace, resolution_ok and not sharpness.is_blurry)


# ─────────────────────────────────────────────
# 8. MAIN ANALYSIS — PUTS EVERYTHING TOGETHER
# ─────────────────────────────────────────────

def analyze_photo(
    img: np.ndarray,
    marketplace: str = "amazon",
) -> PhotoScoreResult:
    """
    Complete photo quality analysis.
    
    Takes an image (numpy array) and returns a full quality report
    with scores, issues, and marketplace compliance.
    """
    result = PhotoScoreResult()

    # Run all analyses
    result.background = analyze_background(img)
    result.product = analyze_product(img)
    result.sharpness = analyze_sharpness(img)
    result.lighting = analyze_lighting(img)
    result.text_detection = analyze_text_watermark(img)

    # Resolution check
    result.resolution_ok, result.resolution_width, result.resolution_height = (
        check_resolution(img, marketplace)
    )

    # Total score (out of 100)
    result.total_score = (
        result.background.score
        + result.product.score
        + result.sharpness.score
        + result.lighting.score
        + result.text_detection.score
    )

    # Marketplace compliance
    all_marketplaces = ["amazon", "flipkart", "meesho", "etsy", "ebay", "shopify"]
    for mp in all_marketplaces:
        res_ok, _, _ = check_resolution(img, mp)
        result.marketplace_pass[mp] = check_marketplace_compliance(
            result.background,
            result.product,
            result.sharpness,
            result.lighting,
            result.text_detection,
            res_ok,
            mp,
        )

    # Generate issues list
    result.issues = _generate_issues(result, marketplace)

    return result


def _generate_issues(result: PhotoScoreResult, marketplace: str) -> list[dict]:
    """Generate human-readable issue descriptions."""
    issues = []

    # Background issues
    if not result.background.is_white_bg and marketplace in ("amazon", "meesho"):
        issues.append({
            "type": "background",
            "severity": "high",
            "code": "BG_NOT_WHITE",
            "detail_key": "bg_not_white",
        })
    elif not result.background.is_clean_bg:
        issues.append({
            "type": "background",
            "severity": "medium",
            "code": "BG_CLUTTERED",
            "detail_key": "bg_cluttered",
        })

    # Sharpness issues
    if result.sharpness.is_blurry:
        issues.append({
            "type": "sharpness",
            "severity": "high",
            "code": "BLURRY",
            "detail_key": "photo_blurry",
        })
    elif not result.sharpness.is_sharp:
        issues.append({
            "type": "sharpness",
            "severity": "medium",
            "code": "SLIGHTLY_SOFT",
            "detail_key": "photo_soft",
        })

    # Lighting issues
    if result.lighting.brightness < 80:
        issues.append({
            "type": "lighting",
            "severity": "high",
            "code": "TOO_DARK",
            "detail_key": "too_dark",
        })
    elif result.lighting.brightness > 220:
        issues.append({
            "type": "lighting",
            "severity": "high",
            "code": "TOO_BRIGHT",
            "detail_key": "too_bright",
        })
    elif result.lighting.contrast < 30:
        issues.append({
            "type": "lighting",
            "severity": "medium",
            "code": "LOW_CONTRAST",
            "detail_key": "low_contrast",
        })

    # Product framing issues
    if result.product.product_found:
        if result.product.product_fill_percent < 30:
            issues.append({
                "type": "framing",
                "severity": "high",
                "code": "PRODUCT_TOO_SMALL",
                "detail_key": "product_too_small",
            })
        elif not result.product.is_centered:
            issues.append({
                "type": "framing",
                "severity": "low",
                "code": "NOT_CENTERED",
                "detail_key": "not_centered",
            })

    # Text/watermark issues
    if result.text_detection.has_watermark_or_text:
        issues.append({
            "type": "compliance",
            "severity": "high",
            "code": "TEXT_DETECTED",
            "detail_key": "has_text_watermark",
        })

    # Resolution issues
    if not result.resolution_ok:
        issues.append({
            "type": "resolution",
            "severity": "high",
            "code": "LOW_RESOLUTION",
            "detail_key": "low_resolution",
        })

    return issues
