"""
CLI (imgtools_m8.__main__) unittest class.

Use pytest package.
"""

import json
import logging
import multiprocessing
from os.path import join

import pytest

import imgtools_m8
from imgtools_m8 import configure_logging
from imgtools_m8.__main__ import (
    _build_conf,
    _build_image_size,
    _parse_format,
    _select_models,
    main,
)

from .helper import HelperTest

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "2.0.0"


# ---------------------------------------------------------------------------
# _parse_format
# ---------------------------------------------------------------------------


class TestParseFormat:
    def test_ext_with_quality(self):
        assert _parse_format("webp:80") == {"ext": "WEBP", "quality": 80}

    def test_jpg_alias(self):
        assert _parse_format("jpg:95") == {"ext": "JPEG", "quality": 95}

    def test_jpeg_alias(self):
        assert _parse_format("jpeg:75") == {"ext": "JPEG", "quality": 75}

    def test_ext_only(self):
        assert _parse_format("png") == {"ext": "PNG"}

    def test_unknown_ext_uppercased(self):
        assert _parse_format("avif:60") == {"ext": "AVIF", "quality": 60}

    def test_invalid_quality_ignored(self):
        result = _parse_format("webp:bad")
        assert result["ext"] == "WEBP"
        assert "quality" not in result


# ---------------------------------------------------------------------------
# _build_image_size
# ---------------------------------------------------------------------------


class TestBuildImageSize:
    def _args(self, **kwargs):
        import argparse

        defaults = dict(
            width=None, height=None, size=None, downscale=None, upscale=None
        )
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_no_flags_returns_none(self):
        assert _build_image_size(self._args()) is None

    def test_width_only(self):
        assert _build_image_size(self._args(width=800)) == {"fixed_width": 800}

    def test_width_and_height(self):
        result = _build_image_size(self._args(width=800, height=600))
        assert result == {"fixed_width": 800, "fixed_height": 600}

    def test_fixed_size(self):
        assert _build_image_size(self._args(size=1024)) == {"fixed_size": 1024}

    def test_downscale(self):
        assert _build_image_size(self._args(downscale=2)) == {"fixed_downscale": 2}

    def test_upscale(self):
        assert _build_image_size(self._args(upscale=3)) == {"fixed_upscale": 3}


# ---------------------------------------------------------------------------
# _build_conf
# ---------------------------------------------------------------------------


class TestBuildConf:
    def _args(self, **kwargs):
        import argparse

        defaults = dict(
            source=HelperTest.get_source_path(),
            output=HelperTest.get_output_path(),
            format=None,
            width=None,
            height=None,
            size=None,
            downscale=None,
            upscale=None,
            allow_upscale=False,
            max_bytes=None,
            subdirs=False,
            flatten=False,
            config=None,
        )
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_defaults_give_webp_80(self):
        conf = _build_conf(self._args())
        assert conf["output_options"][0]["formats"] == [{"ext": "WEBP", "quality": 80}]

    def test_format_flag_parsed(self):
        conf = _build_conf(self._args(format=["jpg:95", "webp:80"]))
        fmts = conf["output_options"][0]["formats"]
        assert {"ext": "JPEG", "quality": 95} in fmts
        assert {"ext": "WEBP", "quality": 80} in fmts

    def test_image_size_included(self):
        conf = _build_conf(self._args(width=1920))
        assert conf["output_options"][0]["image_size"] == {"fixed_width": 1920}

    def test_config_file_loaded(self, tmp_path):
        data = {
            "source_path": HelperTest.get_source_path(),
            "output_path": HelperTest.get_output_path(),
            "output_options": [{"formats": [{"ext": "PNG"}]}],
        }
        cfg = tmp_path / "conf.json"
        cfg.write_text(json.dumps(data))
        conf = _build_conf(self._args(config=str(cfg)))
        assert conf["output_options"][0]["formats"] == [{"ext": "PNG"}]

    def test_allow_upscale_flag(self):
        conf = _build_conf(self._args(allow_upscale=True))
        assert conf["output_options"][0]["allow_upscale"] is True

    def test_max_bytes_flag(self):
        conf = _build_conf(self._args(max_bytes=50_000))
        assert conf["output_options"][0]["max_byte_size"] == 50_000

    def test_bad_config_file_exits(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json}")
        with pytest.raises(SystemExit):
            _build_conf(self._args(config=str(bad)))


