from PIL import Image
import pytesseract
import logging
import os
import shutil

from PIL import Image
import pytesseract
import logging
import os
import shutil

logger = logging.getLogger(__name__)

# When spawned by Electron or launchd without a full shell PATH,
# /opt/homebrew/bin is missing. Inject well-known Homebrew dirs into
# os.environ['PATH'] so that both shutil.which and every subprocess
# spawned from this process (including pytesseract's tesseract call,
# which passes env=os.environ) can locate the tesseract binary.
_EXTRA_DIRS = ['/opt/homebrew/bin', '/opt/homebrew/sbin', '/usr/local/bin']
_current_path = os.environ.get('PATH', '')
_missing = [d for d in _EXTRA_DIRS if d not in _current_path and os.path.isdir(d)]
if _missing:
    os.environ['PATH'] = ':'.join(_missing) + ':' + _current_path

_tesseract_bin = shutil.which('tesseract')
if _tesseract_bin:
    pytesseract.pytesseract.tesseract_cmd = _tesseract_bin
    logger.info("tesseract binary resolved: %s", _tesseract_bin)
else:
    logger.warning("tesseract binary not found; OCR will be unavailable")


def extract_text(image: Image.Image) -> str:
    try:
        text = pytesseract.image_to_string(image, timeout=10)
        return text.strip()
    except RuntimeError as exc:
        # pytesseract raises RuntimeError on timeout
        logger.warning("OCR timed out — returning empty text: %s", exc)
        return ""
    except Exception as exc:
        logger.warning("OCR failed: %s", exc)
        return ""


def is_text_sparse(text: str, min_chars: int = 20) -> bool:
    return len(text.strip()) < min_chars
