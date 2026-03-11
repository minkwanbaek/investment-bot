import base64
import hashlib
import hmac
import json
import os
import uuid
from urllib.parse import urlencode

import httpx


class UpbitClient:
    def __init__(self, access_key: str | None = None, secret_key: str | None = None, base_url: str = "https://api.upbit.com"):
        self.access_key = access_key or os.getenv("UPBIT_ACCESS_KEY", "")
        self.secret_key = secret_key or os.getenv("UPBIT_SECRET_KEY", "")
        self.base_url = base_url.rstrip("/")

    def configured(self) -> bool:
        return bool(self.access_key and self.secret_key)

    def get_balances(self) -> list[dict]:
        return self._request("GET", "/v1/accounts")

    def get_markets(self, is_details: bool = False) -> list[dict]:
        return self._request("GET", "/v1/market/all", params={"isDetails": str(is_details).lower()}, auth=False)

    def _request(self, method: str, path: str, params: dict | None = None, auth: bool = True) -> list[dict] | dict:
        headers = {"accept": "application/json"}
        if auth:
            if not self.configured():
                raise ValueError("Upbit credentials are not configured")
            headers["Authorization"] = f"Bearer {self._create_jwt(params or {})}"
        response = httpx.request(
            method,
            f"{self.base_url}{path}",
            params=params,
            headers=headers,
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()

    def _create_jwt(self, params: dict) -> str:
        payload = {
            "access_key": self.access_key,
            "nonce": str(uuid.uuid4()),
        }
        if params:
            query_string = urlencode(params, doseq=True)
            payload["query_hash"] = hashlib.sha512(query_string.encode()).hexdigest()
            payload["query_hash_alg"] = "SHA512"
        return self._encode_hs256(payload, self.secret_key)

    def _encode_hs256(self, payload: dict, secret: str) -> str:
        header = {"alg": "HS256", "typ": "JWT"}

        def b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

        signing_input = f"{b64url(json.dumps(header, separators=(',', ':')).encode())}.{b64url(json.dumps(payload, separators=(',', ':')).encode())}"
        signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
        return f"{signing_input}.{b64url(signature)}"
