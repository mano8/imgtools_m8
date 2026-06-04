"""
scan_dir.py

Class-based utility module for images source directory scanning.
"""

import logging
from os import listdir, walk
from os.path import isdir, isfile, join, sep
from typing import List, Optional, Tuple

from imgtools_m8.helpers.file_utils import FileUtils
from imgtools_m8.helpers.image_utils import ImageUtils

logger = logging.getLogger("imgTools_m8")


class ScanDir:
    """Source directory scanning utility static methods."""

    @staticmethod
    def get_file_item_info(
        file_path: str,
        byte_size: bool = True,
        image_size: bool = True
    ) -> List[str]:
        """
        Retrieve file item from directory tree.
        """
        result = None
        if isinstance(file_path, str):
            result = {}
            if byte_size is True:
                result['byte_size'] = FileUtils.get_file_size_str(
                    file_path)

            info = ImageUtils.get_image_info(
                file_path,
                image_size=image_size,
                image_format=True,
                is_valid=True
            )
            if info is not None:
                result.update(info)

        return result

    @staticmethod
    def get_path_directory_list(
        source_path: str,
        root: str
    ) -> Tuple[List[str], int]:
        """
        Retrieve directory list from source path to root.
        Args:
            source_path (str): Source directory path.
            root (str): Current directory path in the tree.
        Returns:
            Tuple[List[str], int]: List of subdirectories and their count.
            If root is the same as source_path, returns None and 0.
        """
        result, nb_sub_dirs = None, 0
        if root != source_path\
                and isdir(root)\
                and isdir(source_path):
            current_dir = root.replace(f"{source_path}{sep}", "")
            result = current_dir.split(sep)
            nb_sub_dirs = len(result)
            if nb_sub_dirs == 0\
                    or (nb_sub_dirs == 1 and result[0] == ""):
                result = None
                nb_sub_dirs = 0
        return result, nb_sub_dirs

    @staticmethod
    def get_file_item(
        root: str,
        file: str
    ) -> Optional[str]:
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
            logger.debug(
                "Root %s is not a valid directory.",
                root
            )
            return result

        filepath = join(root, file)
        if not isfile(filepath):
            logger.debug(
                "File %s does not exist in directory %s.",
                file, root
            )
            return result

        if file.startswith("."):
            logger.debug(
                "File %s is not a valid image file. "
                "Hidden files are not processed.",
                file
            )
            return result

        if FileUtils.is_valid_image_file(
                filepath):
            result = file
        else:
            logger.debug(
                "File %s is not a valid image file. "
                "Bad format or not a file.",
                file
            )
        return result

    @staticmethod
    def process_valid_file_item(
        root: str,
        file: str,
        sub_dirs: Optional[List[str]] = None,
        byte_size: bool = True,
        image_size: bool = True
    ) -> List[str]:
        """
        Retrieve file item from directory tree.
        """
        file_item = ScanDir.get_file_item(root, file)
        if file_item is None:
            return None
        info = ScanDir.get_file_item_info(
            join(root, file),
            byte_size=byte_size,
            image_size=image_size
        )
        if info is None:
            logger.debug(
                "File %s is not a valid image file. "
                "Bad format or not a file.",
                file
            )
            return None

        if info.get('is_valid', False) is False:
            logger.debug(
                "File %s is corrupted image file.",
                file
            )
            return None

        file_data = {
            "name": file,
            "sub_dirs": sub_dirs
        }

        file_data.update(info)
        return file_data

    @staticmethod
    def scan_tree(
        source_path: str,
        max_depth: int = 4
    ):
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
        if isinstance(source_path, str) and source_path \
                and isdir(source_path):
            for root, _, files in walk(source_path):
                dirs, nb_sub_dirs = ScanDir.get_path_directory_list(
                    source_path=source_path,
                    root=root
                )
                if nb_sub_dirs > max_depth:
                    logger.debug(
                        "Skipping directory %s, "
                        "exceeds maximum depth of %d.",
                        root, max_depth
                    )
                    continue
                for file in files:
                    yield root, file, dirs, nb_sub_dirs

    @staticmethod
    def get_files_list_from_tree(
        source_path: str,
        byte_size: bool = True,
        image_size: bool = True,
        max_depth: int = 4
    ) -> List[str]:
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
            List[str]: List of file paths matching criteria.
        """
        matched_files = None
        if isinstance(source_path, str) and source_path \
                and isdir(source_path):
            matched_files = {
                "root_dir": source_path,
                "files": []
            }
            for root, file, dirs, _ in ScanDir.scan_tree(
                source_path=source_path,
                max_depth=max_depth
            ):
                file_data = ScanDir.process_valid_file_item(
                    sub_dirs=dirs,
                    root=root,
                    file=file,
                    byte_size=byte_size,
                    image_size=image_size
                )

                if file_data is None:
                    continue

                matched_files['files'].append(file_data)

        return matched_files

    @staticmethod
    def get_files_list_from_dir(
        source_path: str,
        byte_size: bool = False,
        image_size: bool = False
    ) -> List[str]:
        """
        Retrieve list of files from directory filtered by extensions.

        Args:
            directory (str): Directory path to search.

        Returns:
            List[str]: List of file paths matching criteria.
        """
        matched_files = None
        if isinstance(source_path, str) and source_path \
                and isdir(source_path):
            try:
                matched_files = {
                    "root_dir": source_path,
                    "files": []
                }
                for file in listdir(source_path):
                    file_data = ScanDir.process_valid_file_item(
                        sub_dirs=None,
                        root=source_path,
                        file=file,
                        byte_size=byte_size,
                        image_size=image_size
                    )

                    if file_data is None:
                        continue
                    matched_files['files'].append(file_data)
            except FileNotFoundError:
                return matched_files
        return matched_files

    @staticmethod
    def get_dir_files_by_format_type(
        item_tree: dict
    ) -> List[str]:
        """
        Retrieve files from item tree grouped by image format type.
        Args:
            item_tree (dict): Item tree containing files and directory info.
        Returns:
            List[str]: Dictionary with image format types as keys and
        """
        result = None
        if isinstance(item_tree, dict)\
                and isinstance(item_tree.get('files'), list):
            result = {}
            keys_size = ['portrait', 'landscape', 'square']
            for file in item_tree.get('files'):
                format_size = ImageUtils.get_image_format_type(
                    file.pop('image_size'))
                if format_size is None\
                        or format_size not in keys_size:
                    continue
                if format_size in result:
                    result[format_size]["files"].append(file)
                else:
                    result[format_size] = {
                        "root_dir": item_tree.get('root_dir'),
                        "files": [file]
                    }
        return result

    @staticmethod
    def get_dir_files_by_ext(
        item_tree: dict
    ) -> List[str]:
        """
        Retrieve files from item tree grouped by file extensions.
        """
        result = None
        if isinstance(item_tree, dict)\
                and isinstance(item_tree.get('files'), list):
            result = {}
            for file in item_tree.get('files'):
                ext = file.pop('image_format')
                if ext in result:
                    result[ext]["files"].append(file)
                else:
                    result[ext] = {
                        "root_dir": item_tree.get('root_dir'),
                        "files": [file]
                    }
        return result

    @staticmethod
    def get_ordered_dir_files(
        item_tree: dict,
        order_by: str = 'image_format'
    ) -> List[str]:
        """
        Retrieve files from directory tree ordered by file extensions or
        image format type.
        Args:
            item_tree (dict): Item tree containing files and directory info.
            order_by (str): Criteria to order files ('image_size' or
                'image_format').
                Returns:
                List[str]: Dictionary with ordered files based on criteria.
        """
        result = None
        if order_by == 'image_format':
            result = ScanDir.get_dir_files_by_ext(item_tree)
        elif order_by == 'image_size':
            result = ScanDir.get_dir_files_by_format_type(item_tree)
        else:
            result = None
        return result

    @staticmethod
    def get_ordered_files(
        source_path: str,
        include_subdirs: bool = True,
        byte_size: bool = True,
        image_size: bool = True,
        order_by: str = 'image_format'
    ) -> List[str]:
        """
        Retrieve list of files from directory filtered by extensions.

        Args:
            source_path (str): Directory path to search.
            include_subdirs (bool): Whether to include files in subdirectories.

        Returns:
            List[str]: List of file paths matching criteria.
        """
        result = None
        if include_subdirs is True:
            files = ScanDir.get_files_list_from_tree(
                source_path=source_path,
                byte_size=byte_size,
                image_size=image_size
            )
        else:
            files = ScanDir.get_files_list_from_dir(
                source_path=source_path,
                byte_size=byte_size,
                image_size=image_size
            )
        result = ScanDir.get_ordered_dir_files(
            item_tree=files,
            order_by=order_by
        )
        return result
