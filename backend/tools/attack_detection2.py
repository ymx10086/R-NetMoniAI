from pathlib import Path
from typing import Union

from secretKeys import OPENROUTER_API_KEY
from tools.attack_detection3 import detect_attack_func as detect_attack_func_v3


def detect_attack_func(path: Union[str, Path], api_key: str = "") -> str:
    """Backward-compatible wrapper using OpenRouter-backed detector."""
    effective_key = api_key or OPENROUTER_API_KEY
    return detect_attack_func_v3(path, effective_key)
