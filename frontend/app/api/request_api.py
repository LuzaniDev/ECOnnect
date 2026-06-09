from frontend.app.api.client import client


def list_requests(status: str | None = None) -> list:
    params = {}
    if status:
        params["status"] = status
    resp = client.get("/api/requests", params=params)
    resp.raise_for_status()
    return resp.json()


def get_request(request_id: str) -> dict:
    resp = client.get(f"/api/requests/{request_id}")
    resp.raise_for_status()
    return resp.json()


def create_request(data: dict) -> dict:
    resp = client.post("/api/requests", data)
    resp.raise_for_status()
    return resp.json()


def send_request(request_id: str) -> dict:
    resp = client.put(f"/api/requests/{request_id}/send")
    resp.raise_for_status()
    return resp.json()


def cancel_request(request_id: str) -> dict:
    resp = client.put(f"/api/requests/{request_id}/cancel")
    resp.raise_for_status()
    return resp.json()


def get_history_by_phone(phone: str) -> list:
    resp = client.get(f"/api/requests/history/{phone}")
    resp.raise_for_status()
    return resp.json()


def update_request_link(request_id: str, link: str | None) -> dict:
    resp = client.put(f"/api/requests/{request_id}/link", {"link": link})
    resp.raise_for_status()
    return resp.json()
