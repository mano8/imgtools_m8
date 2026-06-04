"""
ImageToolsHelper unittest class.

Use pytest package.
"""
from os.path import join, sep
import pytest
from imgtools_m8.helpers.scan_dir import ScanDir
from ..helper import HelperTest

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "1.0.0"


class TestScanDir:
    """ScanDir unittest class."""
    @staticmethod
    def test_get_path_directory_list():
        """Test get_path_directory_list method"""
        source_path = HelperTest.get_source_path()
        result, nb_sub_dirs = ScanDir.get_path_directory_list(
            source_path=source_path,
            root=join(source_path, 'cat1')
        )
        assert isinstance(result, list)
        assert len(result) == nb_sub_dirs
        assert nb_sub_dirs == 1
        assert result[0] == 'cat1'

        result, nb_sub_dirs = ScanDir.get_path_directory_list(
            source_path=source_path,
            root=join(source_path, 'bad_dir')
        )
        assert result is None
        assert nb_sub_dirs == 0

        result, nb_sub_dirs = ScanDir.get_path_directory_list(
            source_path=source_path,
            root=source_path + sep
        )
        assert result is None
        assert nb_sub_dirs == 0

    @pytest.mark.parametrize(
        "root, img_file, expected",
        [
            (
                join(HelperTest.get_source_path(), 'bad_dir'),
                "mar.jpg",
                None
            ),
            (
                HelperTest.get_source_path(),
                "mar.exe",
                None
            ),
            (
                HelperTest.get_source_path(),
                ".private_file",
                None
            ),
            (
                HelperTest.get_source_path(),
                "a.txt",
                None
            ),
            (
                HelperTest.get_source_path(),
                "mar.jpg",
                "mar.jpg"
            ),
        ],
    )
    @staticmethod
    def test_get_file_item(root, img_file, expected):
        """Test get_file_item method"""
        result = ScanDir.get_file_item(
            root=root,
            file=img_file
        )
        assert result == expected

    @staticmethod
    def test_scan_tree():
        """Test scan_tree method"""
        source_path = HelperTest.get_source_path()
        result = []
        for root, file, dirs, nb_sub_dirs in ScanDir.scan_tree(
            source_path=source_path,
            max_depth=4
        ):
            result.append({
                'root': root,
                'file': file,
                'dirs': dirs,
                'nb_sub_dirs': nb_sub_dirs
            })
        assert isinstance(result, list)
        assert len(result) == 12

    @staticmethod
    def test_restricted_scan_tree():
        """Test scan_tree method"""
        source_path = HelperTest.get_source_path()
        result = []
        for root, file, dirs, nb_sub_dirs in ScanDir.scan_tree(
            source_path=source_path,
            max_depth=1
        ):
            result.append({
                'root': root,
                'file': file,
                'dirs': dirs,
                'nb_sub_dirs': nb_sub_dirs
            })
        assert isinstance(result, list)
        assert len(result) == 9

    @staticmethod
    def test_get_files_list_from_dir():
        """Test get_files_list_from_dir method"""
        result = ScanDir.get_files_list_from_dir(
            source_path=HelperTest.get_source_path()
        )
        assert isinstance(result, dict)
        assert isinstance(result.get('files'), list)
        assert len(result.get('files')) > 0

    @staticmethod
    def test_get_files_list_from_tree():
        """Test get_files_list_from_tree method"""
        result = ScanDir.get_files_list_from_tree(
            source_path=HelperTest.get_source_path()
        )
        assert isinstance(result, dict)
        assert isinstance(result.get('files'), list)
        assert len(result.get('files')) == 7

    @staticmethod
    def test_get_dir_files_by_format_type():
        """Test get_dir_files_by_format_type method"""
        files = ScanDir.get_files_list_from_tree(
                source_path=HelperTest.get_source_path()
            )
        files['files'][0].update({
            'image_size': None
        })
        result = ScanDir.get_dir_files_by_format_type(
            item_tree=files
        )
        assert isinstance(result, dict)
        assert isinstance(result.get('portrait'), dict)
        assert len(result.get('portrait').get('files')) == 3
        assert isinstance(result.get('landscape'), dict)
        assert len(result.get('landscape').get('files')) == 3

    @staticmethod
    def test_get_ordered_files():
        """Test get_ordered_files method"""
        result = ScanDir.get_ordered_files(
            source_path=HelperTest.get_source_path(),
            order_by='image_format'
        )
        assert isinstance(result, dict)
        assert isinstance(result.get('JPEG'), dict)
        assert isinstance(result['JPEG'].get('files'), list)
        assert len(result['JPEG'].get('files')) == 7

        result = ScanDir.get_ordered_files(
            source_path=HelperTest.get_source_path(),
            order_by='image_size'
        )
        assert isinstance(result, dict)
        assert isinstance(result.get('portrait'), dict)
        assert len(result.get('portrait').get('files')) == 4
        assert isinstance(result.get('landscape'), dict)
        assert len(result.get('landscape').get('files')) == 3

        result = ScanDir.get_ordered_files(
            source_path=HelperTest.get_source_path(),
            order_by='image_format',
            include_subdirs=False
        )
        assert isinstance(result, dict)
        assert isinstance(result.get('JPEG'), dict)
        assert isinstance(result['JPEG'].get('files'), list)
        assert len(result['JPEG'].get('files')) == 3

        result = ScanDir.get_ordered_files(
            source_path=HelperTest.get_source_path(),
            order_by='bad_order',
            include_subdirs=False
        )
        assert result is None
