from PIL import Image
import imagehash

_HASH_BITS = 64  # whash produces 64-bit hash → max distance = 64


def compute_phash(image: Image.Image) -> str:
    """Compute a perceptual (wavelet) hash of an image, returned as a hex string."""
    return str(imagehash.whash(image))


def is_duplicate(current_hash: str, prev_hash: str | None, threshold: float = 0.95) -> bool:
    """Return True if the two hashes are similar enough to be considered duplicates."""
    if prev_hash is None:
        return False
    h1 = imagehash.hex_to_hash(current_hash)
    h2 = imagehash.hex_to_hash(prev_hash)
    distance = h1 - h2  # Hamming distance
    similarity = 1.0 - (distance / _HASH_BITS)
    return bool(similarity >= threshold)
