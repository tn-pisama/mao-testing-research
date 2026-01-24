from typing import Optional, Dict
import httpx
from jose import jwt, JWTError
from pybreaker import CircuitBreaker

from app.config import get_settings

settings = get_settings()

google_breaker = CircuitBreaker(fail_max=5, reset_timeout=60)


class GoogleAuth:
    """Google OAuth token verification using Google's tokeninfo endpoint."""

    GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"

    def __init__(self):
        pass

    @google_breaker
    async def verify_token(self, id_token: str) -> Dict:
        """Verify a Google ID token using Google's tokeninfo endpoint.

        Args:
            id_token: The Google ID token to verify

        Returns:
            Dict containing user info from the token (sub, email, etc.)

        Raises:
            JWTError: If token verification fails
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    self.GOOGLE_TOKENINFO_URL,
                    params={"id_token": id_token}
                )

                if resp.status_code != 200:
                    raise JWTError(f"Google token verification failed: {resp.text}")

                token_info = resp.json()

                # Validate that the token is for our app
                client_id = settings.google_client_id
                if client_id and token_info.get("aud") != client_id:
                    raise JWTError("Token audience does not match client ID")

                # Check if token is expired
                if "exp" in token_info:
                    import time
                    if int(token_info["exp"]) < time.time():
                        raise JWTError("Token has expired")

                # Return user info
                return {
                    "sub": token_info.get("sub"),  # Google user ID
                    "email": token_info.get("email"),
                    "email_verified": token_info.get("email_verified") == "true",
                    "name": token_info.get("name"),
                    "picture": token_info.get("picture"),
                }

        except httpx.HTTPError as e:
            raise JWTError(f"Failed to verify Google token: {e}")


google_auth: Optional[GoogleAuth] = None


def get_google_auth() -> GoogleAuth:
    """Get or create GoogleAuth instance."""
    global google_auth
    if google_auth is None:
        google_auth = GoogleAuth()
    return google_auth
