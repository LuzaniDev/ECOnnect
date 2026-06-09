from frontend.app.api.client import client


def list_integrations() -> list:
    resp = client.get("/api/integrations")
    resp.raise_for_status()
    return resp.json()


def get_integration(config_id: str) -> dict:
    resp = client.get(f"/api/integrations/{config_id}")
    resp.raise_for_status()
    return resp.json()


def get_integration_by_template(template_id: str) -> dict | None:
    resp = client.get(f"/api/integrations/template/{template_id}")
    resp.raise_for_status()
    data = resp.json()
    return data if data else None


def create_integration(data: dict) -> dict:
    resp = client.post("/api/integrations", data)
    resp.raise_for_status()
    return resp.json()


def update_integration(config_id: str, data: dict) -> dict:
    resp = client.put(f"/api/integrations/{config_id}", data)
    resp.raise_for_status()
    return resp.json()


def delete_integration(config_id: str) -> dict:
    resp = client.delete(f"/api/integrations/{config_id}")
    resp.raise_for_status()
    return resp.json()


def trigger_integration(config_id: str, data: dict = None) -> dict:
    body = data or {}
    resp = client.post(f"/api/integrations/{config_id}/trigger", body)
    resp.raise_for_status()
    return resp.json()
