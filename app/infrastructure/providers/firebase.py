import os
from functools import lru_cache
from typing import Optional

import firebase_admin
from firebase_admin import credentials

from app.core.config import settings


@lru_cache(maxsize=1)
def _get_credentials() -> credentials.Certificate:
    """
    Resolve Firebase credentials from the service account JSON file path.
    """
    path = settings.FIREBASE_SERVICE_ACCOUNT_PATH
    if not path:
        raise ValueError(
            "FIREBASE_SERVICE_ACCOUNT_PATH is not set in environment configuration."
        )

    path = path.strip()
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Firebase service account file not found at: {path}")

    return credentials.Certificate(path)


@lru_cache(maxsize=1)
def _get_options() -> Optional[dict]:
    """
    Optional Firebase initialization options.
    """
    if settings.FIREBASE_PROJECT_ID:
        return {"projectId": settings.FIREBASE_PROJECT_ID}

    return None


def initialize_firebase():
    """
    Initialize Firebase Admin SDK once.
    Safe for multi-import environments.
    """

    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            _get_credentials(),
            options=_get_options(),
        )

    return firebase_admin.get_app()
