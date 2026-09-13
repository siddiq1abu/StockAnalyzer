"""Local credential storage and optional broker/AI API clients."""
import json
import os

import requests


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, ".credentials.json")
ANGEL_CREDENTIALS_FILE = os.path.join(BASE_DIR, ".angel_one_credentials.json")


def load_credentials():
    data = {}
    try:
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
            if isinstance(loaded, dict):
                data = loaded
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    try:
        with open(ANGEL_CREDENTIALS_FILE, "r", encoding="utf-8") as handle:
            angel = json.load(handle)
            if isinstance(angel, dict) and not angel.get("mpin") and angel.get("pin"):
                angel["mpin"] = angel["pin"]
            required = ("api_key", "totp", "mpin", "client_id")
            if (isinstance(angel, dict)
                    and all(angel.get(key) for key in required)
                    and not any(str(angel[key]).startswith("paste-your-") for key in required)):
                data["angel_one"] = angel
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return data


def save_credentials(data):
    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as handle:
        json.dump({"groq": data.get("groq", {})}, handle, indent=2)
    try:
        os.chmod(CREDENTIALS_FILE, 0o600)
    except OSError:
        pass
    with open(ANGEL_CREDENTIALS_FILE, "w", encoding="utf-8") as handle:
        json.dump(data.get("angel_one", {}), handle, indent=2)
    try:
        os.chmod(ANGEL_CREDENTIALS_FILE, 0o600)
    except OSError:
        pass


def mask(value):
    if not value:
        return ""
    return "*" * max(0, len(value) - 4) + value[-4:]


def credential_status():
    data = load_credentials()
    groq = data.get("groq", {})
    angel = data.get("angel_one", {})
    return {
        "groq": {"configured": bool(groq.get("api_key")), "api_key": mask(groq.get("api_key"))},
        "angel_one": {
            "configured": all(angel.get(key) for key in ("api_key", "client_id", "mpin", "totp")),
            "api_key": mask(angel.get("api_key")),
            "client_id": mask(angel.get("client_id")),
            "totp": "configured" if angel.get("totp") else "",
            "mpin": "configured" if angel.get("mpin") else "",
        },
    }


def test_groq():
    api_key = load_credentials().get("groq", {}).get("api_key")
    if not api_key:
        raise ValueError("Groq API key is not configured")
    response = requests.get(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=15,
    )
    response.raise_for_status()
    return "Groq connection successful"


def groq_chat(prompt):
    api_key = load_credentials().get("groq", {}).get("api_key")
    if not api_key:
        raise ValueError("Groq API key is not configured")
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def test_angel_one():
    credentials = load_credentials().get("angel_one", {})
    required = ("api_key", "client_id", "mpin", "totp")
    if not all(credentials.get(key) for key in required):
        raise ValueError("Angel One API key, client ID, MPIN and TOTP are required")

    try:
        import pyotp
        from SmartApi import SmartConnect
    except ImportError as exc:
        raise RuntimeError("Install the SmartAPI dependencies before testing Angel One") from exc

    client = SmartConnect(api_key=credentials["api_key"])
    session = client.generateSession(
        credentials["client_id"],
        credentials["mpin"],
        pyotp.TOTP(credentials["totp"]).now(),
    )
    if not session or not session.get("status"):
        message = session.get("message", "Angel One login failed") if session else "Angel One login failed"
        raise RuntimeError(message)
    return "Angel One login successful"