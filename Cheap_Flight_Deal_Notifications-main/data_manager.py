import json
import os

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")


def _load():
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def _save(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


class DataManager:
    def __init__(self):
        self.data = {}

    def get_data(self):
        store = _load()
        self.data = store["prices"]
        return self.data

    def update_data(self):
        store = _load()
        store["prices"] = self.data
        _save(store)

    def get_emails(self):
        store = _load()
        self.customers_data = store["users"]
        return self.customers_data