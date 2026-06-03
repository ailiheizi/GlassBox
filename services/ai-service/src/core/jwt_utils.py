"""
JWT token generation and validation utilities for service-to-service authentication
"""

import jwt
import time
from typing import Optional
from datetime import datetime, timedelta


def generate_service_token(jwt_secret: str, service_name: str = "ai-service", expiry_hours: int = 24) -> str:
    """
    Generate a JWT token for service-to-service authentication

    Args:
        jwt_secret: The JWT secret key
        service_name: Name of the service
        expiry_hours: Token expiry time in hours

    Returns:
        JWT token string
    """
    now = datetime.utcnow()
    expiry = now + timedelta(hours=expiry_hours)

    payload = {
        "user_id": service_name,
        "username": service_name,
        "service": True,
        "iat": int(now.timestamp()),
        "exp": int(expiry.timestamp()),
    }

    token = jwt.encode(payload, jwt_secret, algorithm="HS256")
    return token
