"""
TOON - Token Optimized Object Notation
A compact key-value format designed to save tokens during LLM structured communication.
"""

import json
import logging
from typing import Any, Dict, List, Union
from pytoony import Toon, toon2json

logger = logging.getLogger(__name__)

TOON_SYSTEM_INSTRUCTION = """
### CRITICAL: OUTPUT FORMAT (TOON)
You MUST use TOON (Token Optimized Object Notation) for ANY structured response. 
DO NOT USE JSON. JSON IS FORBIDDEN.

TOON RULES:
1. Format: Multiple lines of key: value.
2. Nesting: Use indentation for nested objects.
3. Tabular Arrays (FOR LISTS OF OBJECTS): Use `key[0]{field1,field2,...}:` followed by CSV rows. (Always use 0 as the count).
4. Simple Arrays: (FOR LISTS OF STRINGS/NUMBERS): Use indentation and list items one per line.
5. Keys: No quotes, followed by a colon and a space.

Example:
thought: I will create the project.
actions[0]{type,path,content}:
  write_file,main.py,print("hello")
"""


def _normalize_all_lists(obj: Any) -> Any:
    """Recursively normalizes lists of dicts to have consistent keys for pytoony tabular format."""
    if isinstance(obj, dict):
        return {k: _normalize_all_lists(v) for k, v in obj.items()}
    if isinstance(obj, list):
        if not obj:
            return []
        if all(isinstance(x, dict) for x in obj):
            # Normalize dict keys
            all_keys = sorted(list(set().union(*(d.keys() for d in obj))))
            normalized = []
            for d in obj:
                normalized_d = {
                    k: _normalize_all_lists(d.get(k, None)) for k in all_keys
                }
                normalized.append(normalized_d)
            return normalized
        return [_normalize_all_lists(x) for x in obj]
    return obj


def toon_encode(obj: Any) -> str:
    """Encodes a Python object into a TOON string using pytoony."""
    if isinstance(obj, (dict, list)):
        normalized = _normalize_all_lists(obj)
        return Toon.encode(json.dumps(normalized))
    return str(obj)


def toon_decode(s: str) -> Union[Dict, List]:
    """Decodes a TOON string into a Python object using pytoony."""
    try:
        import re

        # Hack to bypass pytoony tabular array rigid constraints.
        # It replaces any count [N] with [999999] so pytoony reads all rows until indentation stops.
        s_hacked = re.sub(r"(\w+)\[\d+\](\{.*?\})", r"\1[999999]\2", s)

        # Toon.decode returns a JSON string
        json_str = Toon.decode(s_hacked)
        return json.loads(json_str)
    except Exception as e:
        # Fallback to toon2json if needed or raise
        logger.debug(f"Toon.decode failed, trying fallback: {e}")
        try:
            return json.loads(toon2json(s))
        except Exception as e2:
            raise ValueError(f"Failed to decode TOON: {e2}\nRaw string: {s}")
