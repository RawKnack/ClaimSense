import json
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings


@lru_cache
def load_policy_terms() -> dict:
    path = get_settings().policy_terms_path
    with path.open(encoding="utf-8") as f:
        return json.load(f)
