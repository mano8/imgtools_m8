"""
Secure model downloader for imgtools_m8 (CLI / utility only).

This module is the ONLY place that performs network downloads; the library
itself never downloads. Downloads are pinned to a release tag, streamed to a
temp file, SHA256-verified, then atomically moved into place.
"""

import hashlib
import os
from urllib.error import URLError
from urllib.request import urlopen

from imgtools_m8.helper import ImageToolsHelper

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "2.0.0"

RELEASE_TAG = "v2.0.0"
BASE_URL = f"https://github.com/mano8/imgtools_m8/releases/download/{RELEASE_TAG}"

# Real SHA256 digests are filled in Phase C2 (Sonnet); placeholders for now.
MODEL_REGISTRY: dict[str, dict[str, list[dict[str, str]]]] = {
    "opencv": {
        "edsr": [
            {
                "filename": "EDSR_x2.pb",
                "sha256": "585623221baa070279a0d1e7e113a4c3faba0f318ca7fdd9a65d9afc0763d9b4",
            },
            {
                "filename": "EDSR_x3.pb",
                "sha256": "3baa3740fdb8ee9c52f1a41d69fa74cb9feef0fa9bfeec24f0ee58b928068e9a",
            },
            {
                "filename": "EDSR_x4.pb",
                "sha256": "dd35ce3cae53ecee2d16045e08a932c3e7242d641bb65cb971d123e06904347f",
            },
        ],
    },
}

_CHUNK = 64 * 1024


def get_dest_dir(backend: str = "opencv") -> str:
    """
    Resolve the destination models directory for a backend.

    Delegates to the single-source path resolver (no duplicate path logic).

    :param backend: Backend sub-directory (e.g. ``"opencv"``).
    :type backend: str

    :return: Absolute path to the backend models directory.
    :rtype: str
    """
    return ImageToolsHelper.get_default_models_path(backend)


def _sha256(path: str) -> str:
    """
    Compute the SHA256 hex digest of a file, streamed in chunks.

    :param path: Path to the file to hash.
    :type path: str

    :return: The hex-encoded SHA256 digest.
    :rtype: str
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_model(filename: str, sha256: str, dest_dir: str) -> str:
    """
    Download and verify a single model file into ``dest_dir``.

    Streams a single pinned HTTPS request to ``{dest}.tmp`` in 64 KiB chunks,
    verifies its SHA256, then atomically replaces the destination. A cache hit
    (file already present) short-circuits the download.

    :param filename: Release asset filename (e.g. ``"EDSR_x2.pb"``).
    :type filename: str
    :param sha256: Expected SHA256 hex digest of the file.
    :type sha256: str
    :param dest_dir: Directory to place the verified file in.
    :type dest_dir: str

    :return: Absolute path to the downloaded (or cached) file.
    :rtype: str

    :raises ValueError: If the URL is not https or the digest mismatches.
    :raises URLError: On network failure.
    :raises OSError: On filesystem failure.
    """
    dest = os.path.join(dest_dir, filename)
    if os.path.isfile(dest):
        return dest

    url = f"{BASE_URL}/{filename}"
    if not url.startswith("https://"):
        raise ValueError(f"Refusing non-https model URL: {url!r}")

    os.makedirs(dest_dir, exist_ok=True)
    tmp = f"{dest}.tmp"
    try:
        with (
            urlopen(url, timeout=60) as response,  # nosec B310 — https asserted above
            open(tmp, "wb") as handle,
        ):
            for chunk in iter(lambda: response.read(_CHUNK), b""):
                handle.write(chunk)
        actual = _sha256(tmp)
        if actual != sha256:
            raise ValueError(
                f"SHA256 mismatch for {filename}: expected {sha256}, got {actual}"
            )
        os.replace(tmp, dest)
    except (URLError, OSError, ValueError):
        if os.path.isfile(tmp):
            os.unlink(tmp)
        raise
    return dest
