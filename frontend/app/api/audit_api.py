from frontend.app.api.client import client


def list_logs(limit: int = 100, offset: int = 0) -> list:
    resp = client.get("/api/audit/logs", params={"limit": limit, "offset": offset})
    resp.raise_for_status()
    return resp.json()
