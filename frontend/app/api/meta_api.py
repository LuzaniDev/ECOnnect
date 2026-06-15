from frontend.app.api.client import client


def get_credentials() -> dict | None:
    resp = client.get("/api/meta/credentials")
    if resp.status_code == 200:
        return resp.json()
    return None


def save_credentials(data: dict) -> dict:
    resp = client.post("/api/meta/credentials", data)
    resp.raise_for_status()
    return resp.json()


def test_connection(data: dict) -> dict:
    resp = client.post("/api/meta/verify", data)
    resp.raise_for_status()
    return resp.json()


def sync_template(template_id: str) -> dict:
    resp = client.post("/api/meta/templates/sync", {"template_id": template_id})
    resp.raise_for_status()
    return resp.json()


def check_template_status(template_id: str) -> dict:
    resp = client.get(f"/api/meta/templates/{template_id}/status")
    resp.raise_for_status()
    return resp.json()


def send_message(data: dict) -> dict:
    resp = client.post("/api/meta/send", data)
    resp.raise_for_status()
    return resp.json()


def list_messages(phone: str | None = None) -> list:
    params = {}
    if phone:
        params["phone"] = phone
    resp = client.get("/api/meta/messages", params=params)
    resp.raise_for_status()
    return resp.json()
