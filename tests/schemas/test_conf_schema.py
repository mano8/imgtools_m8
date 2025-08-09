"""
Additional tests for imgtools_m8.schemas.conf_schema.

These tests use pytest, pytest.mark.parametrize, and pytest fixtures.
They follow PEP8/flake8 (max line length 79) and Google style docstrings.
"""

import pytest
from pydantic import ValidationError
from imgtools_m8.schemas import conf_schema

# pylint: disable=redefined-outer-name, no-member


@pytest.fixture
def jpeg_format_defaults():
    """Fixture for default JPEG format."""
    return conf_schema.JpegFormat()


@pytest.fixture
def webp_format_defaults():
    """Fixture for default WebP format."""
    return conf_schema.WebpFormat()


@pytest.fixture
def png_format_defaults():
    """Fixture for default PNG format."""
    return conf_schema.PngFormat()


@pytest.fixture
def gif_format_defaults():
    """Fixture for default GIF format."""
    return conf_schema.GifFormat()


@pytest.fixture
def avif_format_defaults():
    """Fixture for default AVIF format."""
    return conf_schema.AvifFormat()


class TestJpegFormat:
    """Tests for JpegFormat schema."""

    @pytest.mark.parametrize(
        "quality, expected",
        [
            (1, 1),
            (50, 50),
            (100, 100),
            (None, None),
        ],
    )
    def test_quality_valid(self, quality, expected):
        """Test valid JPEG quality values."""
        fmt = conf_schema.JpegFormat(
            quality=quality
        )
        assert fmt.quality == expected

    @pytest.mark.parametrize("quality", [0, 101, -5])
    def test_quality_invalid(self, quality):
        """Test invalid JPEG quality values."""
        with pytest.raises(ValidationError):
            conf_schema.JpegFormat(quality=quality)

    @pytest.mark.parametrize(
        "subsampling", [0, 1, 2, "4:4:4", "4:2:2", "4:2:0"]
    )
    def test_subsampling_valid(self, subsampling):
        """Test valid subsampling values."""
        fmt = conf_schema.JpegFormat(subsampling=subsampling)
        assert fmt.subsampling == subsampling

    @pytest.mark.parametrize("subsampling", ["4:1:1", 3, "bad"])
    def test_subsampling_invalid(self, subsampling):
        """Test invalid subsampling values."""
        with pytest.raises(ValidationError):
            conf_schema.JpegFormat(subsampling=subsampling)

    def test_defaults(self, jpeg_format_defaults):
        """Test JPEG format defaults."""
        assert jpeg_format_defaults.optimize is False
        assert jpeg_format_defaults.progressive is False
        assert jpeg_format_defaults.quality is None
        assert jpeg_format_defaults.subsampling is None


class TestWebpFormat:
    """Tests for WebpFormat schema."""

    @pytest.mark.parametrize(
        "quality,expected",
        [(1, 1), (50, 50), (100, 100), (None, None)],
    )
    def test_quality_valid(self, quality, expected):
        """Test valid WebP quality values."""
        fmt = conf_schema.WebpFormat(quality=quality)
        assert fmt.quality == expected

    @pytest.mark.parametrize("quality", [0, 101, -1])
    def test_quality_invalid(self, quality):
        """Test invalid WebP quality values."""
        with pytest.raises(ValidationError):
            conf_schema.WebpFormat(quality=quality)

    @pytest.mark.parametrize("method", [0, 3, 6, None])
    def test_method_valid(self, method):
        """Test valid WebP method values."""
        fmt = conf_schema.WebpFormat(method=method)
        assert fmt.method == method

    @pytest.mark.parametrize("method", [-1, 7, 100])
    def test_method_invalid(self, method):
        """Test invalid WebP method values."""
        with pytest.raises(ValidationError):
            conf_schema.WebpFormat(method=method)

    def test_defaults(self, webp_format_defaults):
        """Test WebP format defaults."""
        assert webp_format_defaults.lossless is False
        assert webp_format_defaults.quality is None
        assert webp_format_defaults.method is None


