import imagehash
from PIL import Image


def compute_phash(image: Image.Image) -> str:
    """Compute a perceptual (wavelet) hash of an image, returned as a hex string."""
    return str(imagehash.whash(image))


def is_duplicate(current_hash: str, prev_hash: str | None, threshold: float = 0.95) -> bool:
    """Return True if the two hashes are similar enough to be considered duplicates."""
    if prev_hash is None:
        return False
    h1 = imagehash.hex_to_hash(current_hash)
    h2 = imagehash.hex_to_hash(prev_hash)
    hash_bits = len(current_hash) * 4
    distance = h1 - h2
    similarity = 1.0 - (distance / hash_bits)
    return bool(similarity >= threshold)
