import pytest
from PIL import Image
import numpy as np
from brn_daemon.dedup import compute_phash, is_duplicate

def _solid_image(color: tuple, size=(100, 100)) -> Image.Image:
    arr = np.full((size[1], size[0], 3), color, dtype=np.uint8)
    return Image.fromarray(arr)

def test_identical_images_are_duplicate():
    img = _solid_image((100, 149, 200))
    h = compute_phash(img)
    assert is_duplicate(h, h, threshold=0.95) is True

def test_very_different_images_are_not_duplicate():
    # Solid uniform images produce near-identical hashes because whash finds
    # no frequency content in flat signals. Use a strong horizontal gradient
    # vs a mid-grey solid — the gradient has clear directional frequency content
    # that survives rescaling and produces a distinct hash on all platforms.
    size = (64, 64)
    arr_grad = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    for col in range(size[0]):
        arr_grad[:, col] = int(col * 4)  # 0 → 252 left-to-right
    img_a = Image.fromarray(arr_grad)
    img_b = _solid_image((128, 128, 128), size=size)
    h_a = compute_phash(img_a)
    h_b = compute_phash(img_b)
    assert is_duplicate(h_a, h_b, threshold=0.95) is False

def test_slightly_different_images_are_not_duplicate():
    img_a = _solid_image((100, 100, 100))
    arr = np.full((100, 100, 3), (100, 100, 100), dtype=np.uint8)
    arr[0:30, 0:30] = (200, 50, 10)
    img_b = Image.fromarray(arr)
    h_a = compute_phash(img_a)
    h_b = compute_phash(img_b)
    assert is_duplicate(h_a, h_b, threshold=0.95) is False

def test_compute_phash_returns_string():
    img = _solid_image((123, 45, 67))
    h = compute_phash(img)
    assert isinstance(h, str)
    assert len(h) > 0

def test_none_prev_hash_is_not_duplicate():
    img = _solid_image((10, 20, 30))
    h = compute_phash(img)
    assert is_duplicate(h, None, threshold=0.95) is False
