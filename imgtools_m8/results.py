"""Storage-agnostic result types for the in-memory image API.

These types intentionally carry no database, filesystem, or service fields so
they can be reused unchanged by any consumer (SD5).
"""

from dataclasses import dataclass

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "1.0.0"


@dataclass(frozen=True)
class VariantResult:
    """A single encoded image variant produced by ``process_image``.

    Attributes:
        name: A caller-supplied label (≤64 chars) or a derived ``stem_WxH``
            label. Purely informational — not a path or storage key.
        data: The encoded image bytes.
        width: Variant width in pixels.
        height: Variant height in pixels.
        size_bytes: Length of ``data`` in bytes.
        format: Output format name (e.g. ``"JPEG"``, ``"WEBP"``).
    """

    name: str
    data: bytes
    width: int
    height: int
    size_bytes: int
    format: str
