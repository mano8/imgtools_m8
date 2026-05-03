"""Manage add on auth."""
from google.oauth2 import id_token
from google.auth.transport import requests as googleRequests
import httpx
from fastapi import HTTPException

from auth_user_service.schemas.google import OAuthGoogleToken
from auth_user_service.core.config import settings


class OAuthController:
    """Manage add on auth."""
    @staticmethod
    async def get_google_access_token(
        code: str,
        code_verifier: str,
        redirect_uri: str
    ) -> OAuthGoogleToken:
        """
        get and verrify google access token from OAuth callback
        """
        token_request_uri = "https://oauth2.googleapis.com/token"
        data = {
            'code': code,
            'client_id': settings.GOOGLE_CLIENT_ID.get_secret_value(),
            'client_secret': settings.GOOGLE_CLIENT_SECRET.get_secret_value(),
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
            'code_verifier': code_verifier
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(token_request_uri, data=data)
                response.raise_for_status()
                token_data = response.json()

            if "id_token" not in token_data:
                raise HTTPException(status_code=400, detail="Missing id_token in token response.")
            try:
                id_info = id_token.verify_oauth2_token(
                    token_data["id_token"],
                    googleRequests.Request(),
                    settings.GOOGLE_CLIENT_ID.get_secret_value(),
                    clock_skew_in_seconds=10
                )
            except Exception as e:
                raise HTTPException(
                    status_code=400, detail=f"Invalid id_token: {e}") from e

            return OAuthGoogleToken(
                access_token=token_data.get("access_token"),
                expires_in=token_data.get("expires_in"),
                refresh_token=token_data.get("refresh_token"),
                user_id=id_info.get("sub"),
                email=id_info.get("email"),
                email_verified=id_info.get("email_verified"),
                name=id_info.get("name"),
                picture=id_info.get("picture")
            )
        except httpx.HTTPError as ex:
            raise HTTPException(status_code=400, detail=f"Token exchange failed: {ex}") from ex
        except Exception as ex:
            raise HTTPException(status_code=500, detail=f"Authentication error: {ex}") from ex
