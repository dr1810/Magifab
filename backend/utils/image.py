"""Safe base64 image decoding shared by perception endpoints."""
import base64
import binascii
import io

from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError

from config import Settings


def decode_base64_image(encoded: str, settings: Settings) -> Image.Image:
    """Decode a base64 image into RGB Pillow data with bounded resource use."""
    payload = encoded.split(",", 1)[1] if encoded.startswith("data:") and "," in encoded else encoded
    try:
        raw = base64.b64decode(payload, validate=True)
    except (ValueError, binascii.Error) as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="image must be valid base64") from error
    if len(raw) > settings.max_image_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="image exceeds the configured size limit")
    try:
        with Image.open(io.BytesIO(raw)) as candidate:
            candidate.verify()
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    except (UnidentifiedImageError, OSError) as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="image data is not a supported image") from error
    if image.width > settings.max_image_dimension or image.height > settings.max_image_dimension:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="image dimensions exceed the configured limit")
    return image
