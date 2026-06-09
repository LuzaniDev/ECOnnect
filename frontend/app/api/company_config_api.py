from frontend.app.api.client import client


def get_company_config(company_code: str) -> dict:
    resp = client.get(f"/api/company-config/{company_code}")
    resp.raise_for_status()
    return resp.json()


def update_company_config(company_code: str, data: dict) -> dict:
    resp = client.put(f"/api/company-config/{company_code}", data)
    resp.raise_for_status()
    return resp.json()
