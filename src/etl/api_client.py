import os
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv()


class APIClient:
    """Submit one reading at a time using the import blueprint."""

    def __init__(self):
        settings = {}
        for name in ("API_URL", "API_USER", "API_TOKEN"):
            settings[name] = os.getenv(name)
            if not settings[name]:
                raise ValueError(f"Missing required environment setting: {name}")
        self.base_url = settings["API_URL"]
        if urlparse(self.base_url).scheme != "https" or not urlparse(self.base_url).netloc:
            raise ValueError("API_URL must be an absolute HTTPS URL")
        self.user = settings["API_USER"]
        self.token = settings["API_TOKEN"]
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json", "Accept": "application/json"})

    def submit_reading(self, payload):
        body = {**payload, "user": self.user, "token": self.token}
        # No automatic retries or redirects: POST delivery may already have occurred.
        with self.session.post(self.base_url, json=body, timeout=30, allow_redirects=False) as response:
            return response.status_code

    def close(self):
        self.session.close()