class TestPngFormat:
    """Tests for PngFormat schema."""

    @pytest.mark.parametrize(
        "compression_level,expected",
        [(0, 0), (5, 5), (9, 9), (None, None)],
    )
    def test_compression_level_valid(self, compression_level, expected):
        """Test valid PNG compression levels."""
        fmt = conf_schema.PngFormat(compression_level=compression_level)
        assert fmt.compression_level == expected

    @pytest.mark.parametrize("compression_level", [-1, 10, 100])
    def test_compression_level_invalid(self, compression_level):
        """Test invalid PNG compression levels."""
        with pytest.raises(ValidationError):
            conf_schema.PngFormat(compression_level=compression_level)

    def test_defaults(self, png_format_defaults):
        """Test PNG format defaults."""
        assert png_format_defaults.optimize is False
        assert png_format_defaults.compression_level is None
        assert png_format_defaults.interlace is False


class TestGifFormat:
    """Tests for GifFormat schema."""

    def test_defaults(self, gif_format_defaults):
        """Test GIF format defaults."""
        assert gif_format_defaults.optimize is False

    @pytest.mark.parametrize("optimize", [True, False])
    def test_optimize(self, optimize):
        """Test GIF optimize option."""
        fmt = conf_schema.GifFormat(optimize=optimize)
        assert fmt.optimize is optimize


class TestAvifFormat:
    """Tests for AvifFormat schema."""

    @pytest.mark.parametrize(
        "quality,expected",
        [(1, 1), (50, 50), (100, 100), (None, None)],
    )
    def test_quality_valid(self, quality, expected):
        """Test valid AVIF quality values."""
        fmt = conf_schema.AvifFormat(
            quality=quality
        )
        assert fmt.quality == expected

    @pytest.mark.parametrize("quality", [0, 101, -1])
    def test_quality_invalid(self, quality):
        """Test invalid AVIF quality values."""
        with pytest.raises(ValidationError):
            conf_schema.AvifFormat(quality=quality)

    def test_defaults(self, avif_format_defaults):
        """Test AVIF format defaults."""
        assert avif_format_defaults.lossless is False
        assert avif_format_defaults.quality is None


class TestOutputSize:
    """Tests for OutputSize schema."""

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"fixed_width": 100},
            {"fixed_height": 200},
            {"fixed_size": 300},
            {"fixed_upscale": 2},
            {"fixed_downscale": 2},
        ],
    )
    def test_valid_single_constraints(self, kwargs):
        """Test valid single constraints."""
        size = conf_schema.OutputSize(**kwargs)
        for k, v in kwargs.items():
            assert getattr(size, k) == v

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"fixed_size": 100, "fixed_width": 50},
            {"fixed_upscale": 3, "fixed_height": 200},
            {"fixed_downscale": 2, "fixed_width": 100},
        ],
    )
    def test_invalid_combinations(self, kwargs):
        """Test invalid combinations of constraints."""
        with pytest.raises(ValidationError):
            conf_schema.OutputSize(**kwargs)

    @pytest.mark.parametrize(
        "field,value",
        [
            ("fixed_width", 0),
            ("fixed_height", -1),
            ("fixed_size", 0),
            ("fixed_upscale", 1),
            ("fixed_downscale", 11),
        ],
    )
    def test_invalid_values(self, field, value):
        """Test invalid values for OutputSize fields."""
        kwargs = {field: value}
        with pytest.raises(ValidationError):
            conf_schema.OutputSize(**kwargs)


class TestOutputOptions:
    """Tests for OutputOptions schema."""

    def test_valid_with_all_fields(self):
        """Test OutputOptions with all fields set."""
        size = conf_schema.OutputSize(fixed_width=100)
        fmt = conf_schema.JpegFormat(quality=80)
        out = conf_schema.OutputOptions(
            image_size=size, allow_upscale=True,
            max_byte_size=5000, formats=[fmt]
        )
        assert out.image_size.fixed_width == 100
        assert out.allow_upscale is True
        assert out.max_byte_size == 5000
        assert isinstance(out.formats[0], conf_schema.JpegFormat)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"image_size": None, "max_byte_size": None, "formats": None},
            {},
        ],
    )
    def test_invalid_none_set(self, kwargs):
        """Test OutputOptions with no required fields set."""
        with pytest.raises(ValidationError):
            conf_schema.OutputOptions(**kwargs)

    def test_allow_upscale_set_by_fixed_upscale(self):
        """Test allow_upscale is set when fixed_upscale is used."""
        size = conf_schema.OutputSize(fixed_upscale=3)
        out = conf_schema.OutputOptions(image_size=size)
        assert out.allow_upscale is True

    def test_formats_accepts_multiple_types(self):
        """Test formats accepts multiple format types."""
        fmt1 = conf_schema.JpegFormat(quality=80)
        fmt2 = conf_schema.PngFormat(optimize=True)
        out = conf_schema.OutputOptions(formats=[fmt1, fmt2])
        assert isinstance(out.formats[0], conf_schema.JpegFormat)
        assert isinstance(out.formats[1], conf_schema.PngFormat)


