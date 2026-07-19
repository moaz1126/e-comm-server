import json
import threading
from django.conf import settings

# A lock to prevent concurrent write issues
file_lock = threading.Lock()
DATA_FILE = settings.BASE_DIR / 'config.json'

def get_config_json_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_config_json_data(data):
    with file_lock:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4)
