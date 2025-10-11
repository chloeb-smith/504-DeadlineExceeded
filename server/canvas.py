import requests


def canvas_get(base_url: str, token: str, path: str, params=None):
    url = f"{base_url}{path}"
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()
