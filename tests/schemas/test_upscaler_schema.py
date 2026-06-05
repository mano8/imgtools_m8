"""Tests for imgtools_m8.schemas.upscaler_schema."""

from imgtools_m8.schemas.upscaler_schema import UpscaleModelType


class TestUpscaleModelType:
    def test_to_dict(self):
        obj = UpscaleModelType(model_name="edsr", scale=2)
        result = obj.to_dict()
        assert isinstance(result, dict)
        assert result["model_name"] == "edsr"
        assert result["scale"] == 2

    def test_to_dict_defaults(self):
        obj = UpscaleModelType()
        result = obj.to_dict()
        assert result["model_name"] is None
        assert result["scale"] is None
        assert result["model_path"] is None
