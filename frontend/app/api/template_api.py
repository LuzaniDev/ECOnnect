from frontend.app.api.client import client


def list_templates(active_only: bool = False) -> list:
    resp = client.get("/api/templates", params={"active_only": active_only})
    resp.raise_for_status()
    return resp.json()


def get_template(template_id: str) -> dict:
    resp = client.get(f"/api/templates/{template_id}")
    resp.raise_for_status()
    return resp.json()


def create_template(data: dict) -> dict:
    resp = client.post("/api/templates", data)
    resp.raise_for_status()
    return resp.json()


def update_template(template_id: str, data: dict) -> dict:
    resp = client.put(f"/api/templates/{template_id}", data)
    resp.raise_for_status()
    return resp.json()


def delete_template(template_id: str) -> dict:
    resp = client.delete(f"/api/templates/{template_id}")
    resp.raise_for_status()
    return resp.json()
