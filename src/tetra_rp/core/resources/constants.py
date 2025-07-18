import os

CONSOLE_BASE_URL = os.environ.get("CONSOLE_BASE_URL", "https://console.runpod.io")
CONSOLE_URL = f"{CONSOLE_BASE_URL}/serverless/user/endpoint/%s"