# ---------------------------------------------------------------------------
# main() integration
# ---------------------------------------------------------------------------


class TestMain:
    def test_valid_single_file(self, output_path):
        src = join(HelperTest.get_source_path(), "cat1", "mar.jpg")
        code = main(
            [
                "--source",
                src,
                "--output",
                output_path,
                "--format",
                "webp:80",
                "--width",
                "50",
            ]
        )
        assert code == 0

    def test_invalid_source_returns_1(self, output_path):
        code = main(
            [
                "--source",
                "/nonexistent/path.jpg",
                "--output",
                output_path,
            ]
        )
        assert code == 1

    def test_format_png_no_quality(self, output_path):
        src = join(HelperTest.get_source_path(), "cat1", "mar.jpg")
        code = main(
            [
                "--source",
                src,
                "--output",
                output_path,
                "--format",
                "png",
            ]
        )
        assert code == 0

    def test_debug_flag(self, output_path):
        src = join(HelperTest.get_source_path(), "cat1", "mar.jpg")
        code = main(
            [
                "--source",
                src,
                "--output",
                output_path,
                "--debug",
            ]
        )
        assert code == 0

    def test_config_file(self, output_path, tmp_path):
        src = join(HelperTest.get_source_path(), "cat1", "mar.jpg")
        data = {
            "source_path": src,
            "output_path": output_path,
            "output_options": [{"formats": [{"ext": "WEBP", "quality": 70}]}],
        }
        cfg = tmp_path / "conf.json"
        cfg.write_text(json.dumps(data))
        code = main(["--source", src, "--output", output_path, "--config", str(cfg)])
        assert code == 0

    def test_workers_mode(self, output_path):
        src = join(HelperTest.get_source_path(), "good")
        code = main(
            [
                "--source",
                src,
                "--output",
                output_path,
                "--format",
                "webp:80",
                "--workers",
                "1",
            ]
        )
        assert code == 0

    def test_processing_exception_returns_1(self, output_path, monkeypatch):
        from imgtools_m8 import image_process

        def _boom(self):
            raise RuntimeError("forced failure")

        monkeypatch.setattr(image_process.ImageProcessing, "run", _boom)
        src = join(HelperTest.get_source_path(), "cat1", "mar.jpg")
        code = main(["--source", src, "--output", output_path])
        assert code == 1


# ---------------------------------------------------------------------------
# configure_logging / _ColorFormatter
# ---------------------------------------------------------------------------