class TestImageProcessingSchema:
    """Tests for ImageProcessingConfig schema."""

    def test_valid_config_with_all_fields(self):
        """Test valid ImageProcessingConfig with all fields."""
        size = conf_schema.OutputSize(fixed_width=100)
        out = conf_schema.OutputOptions(image_size=size)
        cfg = conf_schema.ImageProcessingSchema(
            source_path="input.jpg",
            include_subdirs=True,
            output_path="out/",
            flatten_output=True,
            output_options=[out],
        )
        assert cfg.source_path == "input.jpg"
        assert cfg.include_subdirs is True
        assert cfg.output_path == "out/"
        assert cfg.flatten_output is True
        assert isinstance(cfg.output_options, list)
        assert isinstance(cfg.output_options[0], conf_schema.OutputOptions)

    def test_missing_source_path(self):
        """Test missing required source_path."""
        size = conf_schema.OutputSize(fixed_width=100)
        out = conf_schema.OutputOptions(image_size=size)
        with pytest.raises(ValidationError):
            conf_schema.ImageProcessingSchema(
                output_path="out/",
                output_options=out,
            )

    def test_missing_output_path(self):
        """Test missing required output_path."""
        size = conf_schema.OutputSize(fixed_width=100)
        out = conf_schema.OutputOptions(image_size=size)
        with pytest.raises(ValidationError):
            conf_schema.ImageProcessingSchema(
                source_path="input.jpg",
                output_options=out,
            )

    def test_valid_flatten_output_constraints(self):
        """Test missing required flatten_output."""
        cfg = conf_schema.ImageProcessingSchema(
            source_path="input.jpg",
            output_path="out/",
            flatten_output=True,
        )
        assert cfg.source_path == "input.jpg"
        assert cfg.output_path == "out/"
        assert cfg.flatten_output is True
        assert cfg.include_subdirs is True
        assert cfg.output_options is None
        assert cfg.global_options is None

    def test_valid_output_options_constraints(self):
        """Test missing required output_options."""
        size = conf_schema.OutputSize(fixed_width=100)
        out = conf_schema.OutputOptions(image_size=size)

        cfg = conf_schema.ImageProcessingSchema(
            source_path="input.jpg",
            output_path="out/",
            output_options=[out]
        )
        assert cfg.source_path == "input.jpg"
        assert cfg.output_path == "out/"
        assert cfg.flatten_output is False
        assert cfg.include_subdirs is False
        assert cfg.global_options is None
        assert isinstance(cfg.output_options, list)
        assert isinstance(cfg.output_options[0], conf_schema.OutputOptions)

    def test_valid_global_options_constraints(self):
        """Test missing required output_options."""
        avif_format = conf_schema.AvifFormat(quality=80)
        out = conf_schema.GlobalOutputOptions(formats=[avif_format])

        cfg = conf_schema.ImageProcessingSchema(
            source_path="input.jpg",
            output_path="out/",
            global_options=out
        )
        assert cfg.source_path == "input.jpg"
        assert cfg.output_path == "out/"
        assert cfg.flatten_output is False
        assert cfg.include_subdirs is False
        assert cfg.output_options is None
        assert isinstance(cfg.global_options, conf_schema.GlobalOutputOptions)

    def test_invalid_constraints(self):
        """Test missing required output_options."""
        with pytest.raises(ValueError):
            conf_schema.ImageProcessingSchema(
                source_path="input.jpg",
                output_path="out/",
            )
