"""Tests for imgtools_m8.helpers.file_utils."""

import os

import pytest

from imgtools_m8.helpers.file_utils import FileUtils

from ..helper import HelperTest


class TestFileUtilsConvertSize:
    def test_negative_raises(self):
        with pytest.raises(ValueError):
            FileUtils.convert_size(-1)

    def test_zero(self):
        assert FileUtils.convert_size(0) == "0.00 B"

    def test_bytes(self):
        assert FileUtils.convert_size(512) == "512.00 B"

    def test_kilobytes(self):
        assert FileUtils.convert_size(1024) == "1.00 KB"

    def test_megabytes(self):
        assert FileUtils.convert_size(1024 * 1024) == "1.00 MB"


class TestFileUtilsGetFileSizeStr:
    def test_nonexistent_file(self):
        result = FileUtils.get_file_size_str("/nonexistent/path/file.jpg")
        assert result == "File not found"

    def test_existing_file(self):
        src = os.path.join(HelperTest.get_source_path(), "mar.jpg")
        result = FileUtils.get_file_size_str(src)
        assert isinstance(result, str)
        assert result != "File not found"

    def test_oserror_path(self, monkeypatch):
        src = os.path.join(HelperTest.get_source_path(), "mar.jpg")
        monkeypatch.setattr(
            "imgtools_m8.helpers.file_utils.getsize",
            lambda _: (_ for _ in ()).throw(OSError("disk error")),
        )
        result = FileUtils.get_file_size_str(src)
        assert result == "Unable to determine file size"


class TestFileUtilsReadWriteBytes:
    def test_read_existing_file(self):
        src = os.path.join(HelperTest.get_source_path(), "mar.jpg")
        data = FileUtils.read_file_as_bytes(src)
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_read_nonexistent_returns_none(self):
        result = FileUtils.read_file_as_bytes("/nonexistent/path.bin")
        assert result is None

    def test_write_and_read(self, tmp_path):
        dest = str(tmp_path / "out.bin")
        assert FileUtils.write_bytes_to_file(dest, b"hello") is True
        assert FileUtils.read_file_as_bytes(dest) == b"hello"

    def test_write_invalid_path_returns_false(self):
        result = FileUtils.write_bytes_to_file("/nonexistent/dir/file.bin", b"data")
        assert result is False
