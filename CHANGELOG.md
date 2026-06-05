# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `Dockerfile` CUDA build upgraded to CUDA 13.3 / Ubuntu 24.04 / OpenCV 4.13;
  `CUDA_ARCH_BIN` build-arg added for GPU-specific compile (e.g. `8.9` for RTX 40xx)
- `.env.example` documenting `OPENCV_VERSION` and `CUDA_ARCH_BIN` build arguments
- `.dockerignore` to exclude `tests/`, `build/`, `docs/` from the Docker build context
- Docker section in README covering CUDA build, run, and compute-capability reference

### Changed

- Docker base image pinned by digest (`nvidia/cuda:13.3.0-cudnn-devel-ubuntu24.04`)
- Dockerfile now uses a Python venv so pip deps and OpenCV bindings share one environment
- `ENTRYPOINT` + `CMD ["--help"]` replacing the previous `command:` override

### Fixed

- `requirements.txt` re-encoded as UTF-8 (was UTF-16 LE, broke `pip install`
  inside Docker)
- Coverage scoped to the `imgtools_m8` package only; pytest and VS Code
  reporter aligned
- All `ruff`, `mypy`, and `bandit` errors resolved across the codebase

### Build

- Python 3.11–3.14 declared as supported range in `setup.cfg`
- CI workflow split into independent jobs with SHA-pinned actions and
  Dependabot config

---

## [2.0.0] - 2026-05-29

### Breaking Changes

- `ImageTools` class removed — use `ImageProcessing` with a `conf` dict instead
- `ProcessConf` class removed — use `ImageProcessingSchema` dict config directly
- `opencv-contrib-python` is now optional — DNN upscaling requires `pip install imgtools_m8[dnn]`
- `MultiProcessImage` no longer inherits from `ImageTools` — use composition via `conf` dict

### Added

- `imgtools` CLI command with `--source`, `--output`, `--format`, `--width`, `--height`,
  `--size`, `--downscale`, `--upscale`, `--allow-upscale`, `--max-bytes`, `--subdirs`,
  `--flatten`, `--workers`, `--config`, `--debug` flags
- `[cli]` optional extra (`colorama>=0.4.6`) for colored log output
- `configure_logging()` uses colorama colors per log level when the `[cli]` extra is installed
- `num_processes` parameter on `MultiProcessImage` for direct worker-count override;
  clamped to `cpu_count - 1` to prevent system saturation
- `ImageProcessing` as the single authoritative image-processing pipeline (PIL + Pydantic)
- `global_options` config key: fallback formats and byte-limit for all `output_options` entries
- `include_subdirs` config key: scan subdirectories when source is a directory
- `flatten_output` config key: write all outputs flat (no subdir mirroring)
- DNN upscaling in `ImageProcessing` via optional `model_conf` parameter
- `CV2_AVAILABLE` module-level flag in `img_expander` for runtime cv2 detection
- `MultiProcessImage` composition pattern: one `ImageProcessing` instance per worker process
- Pool initializer (`_init_worker`) so DNN models load once per worker, not once per image
- `psutil` and `tqdm` made optional in `multiprocess.py`
- `ruff` and `mypy` added to dev tooling (`requirements-dev.txt`, `pyproject.toml`)
- pytest configuration in `pyproject.toml` (`testpaths`, `addopts`)
- 34 tests covering guards, static helpers, `process_file`, `run`, and `_enforce_max_bytes`

### Fixed

- `multiprocess.py` crash on import (missing `signal`, `List`, `Tuple` imports)
- DNN model was loaded once per image — now loaded once per worker process via pool initializer
- Schema `@model_validator` methods had wrong return-type annotations (`OutputOptions` on all)
- `get_format_kwargs` in `helpers/image_utils.py` raised `TypeError` due to `isinstance` on `Annotated[Union[...]]`
- `logging.basicConfig()` called at module level in multiple files — removed from all except `__init__.py`

### Removed

- `ImageTools` class (`img_tools.py` deleted)
- `ProcessConf` class (`process_conf.py` deleted)
- `upscaler.py` (dead code, replaced by `_dnn_upscale` in `ImageProcessing`)
- `helpers/cv_utils.py` (only used by `upscaler.py`)
- `modules/` directory (empty stubs)
- `ve_utils` dependency — replaced with `isinstance()` throughout
- `img_tools_sav.py`, `core/conf.py`, `core/source_scan.py` (dead/empty files)
- `tests/test_img_tools.py` and `tests/test_precess_conf.py` (obsolete tests)

## [1.1.0] - 2024-01

### Added

- Pydantic v2 schema (`ImageProcessingSchema`) for config validation
- `OutputSize` with `fixed_width`, `fixed_height`, `fixed_size`, `fixed_downscale`, `fixed_upscale` variants
- Format discriminated union (`FormatConfig`) for JPEG, WEBP, PNG, GIF, AVIF

## [1.0.0] - 2023-06

### Added

- Initial release with `ImageTools` and `ProcessConf`
- OpenCV-based DNN super-resolution via `ImageExpander`
- `MultiProcessImage` for parallel batch processing
