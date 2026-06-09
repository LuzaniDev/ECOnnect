from frontend.app.api.client import client


def login(username: str, password: str) -> dict:
    resp = client.post("/api/auth/login", {"username": username, "password": password})
    resp.raise_for_status()
    return resp.json()


def register(username: str, email: str, password: str) -> dict:
    resp = client.post(
        "/api/auth/register",
        {"username": username, "email": email, "password": password},
    )
    resp.raise_for_status()
    return resp.json()


def eco_login(eco_usuario: str, eco_empresa: str, role: str) -> dict:
    resp = client.post(
        "/api/auth/eco-login",
        {"eco_usuario": eco_usuario, "eco_empresa": eco_empresa, "role": role},
    )
    resp.raise_for_status()
    return resp.json()


def get_me() -> dict:
    resp = client.get("/api/auth/me")
    resp.raise_for_status()
    return resp.json()
