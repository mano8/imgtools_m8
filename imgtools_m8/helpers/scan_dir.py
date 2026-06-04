"""
scan_dir.py

Class-based utility module for images source directory scanning.
"""

import logging
from os import listdir, walk
from os.path import isdir, isfile, join, sep
from typing import Dict, List, Optional, Tuple, cast

from imgtools_m8.helpers.file_utils import FileUtils
from imgtools_m8.helpers.image_utils import ImageUtils

logger = logging.getLogger("imgTools_m8")

# Type alias for a flat or tree file listing result
FileListing = Dict[str, object]
OrderedListing = Dict[str, Dict[str, object]]


class ScanDir:
    """Source directory scanning utility static methods."""

    @staticmethod
    def get_file_item_info(
        file_path: str, byte_size: bool = True, image_size: bool = True
    ) -> Optional[FileListing]:
        """
        Retrieve file item from directory tree.
        """
        result: Optional[FileListing] = None
        if isinstance(file_path, str):
            result = {}
            if byte_size is True:
                result["byte_size"] = FileUtils.get_file_size_str(file_path)

            info = ImageUtils.get_image_info(
                file_path, image_size=image_size, image_format=True, is_valid=True
            )
            if info is not None:
                result.update(info)

        return result

    @staticmethod
    def get_path_directory_list(
        source_path: str, root: str
    ) -> Tuple[Optional[List[str]], int]:
        """
        Retrieve directory list from source path to root.
        Args:
            source_path (str): Source directory path.
            root (str): Current directory path in the tree.
        Returns:
            Tuple[Optional[List[str]], int]: List of subdirectories and their count.
            If root is the same as source_path, returns None and 0.
        """
        result: Optional[List[str]] = None
        nb_sub_dirs = 0
        if root != source_path and isdir(root) and isdir(source_path):
            current_dir = root.replace(f"{source_path}{sep}", "")
            result = current_dir.split(sep)
            nb_sub_dirs = len(result)
            if nb_sub_dirs == 0 or (nb_sub_dirs == 1 and result[0] == ""):
                result = None
                nb_sub_dirs = 0
        return result, nb_sub_dirs

    @staticmethod
    def get_file_item(root: str, file: str) -> Optional[str]:
        """
        Retrieve file item from directory tree.
        Args:
            root (str): Root directory path.
            file (str): File name to search for.
        Returns:
            Optional[str]: File name if valid image file, None otherwise.
        """
        result = None
        if not isdir(root):
            logger.debug("Root %s is not a valid directory.", root)
            return result

        filepath = join(root, file)
        if not isfile(filepath):
            logger.debug("File %s does not exist in directory %s.", file, root)
            return result

        if file.startswith("."):
            logger.debug(
                "File %s is not a valid image file. Hidden files are not processed.",
                file,
            )
            return result

        if FileUtils.is_valid_image_file(filepath):
            result = file
        else:
            logger.debug(
                "File %s is not a valid image file. Bad format or not a file.", file
            )
        return result

    @staticmethod
    def process_valid_file_item(
        root: str,
        file: str,
        sub_dirs: Optional[List[str]] = None,
        byte_size: bool = True,
        image_size: bool = True,
    ) -> Optional[FileListing]:
        """
        Retrieve file item from directory tree.
        """
        file_item = ScanDir.get_file_item(root, file)
        if file_item is None:
            return None
        info = ScanDir.get_file_item_info(
            join(root, file), byte_size=byte_size, image_size=image_size
        )
        if info is None:  # pragma: no cover
            logger.debug(  # pragma: no cover
                "File %s is not a valid image file. Bad format or not a file.", file
            )
            return None  # pragma: no cover

        if info.get("is_valid", False) is False:
            logger.debug("File %s is corrupted image file.", file)
            return None

        file_data: FileListing = {"name": file, "sub_dirs": sub_dirs}
        file_data.update(info)
        return file_data

    @staticmethod
    def scan_tree(source_path: str, max_depth: int = 4):
        """
        Scan directory tree and yield file paths with their directories.
        Args:
            source_path (str): Source directory path to search.
            max_depth (int): Maximum depth to traverse in the directory tree.
                Defaults to 4.
                Yields:
                Tuple[str, str, List[str], int]: Tuple containing:
                - root directory path
                - file name
                - list of subdirectories from source_path to root
                - number of subdirectories
        """
        if isinstance(source_path, str) and source_path and isdir(source_path):
            for root, walk_dirs, files in walk(source_path):
                # Sort in place so directory descent and file order are
                # deterministic across filesystems (os.walk order is OS-defined).
                walk_dirs.sort()
                dirs, nb_sub_dirs = ScanDir.get_path_directory_list(
                    source_path=source_path, root=root
                )
                if nb_sub_dirs > max_depth:
                    logger.debug(
                        "Skipping directory %s, exceeds maximum depth of %d.",
                        root,
                        max_depth,
                    )
                    continue
                for file in sorted(files):
                    yield root, file, dirs, nb_sub_dirs

    @staticmethod
    def get_files_list_from_tree(
        source_path: str,
        byte_size: bool = True,
        image_size: bool = True,
        max_depth: int = 4,
    ) -> Optional[FileListing]:
        """
        Retrieve list of files from source directory tree.
        Args:
            source_path (str): Source directory path to search.
            byte_size (bool): Whether to include file byte size.
                Defaults to True.
            image_size (bool): Whether to include image size.
                Defaults to True.
            max_depth (int): Maximum depth to traverse in the directory tree.
                Defaults to 4.
            Returns:
            Optional[FileListing]: Dict with root_dir and files list, or None.
        """
        matched_files: Optional[FileListing] = None
        if isinstance(source_path, str) and source_path and isdir(source_path):
            files_list: List[FileListing] = []
            matched_files = {"root_dir": source_path, "files": files_list}
            for root, file, dirs, _ in ScanDir.scan_tree(
                source_path=source_path, max_depth=max_depth
            ):
                file_data = ScanDir.process_valid_file_item(
                    sub_dirs=dirs,
                    root=root,
                    file=file,
                    byte_size=byte_size,
                    image_size=image_size,
                )

                if file_data is None:
                    continue

                files_list.append(file_data)

        return matched_files

    @staticmethod
    def get_files_list_from_dir(
        source_path: str, byte_size: bool = False, image_size: bool = False
    ) -> Optional[FileListing]:
        """
        Retrieve list of files from directory filtered by extensions.

        Args:
            source_path (str): Directory path to search.

        Returns:
            Optional[FileListing]: Dict with root_dir and files list, or None.
        """
        matched_files: Optional[FileListing] = None
        if isinstance(source_path, str) and source_path and isdir(source_path):
            try:
                files_list: List[FileListing] = []
                matched_files = {"root_dir": source_path, "files": files_list}
                for file in listdir(source_path):
                    file_data = ScanDir.process_valid_file_item(
                        sub_dirs=None,
                        root=source_path,
                        file=file,
                        byte_size=byte_size,
                        image_size=image_size,
                    )

                    if file_data is None:
                        continue
                    files_list.append(file_data)
            except FileNotFoundError:
                return matched_files
        return matched_files

    @staticmethod
    def get_dir_files_by_format_type(
        item_tree: Optional[FileListing],
    ) -> Optional[OrderedListing]:
        """
        Retrieve files from item tree grouped by image format type.
        Args:
            item_tree (Optional[FileListing]): Item tree containing files and directory info.
        Returns:
            Optional[OrderedListing]: Dictionary with image format types as keys and
        """
        result: Optional[OrderedListing] = None
        if not isinstance(item_tree, dict):
            return result
        files = item_tree.get("files")
        if not isinstance(files, list):
            return result
        result = {}
        keys_size = ["portrait", "landscape", "square"]
        for file in files:
            if not isinstance(file, dict):
                continue

            format_size = ImageUtils.get_image_format_type(file.get("image_size"))
            if format_size is None or format_size not in keys_size:
                continue

            file_copy = file.copy()

            if format_size in result:
                files_bucket = cast(
                    List[FileListing], result[format_size]["files"]
                )
                files_bucket.append(file_copy)
            else:
                result[format_size] = {
                    "root_dir": item_tree.get("root_dir"),
                    "files": [file_copy],
                }
        return result

    @staticmethod
    def get_dir_files_by_ext(
        item_tree: Optional[FileListing],
    ) -> Optional[OrderedListing]:
        """
        Retrieve files from item tree grouped by file extensions.
        """
        result: Optional[OrderedListing] = None
        if not isinstance(item_tree, dict):
            return result
        files = item_tree.get("files")
        if not isinstance(files, list):
            return result
        result = {}
        for file in files:
            if not isinstance(file, dict):
                continue

            ext = file.get("image_format")
            if not isinstance(ext, str):
                continue

            file_copy = file.copy()

            if ext in result:
                files_bucket = cast(List[FileListing], result[ext]["files"])
                files_bucket.append(file_copy)
            else:
                result[ext] = {
                    "root_dir": item_tree.get("root_dir"),
                    "files": [file_copy],
                }
        return result

    @staticmethod
    def get_ordered_dir_files(
        item_tree: Optional[FileListing], order_by: str = "image_format"
    ) -> Optional[OrderedListing]:
        """
        Retrieve files from directory tree ordered by file extensions or
        image format type.
        Args:
            item_tree (Optional[FileListing]): Item tree containing files and directory info.
            order_by (str): Criteria to order files ('image_size' or
                'image_format').
                Returns:
                Optional[OrderedListing]: Dictionary with ordered files based on criteria.
        """
        if order_by == "image_format":
            return ScanDir.get_dir_files_by_ext(item_tree)
        if order_by == "image_size":
            return ScanDir.get_dir_files_by_format_type(item_tree)
        return None

    @staticmethod
    def get_ordered_files(
        source_path: str,
        include_subdirs: bool = True,
        byte_size: bool = True,
        image_size: bool = True,
        order_by: str = "image_format",
    ) -> Optional[OrderedListing]:
        """
        Retrieve list of files from directory filtered by extensions.

        Args:
            source_path (str): Directory path to search.
            include_subdirs (bool): Whether to include files in subdirectories.

        Returns:
            Optional[OrderedListing]: Ordered files dict or None.
        """
        if include_subdirs is True:
            files = ScanDir.get_files_list_from_tree(
                source_path=source_path, byte_size=byte_size, image_size=image_size
            )
        else:
            files = ScanDir.get_files_list_from_dir(
                source_path=source_path, byte_size=byte_size, image_size=image_size
            )
        if files is None:
            return None
        return ScanDir.get_ordered_dir_files(item_tree=files, order_by=order_by)
