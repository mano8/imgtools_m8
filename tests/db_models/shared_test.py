"""Tests for db_models.shared models."""
import pytest
from auth_user_service.db_models.shared import NewPassword


class TestNewPassword:
    def test_valid_new_password(self):
        np = NewPassword(token="reset_token_abc", new_password="newpass123")
        assert np.token == "reset_token_abc"
        assert np.new_password == "newpass123"

    def test_password_min_length_enforced(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            NewPassword(token="tok", new_password="short")

    def test_password_max_length_enforced(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            NewPassword(token="tok", new_password="x" * 129)

    def test_long_valid_password(self):
        np = NewPassword(token="tok", new_password="a" * 128)
        assert len(np.new_password) == 128
