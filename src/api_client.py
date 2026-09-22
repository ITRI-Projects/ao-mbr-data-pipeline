import os

import requests
from dotenv import load_dotenv

load_dotenv()


class APIClient:
    def __init__(self):
        self.base_url = os.getenv("API_URL")
        self.api_key = os.getenv("API_KEY")

        self.session = requests.Session()

        self.session.headers.update(
            {
                "Content-Type": "application/json",
            }
        )

        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def predict(self, payload):
        response = self.session.post(
            self.base_url,
            json=payload,
            timeout=30,
        )

        response.raise_for_status()

        return response.json()

    def close(self):
        self.session.close()