class TestConfigureLogging:
    def test_idempotent(self):
        """Calling configure_logging twice does not add duplicate handlers."""
        logger = logging.getLogger("imgTools_m8")
        initial = len(logger.handlers)
        configure_logging()
        configure_logging()
        assert len(logger.handlers) == initial

    def test_color_formatter_with_colorama(self, monkeypatch):
        monkeypatch.setattr(imgtools_m8, "_COLORAMA_AVAILABLE", True)
        formatter = imgtools_m8._ColorFormatter("%(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        assert "hello" in output
        assert "\033[" in output

    def test_color_formatter_without_colorama(self, monkeypatch):
        monkeypatch.setattr(imgtools_m8, "_COLORAMA_AVAILABLE", False)
        formatter = imgtools_m8._ColorFormatter("%(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        assert "hello" in output
        assert "\033[" not in output


# ---------------------------------------------------------------------------
# MultiProcessImage num_processes guard
# ---------------------------------------------------------------------------


class TestNumProcessesGuard:
    def _make(self, **kwargs):
        from imgtools_m8.multiprocess import MultiProcessImage

        return MultiProcessImage(
            conf={
                "source_path": HelperTest.get_source_path(),
                "output_path": HelperTest.get_output_path(),
                "output_options": [{"formats": [{"ext": "WEBP", "quality": 80}]}],
            },
            use_progress=False,
            **kwargs,
        )

    def test_num_processes_respected(self):
        obj = self._make(num_processes=2)
        assert obj.num_processes == 2

    def test_num_processes_clamped_to_safe_max(self):
        safe_max = max(1, multiprocessing.cpu_count() - 1)
        obj = self._make(num_processes=safe_max + 10)
        assert obj.num_processes == safe_max

    def test_num_processes_one_is_valid(self):
        obj = self._make(num_processes=1)
        assert obj.num_processes == 1

    def test_default_uses_user_cpu_percent(self):
        cpu_total = multiprocessing.cpu_count()
        obj = self._make(user_cpu_percent=50)
        expected = max(1, int(cpu_total * 0.5))
        assert obj.num_processes == expected


# ---------------------------------------------------------------------------
# _select_models
# ---------------------------------------------------------------------------


class TestSelectModels:
    def test_no_filter_selects_all(self):
        assert len(_select_models(None, None)) == 3

    def test_backend_filter_miss(self):
        assert _select_models("nope", None) == []

    def test_model_filter_miss(self):
        assert _select_models(None, "nope") == []

    def test_backend_and_model_hit(self):
        selected = _select_models("opencv", "edsr")
        assert {filename for _, filename, _ in selected} == {
            "EDSR_x2.pb",
            "EDSR_x3.pb",
            "EDSR_x4.pb",
        }


# ---------------------------------------------------------------------------
# download-models subcommand + back-compat routing
# ---------------------------------------------------------------------------


class TestDownloadModelsCommand:
    def test_all_downloads_and_reports_ok(self, tmp_path, monkeypatch, capsys):
        from imgtools_m8.helpers import model_downloader

        monkeypatch.setattr(
            model_downloader, "get_dest_dir", lambda backend: str(tmp_path)
        )
        seen = []

        def _fake_download(filename, sha256, dest_dir):
            seen.append(filename)
            return join(dest_dir, filename)

        monkeypatch.setattr(model_downloader, "download_model", _fake_download)
        code = main(["download-models", "--all"])
        assert code == 0
        assert len(seen) == 3
        out = capsys.readouterr().out
        assert "EDSR_x2.pb" in out and "ok" in out

    def test_download_failure_returns_1(self, tmp_path, monkeypatch, capsys):
        from imgtools_m8.helpers import model_downloader

        monkeypatch.setattr(
            model_downloader, "get_dest_dir", lambda backend: str(tmp_path)
        )

        def _boom(filename, sha256, dest_dir):
            raise ValueError("bad digest")

        monkeypatch.setattr(model_downloader, "download_model", _boom)
        code = main(["download-models", "--backend", "opencv"])
        assert code == 1
        assert "FAILED" in capsys.readouterr().out

    def test_no_filter_errors(self):
        assert main(["download-models"]) == 1

    def test_unknown_backend_selects_nothing(self):
        assert main(["download-models", "--backend", "nope"]) == 1


class TestBackCompatRouting:
    def test_source_output_routes_to_process(self, output_path, monkeypatch):
        from imgtools_m8 import image_process

        called = {}

        def _fake_run(self):
            called["ran"] = True
            return True

        monkeypatch.setattr(image_process.ImageProcessing, "run", _fake_run)
        src = join(HelperTest.get_source_path(), "cat1", "mar.jpg")
        code = main(["--source", src, "--output", output_path])
        assert code == 0
        assert called.get("ran") is True

    def test_help_token_is_not_prepended(self):
        with pytest.raises(SystemExit) as exc:
            main(["--help"])
        assert exc.value.code == 0
