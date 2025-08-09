"""
imgtools_m8.core.constants module.
"""
# accepted img formats
from enum import Enum


VALID_IMAGE_EXTENSIONS = {
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tiff",
    ".webp",
}

# Formats that support transparency
TRANSPARENT_FORMATS = {".png", ".webp", ".gif", ".tiff"}


class OutputFormatsEnum(str, Enum):
    """Enumeration of supported output formats."""
    JPEG = "JPEG"
    WEBP = "WEBP"
    PNG = "PNG"
    GIF = "GIF"
    AVIF = "AVIF"
