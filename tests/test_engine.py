import pytest
import cv2
import numpy as np
from app.cv_engine import analyze_photo

def test_pure_white_bg():
    img = np.full((500, 500, 3), 255, dtype=np.uint8)
    cv2.circle(img, (250, 250), 100, (0, 0, 0), -1)
    res = analyze_photo(img, "amazon")
    assert res.background.score > 20

def test_black_image():
    img = np.zeros((500, 500, 3), dtype=np.uint8)
    res = analyze_photo(img, "amazon")
    assert any(i['code'] == 'TOO_DARK' for i in res.issues)

def test_blurry_image():
    img = np.full((500, 500, 3), 128, dtype=np.uint8)
    res = analyze_photo(img, "amazon")
    assert any(i['code'] == 'BLURRY' for i in res.issues)

def test_product_too_small():
    img = np.full((1000, 1000, 3), 255, dtype=np.uint8)
    cv2.circle(img, (500, 500), 10, (0, 0, 0), -1)
    res = analyze_photo(img, "amazon")
    assert any(i['code'] == 'PRODUCT_TOO_SMALL' for i in res.issues)
