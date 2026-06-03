"""
安全响应构建器
"""
import os
import json
import hmac
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional


class SecureResponseBuilder:
    """
    安全的响应构建器

    功能：
    1. 过滤敏感信息
    2. 添加安全标记
    3. 生成响应签名
    """

    def __init__(self, user_id: str, request_id: str):
        self._user_id = user_id
        self._request_id = request_id
        self._secret = os.environ.get("RESPONSE_SIGN_SECRET", "default-secret")

    def build_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """构建安全的响应"""
        # 1. 过滤敏感信息
        filtered_data = self._filter_sensitive(data)

        # 2. 添加安全标记
        response = {
            "data": filtered_data,
            "_security": {
                "user_id": self._user_id,
                "request_id": self._request_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
        }

        return response

    def _filter_sensitive(self, data: Any) -> Any:
        """过滤敏感信息"""
        sensitive_keys = {"password", "password_hash", "secret", "token", "api_key"}

        if isinstance(data, dict):
            filtered = {}
            for key, value in data.items():
                # 过滤其他用户的ID
                if key == "user_id" and value != self._user_id:
                    continue
                # 过滤敏感字段
                if key.lower() in sensitive_keys:
                    continue
                filtered[key] = self._filter_sensitive(value)
            return filtered
        elif isinstance(data, list):
            return [self._filter_sensitive(item) for item in data]
        return data

    def _sign(self, data: Dict[str, Any]) -> str:
        """生成响应签名"""
        message = json.dumps(data, sort_keys=True)
        return hmac.new(
            self._secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
