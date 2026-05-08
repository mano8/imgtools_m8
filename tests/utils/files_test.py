"""Unit tests for utils.files.FilesHelper."""

import os
import tempfile

import pytest

from auth_user_service.utils.files import FilesHelper


class TestGetFileExtension:
    def test_jpg(self):
        assert FilesHelper.get_file_extension("photo.jpg") == ".jpg"

    def test_jpeg(self):
        assert FilesHelper.get_file_extension("photo.JPEG") == ".jpeg"

    def test_png(self):
        assert FilesHelper.get_file_extension("image.PNG") == ".png"

    def test_gif(self):
        assert FilesHelper.get_file_extension("anim.GIF") == ".gif"

    def test_no_extension(self):
        assert FilesHelper.get_file_extension("noext") == ""

    def test_multiple_dots(self):
        assert FilesHelper.get_file_extension("archive.tar.gz") == ".gz"

    def test_hidden_file_no_ext(self):
        assert FilesHelper.get_file_extension(".gitignore") == ""


class TestIsReadablePath:
    def test_existing_directory_returns_true(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assert FilesHelper.is_readable_path(tmpdir) is True

    def test_file_path_returns_false(self):
        with tempfile.NamedTemporaryFile() as tmp:
            assert FilesHelper.is_readable_path(tmp.name) is False

    def test_nonexistent_path_returns_false(self):
        assert FilesHelper.is_readable_path("/nonexistent/path/xyz") is False


class TestScanDir:
    def test_returns_file_names_in_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path1 = os.path.join(tmpdir, "file1.txt")
            path2 = os.path.join(tmpdir, "file2.png")
            open(path1, "w").close()
            open(path2, "w").close()

            result = FilesHelper.scan_dir(tmpdir)

        assert sorted(result) == ["file1.txt", "file2.png"]

    def test_excludes_subdirectories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "subdir")
            os.makedirs(subdir)
            filepath = os.path.join(tmpdir, "file.txt")
            open(filepath, "w").close()

            result = FilesHelper.scan_dir(tmpdir)

        assert result == ["file.txt"]

    def test_empty_directory_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = FilesHelper.scan_dir(tmpdir)

        assert result == []

    def test_nonexistent_path_returns_empty_list(self):
        result = FilesHelper.scan_dir("/nonexistent/path/xyz")
        assert result == []

    def test_file_path_returns_empty_list(self):
        with tempfile.NamedTemporaryFile() as tmp:
            result = FilesHelper.scan_dir(tmp.name)
        assert result == []


class TestGetPathFileSizes:
    def test_sums_file_sizes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path1 = os.path.join(tmpdir, "a.txt")
            path2 = os.path.join(tmpdir, "b.txt")
            with open(path1, "w") as f:
                f.write("hello")  # 5 bytes
            with open(path2, "w") as f:
                f.write("world!")  # 6 bytes

            result = FilesHelper.get_path_file_sizes(tmpdir)

        assert result == 11

    def test_excludes_subdirectory_sizes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "sub")
            os.makedirs(subdir)
            subfile = os.path.join(subdir, "nested.txt")
            with open(subfile, "w") as f:
                f.write("nested content")

            topfile = os.path.join(tmpdir, "top.txt")
            with open(topfile, "w") as f:
                f.write("top")  # 3 bytes

            result = FilesHelper.get_path_file_sizes(tmpdir)

        assert result == 3

    def test_empty_directory_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = FilesHelper.get_path_file_sizes(tmpdir)

        assert result == 0

    def test_nonexistent_path_returns_zero(self):
        result = FilesHelper.get_path_file_sizes("/nonexistent/path/xyz")
        assert result == 0

    def test_file_path_returns_zero(self):
        with tempfile.NamedTemporaryFile() as tmp:
            result = FilesHelper.get_path_file_sizes(tmp.name)
        assert result == 0


class TestFilesHelperConstants:
    def test_allowed_mime_types(self):
        assert "image/jpeg" in FilesHelper.ALLOWED_IMG_MIME_TYPES
        assert "image/png" in FilesHelper.ALLOWED_IMG_MIME_TYPES
        assert "image/gif" in FilesHelper.ALLOWED_IMG_MIME_TYPES

    def test_allowed_extensions(self):
        assert ".jpg" in FilesHelper.ALLOWED_IMG_EXTENSIONS
        assert ".jpeg" in FilesHelper.ALLOWED_IMG_EXTENSIONS
        assert ".png" in FilesHelper.ALLOWED_IMG_EXTENSIONS
        assert ".gif" in FilesHelper.ALLOWED_IMG_EXTENSIONS

    def test_max_file_size_is_2mb(self):
        assert FilesHelper.MAX_IMG_FILE_SIZE == 2 * 1024 * 1024
