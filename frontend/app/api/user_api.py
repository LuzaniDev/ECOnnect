from frontend.app.api.client import client


def list_users() -> list:
    resp = client.get("/api/users")
    resp.raise_for_status()
    return resp.json()


def update_user(user_id: str, data: dict) -> dict:
    resp = client.put(f"/api/users/{user_id}", data)
    resp.raise_for_status()
    return resp.json()


def delete_user(user_id: str) -> dict:
    resp = client.delete(f"/api/users/{user_id}")
    resp.raise_for_status()
    return resp.json()
