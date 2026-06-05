"""
model_downloader unittest class (no network — urllib mocked).

Use pytest package.
"""

import hashlib
import os
from urllib.error import URLError

import pytest

from imgtools_m8.helpers import model_downloader as md
from imgtools_m8.helpers.model_downloader import MODEL_REGISTRY

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "2.0.0"


class _FakeResponse:
    """Minimal context-manager stand-in for urlopen's response."""

    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        chunk, self._data = self._data[:size], self._data[size:]
        return chunk


def _patch_urlopen(monkeypatch, data: bytes) -> None:
    """Patch urlopen to stream `data` without touching the network."""
    monkeypatch.setattr(md, "urlopen", lambda url, timeout=0: _FakeResponse(data))


# ---------------------------------------------------------------------------
# download_model
# ---------------------------------------------------------------------------


class TestDownloadModel:
    def test_success_writes_and_verifies(self, tmp_path, monkeypatch):
        data = b"super-resolution-model-bytes" * 4096
        digest = hashlib.sha256(data).hexdigest()
        _patch_urlopen(monkeypatch, data)
        dest = md.download_model("EDSR_x2.pb", digest, str(tmp_path))
        assert dest == os.path.join(str(tmp_path), "EDSR_x2.pb")
        with open(dest, "rb") as handle:
            assert handle.read() == data
        assert not os.path.isfile(dest + ".tmp")

    def test_sha_mismatch_raises_and_cleans_tmp(self, tmp_path, monkeypatch):
        _patch_urlopen(monkeypatch, b"corrupt")
        with pytest.raises(ValueError, match="SHA256 mismatch"):
            md.download_model("EDSR_x2.pb", "deadbeef", str(tmp_path))
        assert not os.path.isfile(str(tmp_path / "EDSR_x2.pb.tmp"))
        assert not os.path.isfile(str(tmp_path / "EDSR_x2.pb"))

    def test_network_error_reraises_no_tmp(self, tmp_path, monkeypatch):
        def _boom(url, timeout=0):
            raise URLError("offline")

        monkeypatch.setattr(md, "urlopen", _boom)
        with pytest.raises(URLError):
            md.download_model("EDSR_x2.pb", "x", str(tmp_path))
        assert not os.path.isfile(str(tmp_path / "EDSR_x2.pb.tmp"))

    def test_cache_hit_skips_download(self, tmp_path, monkeypatch):
        dest = tmp_path / "EDSR_x2.pb"
        dest.write_bytes(b"cached")

        def _never(url, timeout=0):  # pragma: no cover
            raise AssertionError("download must be skipped on cache hit")

        monkeypatch.setattr(md, "urlopen", _never)
        result = md.download_model("EDSR_x2.pb", "ignored", str(tmp_path))
        assert result == str(dest)

    def test_non_https_url_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(md, "BASE_URL", "http://example.com/insecure")
        with pytest.raises(ValueError, match="non-https"):
            md.download_model("EDSR_x2.pb", "x", str(tmp_path))


# ---------------------------------------------------------------------------
# get_dest_dir / registry
# ---------------------------------------------------------------------------


class TestDestDirAndRegistry:
    def test_get_dest_dir_delegates_to_resolver(self, tmp_path, monkeypatch):
        monkeypatch.setenv("IMGTOOLS_M8_MODELS_DIR", str(tmp_path))
        assert md.get_dest_dir("opencv") == os.path.join(str(tmp_path), "opencv")

    def test_registry_consistency(self):
        assert set(MODEL_REGISTRY) == {"opencv"}
        edsr = MODEL_REGISTRY["opencv"]["edsr"]
        assert {e["filename"] for e in edsr} == {
            "EDSR_x2.pb",
            "EDSR_x3.pb",
            "EDSR_x4.pb",
        }
        for entry in edsr:
            assert set(entry) == {"filename", "sha256"}
            assert entry["sha256"].startswith("TODO_SHA256_")
