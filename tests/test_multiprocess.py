"""
MultiProcessImage unittest class.

Use pytest package.
"""

import os

from imgtools_m8.multiprocess import (
    MultiProcessImage,
    _init_worker,
    _process_one_file,
)

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

    def test_run_multiple_valid_source(self, monkeypatch):
        """run_multiple returns True when pool processes all tasks successfully.

        Monkeypatches multiprocessing.Pool so no subprocesses are spawned —
        real Pool startup forks OpenCV-imported threads and deadlocks in
        container CI environments.
        """
        import multiprocessing as mp_mod

        class _AllOkPool:
            def __init__(self, *a, **kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def terminate(self):
                pass

            def starmap(self, func, tasks):
                return [True] * len(tasks)

        monkeypatch.setattr(mp_mod, "Pool", _AllOkPool)
        obj = _make_obj(source_path=os.path.join(HelperTest.get_source_path(), "good"))
        assert obj.run_multiple() is True

    def test_run_multiple_no_images(self):
        """Processing a non-existent source directory returns False."""
        obj = _make_obj(source_path="/nonexistent/path")
        assert obj.run_multiple() is False

    def test_collect_file_tasks_valid_source(self):
        """Tasks are collected for valid image directories."""
        obj = _make_obj(source_path=os.path.join(HelperTest.get_source_path(), "good"))
        tasks = obj._collect_file_tasks()
        assert isinstance(tasks, list)
        assert len(tasks) >= 1

    def test_collect_file_tasks_invalid_source(self):
        """Empty task list for non-existent source."""
        obj = _make_obj(source_path="/nonexistent/path")
        assert obj._collect_file_tasks() == []

    def test_collect_file_tasks_with_subdirs(self):
        """Tasks include files from subdirectories."""
        obj = MultiProcessImage(
            conf={
                "source_path": HelperTest.get_source_path(),
                "output_path": HelperTest.get_output_path(),
                "include_subdirs": True,
                "output_options": [{"formats": [{"ext": "JPEG", "quality": 80}]}],
            },
            use_progress=False,
        )
        tasks = obj._collect_file_tasks()
        assert len(tasks) > 1
        # At least one task should have a path containing a subdir
        has_subdir = any(
            os.sep in os.path.relpath(path, HelperTest.get_source_path())
            for path, _ in tasks
        )
        assert has_subdir


class TestWorkerFunctions:
    """Tests for module-level worker functions."""

    def test_process_one_file_no_worker(self):
        """Returns False when _worker_processor is None."""
        import imgtools_m8.multiprocess as mp_mod

        original = mp_mod._worker_processor
        mp_mod._worker_processor = None
        try:
            result = _process_one_file("/any/path.jpg", {"name": "path.jpg"})
            assert result is False
        finally:
            mp_mod._worker_processor = original

    def test_init_worker_sets_processor(self):
        """_init_worker sets the global _worker_processor."""
        import imgtools_m8.multiprocess as mp_mod

        conf = {
            "source_path": HelperTest.get_source_path(),
            "output_path": HelperTest.get_output_path(),
            "output_options": [{"formats": [{"ext": "WEBP", "quality": 80}]}],
        }
        _init_worker(conf, None)
        assert mp_mod._worker_processor is not None

    def test_process_one_file_with_worker(self):
        """Returns bool after worker is initialized."""
        from os.path import join

        conf = {
            "source_path": HelperTest.get_source_path(),
            "output_path": HelperTest.get_output_path(),
            "output_options": [{"formats": [{"ext": "WEBP", "quality": 80}]}],
        }
        _init_worker(conf, None)
        src = join(HelperTest.get_source_path(), "cat1", "mar.jpg")
        result = _process_one_file(src, {"name": "mar.jpg", "sub_dirs": None})
        assert isinstance(result, bool)

    def test_process_one_file_exception_returns_false(self):
        """Returns False when processor raises an unexpected exception."""
        from unittest.mock import MagicMock

        import imgtools_m8.multiprocess as mp_mod

        mock_proc = MagicMock()
        mock_proc.process_file.side_effect = RuntimeError("boom")
        original = mp_mod._worker_processor
        mp_mod._worker_processor = mock_proc
        try:
            result = _process_one_file("/any.jpg", {"name": "any.jpg"})
            assert result is False
        finally:
            mp_mod._worker_processor = original


class TestHandleSignal:
    def test_sets_interrupted(self):
        obj = _make_obj(source_path=HelperTest.get_source_path())
        assert not obj.interrupted.is_set()
        obj._handle_signal(2, None)
        assert obj.interrupted.is_set()


class TestRunMultipleExtra:
    def test_interrupted_before_batch(self):
        """If interrupted before processing, returns False."""
        obj = _make_obj(source_path=os.path.join(HelperTest.get_source_path(), "good"))
        obj.interrupted.set()
        result = obj.run_multiple()
        assert result is False

    def test_run_multiple_partial_failure(self, monkeypatch):
        """When starmap returns [False], result becomes False (line 221)."""
        import multiprocessing as mp_mod

        class _PartialPool:
            def __init__(self, *a, **kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def terminate(self):
                pass

            def starmap(self, *a, **kw):
                return [False]

        monkeypatch.setattr(mp_mod, "Pool", _PartialPool)
        obj = _make_obj(source_path=os.path.join(HelperTest.get_source_path(), "good"))
        result = obj.run_multiple()
        assert result is False

    def test_run_multiple_exception_returns_false(self, monkeypatch):
        """Exception in pool causes run_multiple to return False (lines 224-226)."""
        import multiprocessing as mp_mod

        class _BoomPool:
            def __init__(self, *a, **kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def terminate(self):
                pass

            def starmap(self, *a, **kw):
                raise RuntimeError("pool exploded")

        monkeypatch.setattr(mp_mod, "Pool", _BoomPool)
        obj = _make_obj(source_path=os.path.join(HelperTest.get_source_path(), "good"))
        result = obj.run_multiple()
        assert result is False
