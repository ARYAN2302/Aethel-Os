import json
import os
from core.models import Scratchpad

SESSION_DIR = "data/sessions"

def ensure_dir():
    if not os.path.exists(SESSION_DIR):
        os.makedirs(SESSION_DIR)

def save_scratchpad(pad: Scratchpad):
    ensure_dir()
    path = os.path.join(SESSION_DIR, f"{pad.meta.session_id}.json")
    with open(path, "w") as f:
        f.write(pad.model_dump_json(indent=2))

def load_scratchpad(session_id: str) -> Scratchpad:
    ensure_dir()
    path = os.path.join(SESSION_DIR, f"{session_id}.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
            return Scratchpad(**data)
    return Scratchpad(meta={"session_id": session_id})