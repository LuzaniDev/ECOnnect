from frontend.app.api.client import client


def list_sql_variables(company_code: str | None = None) -> list[dict]:
    params = {}
    if company_code:
        params["company_code"] = company_code
    resp = client.get("/api/sql-variables", params=params)
    resp.raise_for_status()
    return resp.json()


def get_sql_variable(variable_id: str) -> dict:
    resp = client.get(f"/api/sql-variables/{variable_id}")
    resp.raise_for_status()
    return resp.json()


def create_sql_variable(data: dict) -> dict:
    resp = client.post("/api/sql-variables", data)
    resp.raise_for_status()
    return resp.json()


def update_sql_variable(variable_id: str, data: dict) -> dict:
    resp = client.put(f"/api/sql-variables/{variable_id}", data)
    resp.raise_for_status()
    return resp.json()


def delete_sql_variable(variable_id: str) -> dict:
    resp = client.delete(f"/api/sql-variables/{variable_id}")
    resp.raise_for_status()
    return resp.json()
