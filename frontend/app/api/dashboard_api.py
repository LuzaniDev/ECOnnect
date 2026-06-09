from frontend.app.api.client import client


def get_dashboard_summary() -> dict:
    resp = client.get("/api/dashboard/summary")
    resp.raise_for_status()
    return resp.json()
