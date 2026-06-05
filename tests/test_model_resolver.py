"""
ModelConf.ensure_model_available unittest class (cv2-free).

Use pytest package.
"""

from os.path import dirname, join

import pytest

from imgtools_m8.core.exceptions import ModelNotFoundError
from imgtools_m8.helpers.model_conf import ModelConf

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "2.0.0"

# Co-located source-tree models (repo_root/assets/models/opencv).
MODELS_DIR = join(dirname(dirname(__file__)), "assets", "models", "opencv")


class TestEnsureModelAvailable:
    @staticmethod
    def test_returns_path_when_present():
        """A populated models dir resolves to the model file path."""
        result = ModelConf.ensure_model_available(MODELS_DIR, "edsr", 2)
        assert result == join(MODELS_DIR, "EDSR_x2.pb")

    @staticmethod
    def test_missing_dir_raises():
        """A non-existent models dir raises ModelNotFoundError with hint."""
        with pytest.raises(ModelNotFoundError) as exc:
            ModelConf.ensure_model_available("/no/such/models/dir", "edsr", 2)
        assert "download-models" in str(exc.value)

    @staticmethod
    def test_empty_dir_raises(tmp_path):
        """An empty models dir raises ModelNotFoundError."""
        with pytest.raises(ModelNotFoundError):
            ModelConf.ensure_model_available(str(tmp_path), "edsr", 2)
