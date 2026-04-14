import hashlib
import os
import uuid
from collections.abc import Mapping
from urllib.parse import unquote, urlencode

import httpx
import jwt


class UpbitClient:
    def __init__(self, access_key: str | None = None, secret_key: str | None = None, base_url: str = "https://api.upbit.com"):
        self.access_key = access_key or os.getenv("UPBIT_ACCESS_API_KEY", "")
        self.secret_key = secret_key or os.getenv("UPBIT_SECRET_API_KEY", "")
        self.base_url = base_url.rstrip("/")

    def configured(self) -> bool:
        return bool(self.access_key and self.secret_key)

    def get_balances(self) -> list[dict]:
        return self._request("GET", "/v1/accounts")

    def get_markets(self, is_details: bool = False) -> list[dict]:
        return self._request("GET", "/v1/market/all", params={"isDetails": str(is_details).lower()}, auth=False)

    def get_ticker(self, markets: list[str]) -> list[dict]:
        if not markets:
            return []
        # Upbit accepts comma-separated markets in a single request (up to ~100)
        batch_size = 50
        payload = []
        for i in range(0, len(markets), batch_size):
            batch = markets[i:i + batch_size]
            try:
                rows = self._request("GET", "/v1/ticker", params={"markets": ",".join(batch)}, auth=False)
                if isinstance(rows, list):
                    payload.extend(rows)
            except Exception:
                continue
        return payload

    def create_limit_order(self, market: str, side: str, volume: str, price: str, ord_type: str = "limit") -> dict:
        return self._request(
            "POST",
            "/v1/orders",
            params={
                "market": market,
                "side": side,
                "volume": volume,
                "price": price,
                "ord_type": ord_type,
            },
        )

    def get_order(self, uuid_value: str) -> dict:
        return self._request("GET", "/v1/order", params={"uuid": uuid_value})

    def _request(self, method: str, path: str, params: dict | None = None, auth: bool = True) -> list[dict] | dict:
        headers = {"accept": "application/json"}
        if auth:
            if not self.configured():
                raise ValueError("Upbit credentials are not configured")
            headers["Authorization"] = f"Bearer {self._create_jwt(params or {})}"
        request_kwargs = {
            "headers": headers,
            "timeout": 10.0,
        }
        if method.upper() == "GET":
            request_kwargs["params"] = params
        elif params:
            request_kwargs["data"] = params

        response = httpx.request(
            method,
            f"{self.base_url}{path}",
            **request_kwargs,
        )
        response.raise_for_status()
        return response.json()

    def _create_jwt(self, params: dict) -> str:
        payload = {
            "access_key": self.access_key,
            "nonce": str(uuid.uuid4()),
        }
        if params:
            query_string = self._build_query_string(params)
            payload["query_hash"] = hashlib.sha512(query_string.encode()).hexdigest()
            payload["query_hash_alg"] = "SHA512"
        return self._encode_hs256(payload, self.secret_key)

    def _build_query_string(self, params: dict) -> str:
        data = params if isinstance(params, Mapping) else params
        return unquote(urlencode(data, doseq=True))

    def _encode_hs256(self, payload: dict, secret: str) -> str:
        token = jwt.encode(payload, secret, algorithm="HS512")
        return token if isinstance(token, str) else token.decode("utf-8")
