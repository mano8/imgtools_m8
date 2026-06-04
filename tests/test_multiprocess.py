"""
MultiProcessImage unittest class.

Use pytest package.
"""
import os

from imgtools_m8.multiprocess import MultiProcessImage

from .helper import HelperTest

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "2.0.0"


def _make_obj(source_path: str) -> MultiProcessImage:
    """Build a MultiProcessImage with a single JPEG output option."""
    return MultiProcessImage(
        conf={
            "source_path": source_path,
            "output_path": HelperTest.get_output_path(),
            "output_options": [
                {
                    "image_size": {"fixed_width": 35, "fixed_height": 22},
                    "formats": [{"ext": "JPEG", "quality": 80}],
                }
            ],
        },
        use_progress=False,
    )


class TestMultiProcessImage:
    """MultiProcessImage unittest class."""

    def test_run_multiple_valid_source(self):
        """Processing a directory of valid images returns True."""
        obj = _make_obj(
            source_path=os.path.join(HelperTest.get_source_path(), "good")
        )
        assert obj.run_multiple() is True

    def test_run_multiple_no_images(self):
        """Processing a non-existent source directory returns False."""
        obj = _make_obj(source_path="/nonexistent/path")
        assert obj.run_multiple() is False

    def test_collect_file_tasks_valid_source(self):
        """Tasks are collected for valid image directories."""
        obj = _make_obj(
            source_path=os.path.join(HelperTest.get_source_path(), "good")
        )
        tasks = obj._collect_file_tasks()
        assert isinstance(tasks, list)
        assert len(tasks) >= 1

    def test_collect_file_tasks_invalid_source(self):
        """Empty task list for non-existent source."""
        obj = _make_obj(source_path="/nonexistent/path")
        assert obj._collect_file_tasks() == []
