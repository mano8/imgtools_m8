"""File-upload utilities specific to auth_user_service."""
from os import scandir
from os.path import getsize, isdir, isfile, splitext


class FilesHelper:
    """Utility helpers for file validation and scanning."""

    ALLOWED_IMG_MIME_TYPES = {"image/jpeg", "image/png", "image/gif"}
    ALLOWED_IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}
    MAX_IMG_FILE_SIZE = 2 * 1024 * 1024  # 2 MB

    @staticmethod
    def get_file_extension(filename: str) -> str:
        """Return the lowercased extension of *filename*."""
        return splitext(filename)[1].lower()

    @staticmethod
    def is_readable_path(file_path: str) -> bool:
        """Return True if *file_path* is an existing directory."""
        return isdir(file_path)

    @staticmethod
    def scan_dir(file_path: str) -> list:
        """Return names of files found directly inside *file_path*."""
        result = []
        if isdir(file_path):
            for entry in scandir(file_path):
                if isfile(entry):
                    result.append(entry.name)
        return result

    @staticmethod
    def get_path_file_sizes(file_path: str) -> int:
        """Return total size in bytes of all files directly inside *file_path*."""
        result = 0
        if isdir(file_path):
            for entry in scandir(file_path):
                if isfile(entry):
                    result += getsize(entry)
        return result
