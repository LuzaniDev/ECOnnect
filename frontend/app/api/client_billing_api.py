from frontend.app.api.client import client


def list_configs(is_active: bool | None = None) -> list:
    params = {}
    if is_active is not None:
        params["is_active"] = str(is_active).lower()
    resp = client.get("/api/client-billing/configs", params=params)
    resp.raise_for_status()
    return resp.json()


def get_config(config_id: str) -> dict:
    resp = client.get(f"/api/client-billing/configs/{config_id}")
    resp.raise_for_status()
    return resp.json()


def create_config(data: dict) -> dict:
    resp = client.post("/api/client-billing/configs", data)
    resp.raise_for_status()
    return resp.json()


def update_config(config_id: str, data: dict) -> dict:
    resp = client.put(f"/api/client-billing/configs/{config_id}", data)
    resp.raise_for_status()
    return resp.json()


def delete_config(config_id: str) -> dict:
    resp = client.delete(f"/api/client-billing/configs/{config_id}")
    resp.raise_for_status()
    return resp.json()


def trigger_check() -> dict:
    resp = client.post("/api/client-billing/check")
    resp.raise_for_status()
    return resp.json()


def get_client_pendencias(client_code: str) -> dict:
    resp = client.get(f"/api/client-billing/pendencias/{client_code}")
    resp.raise_for_status()
    return resp.json()


def list_tipos_cliente() -> list:
    resp = client.get("/api/client-billing/tipos")
    resp.raise_for_status()
    return resp.json()


def list_clientes(page: int = 0, nome: str = "", page_size: int = 100, tipo: str = "") -> dict:
    params = {"page": page, "page_size": min(page_size, 500)}
    if nome:
        params["nome"] = nome
    if tipo:
        params["tipo"] = tipo
    resp = client.get("/api/client-billing/clientes", params=params)
    resp.raise_for_status()
    return resp.json()


def create_configs_batch(data: list[dict]) -> dict:
    resp = client.post("/api/client-billing/configs/batch", data)
    resp.raise_for_status()
    return resp.json()


def get_batch_status(batch_id: str) -> dict:
    resp = client.get(f"/api/client-billing/batch-status/{batch_id}")
    resp.raise_for_status()
    return resp.json()


def list_groups(status: str | None = None) -> list:
    params = {}
    if status:
        params["status"] = status
    resp = client.get("/api/billing-groups", params=params)
    resp.raise_for_status()
    return resp.json()


def create_group(data: dict) -> dict:
    resp = client.post("/api/billing-groups", data)
    resp.raise_for_status()
    return resp.json()


def update_group(group_id: str, data: dict) -> dict:
    resp = client.put(f"/api/billing-groups/{group_id}", data)
    resp.raise_for_status()
    return resp.json()


def delete_group(group_id: str) -> dict:
    resp = client.delete(f"/api/billing-groups/{group_id}")
    resp.raise_for_status()
    return resp.json()


def register_group(group_id: str) -> dict:
    resp = client.post(f"/api/billing-groups/{group_id}/register")
    resp.raise_for_status()
    return resp.json()


def test_group(group_id: str) -> dict:
    resp = client.post(f"/api/billing-groups/{group_id}/test")
    resp.raise_for_status()
    return resp.json()


def list_billing_templates() -> list:
    resp = client.get("/api/client-billing/templates")
    resp.raise_for_status()
    return resp.json()


def create_billing_template(data: dict) -> dict:
    resp = client.post("/api/client-billing/templates", data)
    resp.raise_for_status()
    return resp.json()


def update_billing_template(template_id: str, data: dict) -> dict:
    resp = client.put(f"/api/client-billing/templates/{template_id}", data)
    resp.raise_for_status()
    return resp.json()


def delete_billing_template(template_id: str) -> dict:
    resp = client.delete(f"/api/client-billing/templates/{template_id}")
    resp.raise_for_status()
    return resp.json()
