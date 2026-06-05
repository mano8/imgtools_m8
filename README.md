# imgtools_m8

[![Python package](https://github.com/mano8/imgtools_m8/actions/workflows/python-package.yml/badge.svg)](https://github.com/mano8/imgtools_m8/actions/workflows/python-package.yml)
[![PyPI package](https://img.shields.io/pypi/v/imgtools_m8.svg)](https://pypi.org/project/imgtools_m8/)
[![codecov](https://codecov.io/gh/mano8/imgtools_m8/branch/main/graph/badge.svg?token=0J31F62GB7)](https://codecov.io/gh/mano8/imgtools_m8)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/c401bed6812d4f9bb77bfaee16cf0abe)](https://www.codacy.com/gh/mano8/imgtools_m8/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=mano8/imgtools_m8&amp;utm_campaign=Badge_Grade)
[![Downloads](https://static.pepy.tech/badge/imgtools-m8)](https://pepy.tech/project/imgtools-m8)
[![Known Vulnerabilities](https://snyk.io/test/github/mano8/vedirect_m8/badge.svg)](https://snyk.io/test/github/mano8/imgtools_m8)

Python image processing package for converting, downscaling, and optionally upscaling images using Pillow. DNN-based super-resolution upscaling (via OpenCV) is available as an optional extra.

## Installation

```bash
# Core install (Pillow + Pydantic + NumPy only)
pip install imgtools_m8 --upgrade

# With DNN upscaling support (adds opencv-contrib-python)
pip install "imgtools_m8[dnn]" --upgrade

# With CLI color output (adds colorama)
pip install "imgtools_m8[cli]" --upgrade

# Everything at once
pip install "imgtools_m8[dnn,cli]" --upgrade

# From GitHub
pip install "git+https://github.com/mano8/imgtools_m8" --upgrade
```

## Dependencies

| Package | Required | Notes |
| --- | --- | --- |
| `Pillow>=12.2.0` | yes | Core image I/O and format conversion |
| `pydantic>=2.13.4` | yes | Config validation |
| `numpy>=2.4.6` | yes | Array support |
| `opencv-contrib-python>=4.13.0.92` | no | DNN upscaling only — `pip install imgtools_m8[dnn]` |
| `colorama>=0.4.6` | no | Colored CLI output — `pip install imgtools_m8[cli]` |

## Quick start

```python
from imgtools_m8.image_process import ImageProcessing

obj = ImageProcessing(
    conf={
        "source_path": "./tests/sources_test/recien_llegado.jpg",
        "output_path": "./output",
        "output_options": [
            {
                "formats": [
                    {"ext": "JPEG", "quality": 80, "progressive": True, "optimize": True},
                    {"ext": "WEBP", "quality": 70},
                    {"ext": "PNG"},
                ]
            }
        ],
    }
)
obj.run()
```

## Usage

`ImageProcessing` is the main class. It accepts a `conf` dict validated by `ImageProcessingSchema`.

### Configuration structure

```python
conf = {
    # Required
    "source_path": "/path/to/image.jpg",   # or a directory
    "output_path": "/path/to/output/",

    # Optional
    "include_subdirs": False,   # scan subdirectories when source is a dir
    "flatten_output": False,    # write all outputs flat (no subdir mirror)

    # At least one of output_options or global_options is required
    "output_options": [...],    # per-size output rules (see below)
    "global_options": {...},    # fallback formats/byte-limit for all options
}
```

### `output_options` entries

Each entry in `output_options` may specify:

| Field | Type | Description |
|---|---|---|
| `image_size` | `OutputSize` | Resize spec (see below) |
| `allow_upscale` | `bool` | Allow upscaling when image is smaller than target |
| `max_byte_size` | `int` | Hard byte ceiling per output file (binary-search on quality) |
| `formats` | `list[FormatConfig]` | Output formats for this size |

### `image_size` variants (mutually exclusive where noted)

| Field | Description |
| --- | --- |
| `fixed_width` | Resize to exact width, keep aspect ratio |
| `fixed_height` | Resize to exact height, keep aspect ratio |
| `fixed_width` + `fixed_height` | Fit within bounding box, keep aspect ratio |
| `fixed_size` | Constrain longest side to N pixels |
| `fixed_downscale` | Divide each dimension by factor (2–10) |
| `fixed_upscale` | Multiply each dimension by factor (2–10); uses DNN model when available |

### Supported output formats

| `ext` value | Notes |
|---|---|
| `"JPEG"` | quality, optimize, progressive, subsampling |
| `"WEBP"` | quality, lossless, method |
| `"PNG"` | optimize, compression_level, interlace |
| `"GIF"` | optimize |
| `"AVIF"` | quality, lossless |

### Example 1 — convert to multiple formats without resizing

```python
from imgtools_m8.image_process import ImageProcessing

obj = ImageProcessing(
    conf={
        "source_path": "./tests/sources_test/recien_llegado.jpg",
        "output_path": "./output",
        "output_options": [
            {
                "formats": [
                    {"ext": "JPEG", "quality": 80, "progressive": True, "optimize": True},
                    {"ext": "WEBP", "quality": 70},
                    {"ext": "PNG"},
                ]
            }
        ],
    }
)
obj.run()
```

### Example 2 — downscale to a fixed bounding box

The image is 340×216 px. With `fixed_width=300, fixed_height=200`, the wider constraint wins
(width ratio = 300/340 ≈ 88 %; height ratio = 200/216 ≈ 93 %), so the output is 300×190 px.

```python
from imgtools_m8.image_process import ImageProcessing

obj = ImageProcessing(
    conf={
        "source_path": "./tests/sources_test/recien_llegado.jpg",
        "output_path": "./output",
        "output_options": [
            {
                "image_size": {"fixed_width": 300, "fixed_height": 200},
                "formats": [
                    {"ext": "JPEG", "quality": 80, "progressive": True, "optimize": True}
                ],
            }
        ],
    }
)
obj.run()
```

### Example 3 — upscale then downscale (DNN model)

Requires `pip install imgtools_m8[dnn]`. The EDSR model (included) is used automatically.

```python
from imgtools_m8.image_process import ImageProcessing

obj = ImageProcessing(
    conf={
        "source_path": "./tests/sources_test/recien_llegado.jpg",
        "output_path": "./output",
        "output_options": [
            {
                "image_size": {"fixed_width": 1200},
                "allow_upscale": True,
                "formats": [
                    {"ext": "JPEG", "quality": 80, "progressive": True, "optimize": True}
                ],
            }
        ],
    }
)
obj.run()
```

### Example 4 — process a whole directory with subdirectory mirroring

```python
from imgtools_m8.image_process import ImageProcessing

obj = ImageProcessing(
    conf={
        "source_path": "./tests/sources_test/",
        "output_path": "./output",
        "include_subdirs": True,
        "output_options": [
            {
                "image_size": {"fixed_size": 800},
                "max_byte_size": 200_000,
                "formats": [
                    {"ext": "WEBP", "quality": 85}
                ],
            }
        ],
    }
)
obj.run()
```

### Example 5 — multiprocessing batch with resource monitoring

```python
from imgtools_m8.multiprocess import MultiProcessImage

obj = MultiProcessImage(
    conf={
        "source_path": "./tests/sources_test/",
        "output_path": "./output",
        "include_subdirs": True,
        "output_options": [
            {
                "image_size": {"fixed_width": 800},
                "formats": [{"ext": "WEBP", "quality": 80}],
            }
        ],
    },
    max_cpu_percent=75,
    user_cpu_percent=50,
    batch_size=32,
)
obj.run_multiple()
```

## CLI

After installation, an `imgtools` command is available:

```bash
# Convert to WEBP at 80% quality (default when no --format is given)
imgtools --source ./images --output ./out

# Resize to 1920 px wide and save as JPEG + WEBP
imgtools --source ./images --output ./out --width 1920 --format jpg:95 --format webp:80

# Process subdirectories in parallel with 4 workers
imgtools --source ./images --output ./out --subdirs --workers 4

# Load a full conf dict from a JSON file
imgtools --source ./images --output ./out --config ./my_conf.json

# Enable debug logging
imgtools --source ./images --output ./out --debug
```

Install `[cli]` to get colored log output:

```bash
pip install "imgtools_m8[cli]"
```

Run `imgtools --help` for the full argument reference. The `--workers` flag
switches from single-process (`ImageProcessing`) to multiprocess
(`MultiProcessImage`); the worker count is clamped to `cpu_count - 1`
to avoid saturating the system.

## DNN upscaling note

When `opencv-contrib-python` is not installed, `fixed_upscale` falls back to PIL bicubic scaling.
Install the `[dnn]` extra to enable DNN upscaling:

```bash
pip install "imgtools_m8[dnn]"
```

### Models (DNN upscaling)

The EDSR `.pb` models are **not bundled** in the wheel (saves ~111 MB). After installing the
`[dnn]` extra, fetch them once with:

```bash
imgtools download-models
```

Models are SHA256-verified and stored in the platform cache directory. To use a custom location,
set `IMGTOOLS_M8_MODELS_DIR` to a directory that contains an `opencv/` subdirectory with the
`.pb` files. If the models are absent when upscaling is attempted, a `ModelNotFoundError` is
raised with a reminder to run `imgtools download-models`.

Custom models in `.pb` format can be loaded by passing a `model_conf` dict to `ImageProcessing`:

```python
obj = ImageProcessing(
    conf={...},
    model_conf={
        "path": "/path/to/model/directory",
        "model_name": "espcn",   # model prefix, e.g. espcn, edsr, lapsrn
        "scale": 4,              # fixed scale (omit for AUTO_SCALE)
    },
)
```

## Docker (CUDA-accelerated DNN upscaling)

A `Dockerfile` is provided to build a CUDA-enabled image that compiles OpenCV
from source with GPU support, enabling hardware-accelerated DNN upscaling.

**Requirements:** Docker + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

```bash
# Build with defaults (CUDA 13.3 / Ubuntu 24.04 / OpenCV 4.13)
docker build -t imgtools_m8 .

# Target a specific GPU compute capability (much faster compile)
docker build --build-arg CUDA_ARCH_BIN=8.9 -t imgtools_m8 .

# Run with GPU access
docker run --gpus all imgtools_m8 --help
```

Find your GPU's compute capability at [developer.nvidia.com/cuda-gpus](https://developer.nvidia.com/cuda-gpus):
RTX 30xx → `8.6`, RTX 40xx → `8.9`, RTX 50xx → `10.0`.

Build arguments (`OPENCV_VERSION`, `CUDA_ARCH_BIN`) are documented in `.env.example`.
A `docker-compose.yml` for multi-volume GPU batch processing is in `docker_compose/imgtools_dev/`.

## Input/Output Example

### Input Image
The source file is 340×216 px.
<div align="center">
  <img src="https://raw.githubusercontent.com/mano8/imgtools_m8/main/tests/sources_test/recien_llegado.jpg" alt="Recien Llegado @Cezar llañez" width="340" height="216" />
  <p>Recien llegado by <a href="https://www.ichingmaestrodelosespiritus.com/">@Cezar yañez</a></p>
</div>

## License

This project is licensed under the Apache 2 License — see the [LICENSE](https://github.com/mano8/imgtools_m8/blob/main/LICENCE) file for details.

## Authors

- [Eli Serra](https://github.com/mano8)
- Pre-trained DNN models by [Xavier Weber](https://towardsdatascience.com/deep-learning-based-super-resolution-with-opencv-4fd736678066)
