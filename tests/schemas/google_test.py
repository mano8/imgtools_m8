"""Tests for schemas.google."""
from auth_user_service.schemas.google import OAuthGoogleToken


class TestOAuthGoogleToken:
    def test_valid_full_token(self):
        token = OAuthGoogleToken(
            access_token="goog_access",
            expires_in=3600,
            refresh_token="goog_refresh",
            user_id="12345",
            email="user@gmail.com",
            email_verified=True,
            name="Google User",
            picture="https://example.com/pic.jpg",
        )
        assert token.access_token == "goog_access"
        assert token.email == "user@gmail.com"
        assert token.email_verified is True

    def test_minimal_required_fields(self):
        token = OAuthGoogleToken(
            access_token="goog_access",
            expires_in=3600,
            refresh_token="goog_refresh",
            user_id="12345",
            email="user@gmail.com",
            email_verified=False,
            name="User",
            picture="https://example.com/pic.jpg",
        )
        assert token.user_id == "12345"
