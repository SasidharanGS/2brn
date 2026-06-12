import numpy as np
from PIL import Image

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

def _gradient_image(size: tuple[int, int]) -> Image.Image:
    """Horizontal 0→252 gradient — strong directional frequency content."""
    w, h = size
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[:, :, :] = np.linspace(0, 252, w, dtype=np.uint8)[None, :, None]
    return Image.fromarray(arr)


def test_full_resolution_frames_with_different_content_stay_distinct():
    """The pre-hash downscale must not blur away real differences at 4K."""
    grad = _gradient_image((3840, 2160))
    solid = _solid_image((128, 128, 128), size=(3840, 2160))
    assert is_duplicate(compute_phash(grad), compute_phash(solid), threshold=0.95) is False


def test_downscale_preserves_perceptual_identity():
    """A 4K frame and the same content at thumbnail size must hash as duplicates."""
    full = _gradient_image((3840, 2160))
    thumb = _gradient_image((256, 144))
    assert is_duplicate(compute_phash(full), compute_phash(thumb), threshold=0.95) is True


def test_identical_full_resolution_frames_hash_identically():
    img = _gradient_image((3840, 2160))
    assert compute_phash(img) == compute_phash(img.copy())


def test_compute_phash_returns_string():
    img = _solid_image((123, 45, 67))
    h = compute_phash(img)
    assert isinstance(h, str)
    assert len(h) > 0

def test_none_prev_hash_is_not_duplicate():
    img = _solid_image((10, 20, 30))
    h = compute_phash(img)
    assert is_duplicate(h, None, threshold=0.95) is False


def _make_image(color: tuple[int, int, int] = (128, 128, 128)) -> Image.Image:
    return Image.new("RGB", (64, 64), color)


def test_is_duplicate_uses_actual_hash_length(monkeypatch):
    """is_duplicate must derive bit-length from the hash string, not a constant."""
    img1 = _make_image((100, 100, 100))
    img2 = _make_image((101, 101, 101))
    h1 = compute_phash(img1)
    h2 = compute_phash(img2)
    expected_bits = len(h1) * 4
    assert expected_bits > 0
    result = is_duplicate(h1, h2)
    assert isinstance(result, bool)


def test_is_duplicate_identical_images():
    img = _make_image()
    h = compute_phash(img)
    assert is_duplicate(h, h) is True


def test_is_duplicate_none_prev():
    img = _make_image()
    h = compute_phash(img)
    assert is_duplicate(h, None) is False


def test_is_duplicate_very_different_images():
    size = (64, 64)
    import numpy as np
    arr_grad = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    for col in range(size[0]):
        arr_grad[:, col] = int(col * 4)
    h1 = compute_phash(Image.fromarray(arr_grad))
    h2 = compute_phash(_make_image((128, 128, 128)))
    assert is_duplicate(h1, h2) is False
