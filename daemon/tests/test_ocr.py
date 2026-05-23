import shutil
import pytest
from PIL import Image, ImageDraw
import numpy as np
from brn_daemon.ocr import extract_text, is_text_sparse


def _blank_image() -> Image.Image:
    return Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))


def _text_image(text: str) -> Image.Image:
    img = Image.new("RGB", (400, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), text, fill=(0, 0, 0))
    return img


def test_extract_text_from_blank_returns_empty_string():
    img = _blank_image()
    result = extract_text(img)
    assert isinstance(result, str)
    assert result.strip() == "" or len(result.strip()) < 5


@pytest.mark.skipif(
    not shutil.which("tesseract"), reason="tesseract not installed"
)
def test_extract_text_from_text_image():
    img = _text_image("Hello World")
    result = extract_text(img)
    assert "Hello" in result or "World" in result


def test_is_text_sparse_true_for_empty():
    assert is_text_sparse("") is True
    assert is_text_sparse("   ") is True
    assert is_text_sparse("ab") is True


def test_is_text_sparse_false_for_content():
    assert is_text_sparse("This is a normal sentence with enough text.") is False


def test_extract_text_returns_string_type():
    img = _blank_image()
    result = extract_text(img)
    assert isinstance(result, str)
