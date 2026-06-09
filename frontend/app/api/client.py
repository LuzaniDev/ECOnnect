import httpx
from frontend.app.config import settings


class ApiClient:
    def __init__(self):
        self.base_url = settings.API_URL
        self._token: str | None = None
        self._client = httpx.Client(timeout=30, follow_redirects=True)

    def set_token(self, token: str):
        self._token = token

    def clear_token(self):
        self._token = None

    @property
    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def get(self, path: str, params: dict | None = None) -> httpx.Response:
        return self._client.get(
            f"{self.base_url}{path}",
            headers=self._headers,
            params=params,
        )

    def post(self, path: str, data: dict | None = None) -> httpx.Response:
        return self._client.post(
            f"{self.base_url}{path}", json=data, headers=self._headers
        )

    def put(self, path: str, data: dict | None = None) -> httpx.Response:
        return self._client.put(
            f"{self.base_url}{path}", json=data, headers=self._headers
        )

    def delete(self, path: str) -> httpx.Response:
        return self._client.delete(f"{self.base_url}{path}", headers=self._headers)


client = ApiClient()
