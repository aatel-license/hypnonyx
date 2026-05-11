import pytest
import json
from core.toon import toon_encode, toon_decode, _normalize_all_lists

def test_normalize_all_lists_dict():
    data = {"a": 1, "b": {"c": 2}}
    assert _normalize_all_lists(data) == data

def test_normalize_all_lists_list_of_dicts():
    data = [
        {"a": 1, "b": 2},
        {"a": 3, "c": 4}
    ]
    # Should normalize keys to ["a", "b", "c"] and fill missing with None
    expected = [
        {"a": 1, "b": 2, "c": None},
        {"a": 3, "b": None, "c": 4}
    ]
    assert _normalize_all_lists(data) == expected

def test_normalize_all_lists_nested_list():
    data = {"list": [{"x": 1}, {"y": 2}]}
    expected = {"list": [{"x": 1, "y": None}, {"x": None, "y": 2}]}
    assert _normalize_all_lists(data) == expected

def test_toon_encode_simple():
    data = {"key": "value"}
    encoded = toon_encode(data)
    assert "key: value" in encoded

def test_toon_encode_list():
    data = [{"name": "Alice"}, {"name": "Bob"}]
    encoded = toon_encode(data)
    assert "name" in encoded
    assert "Alice" in encoded
    assert "Bob" in encoded

def test_toon_decode_simple():
    toon_str = "key: value"
    decoded = toon_decode(toon_str)
    assert decoded == {"key": "value"}

def test_toon_decode_complex():
    # Example from docstring
    toon_str = """thought: I will create the project.
actions[0]{type,path,content}:
  write_file,main.py,print("hello")"""
    decoded = toon_decode(toon_str)
    assert decoded["thought"] == "I will create the project."
    assert decoded["actions"][0]["type"] == "write_file"
    assert decoded["actions"][0]["path"] == "main.py"

def test_toon_decode_error():
    # Pass something that is definitely not TOON and will fail both decoders
    from unittest.mock import patch
    with patch("pytoony.Toon.decode", side_effect=Exception("Toon failed")):
        with patch("core.toon.toon2json", side_effect=Exception("Both failed")):
            with pytest.raises(ValueError, match="Failed to decode TOON"):
                toon_decode("totally broken")

def test_toon_decode_fallback(caplog):
    import logging
    caplog.set_level(logging.DEBUG)
    # A string that might trigger an error in Toon.decode but be handled by toon2json
    # Or just mock Toon.decode to fail
    from unittest.mock import patch
    with patch("pytoony.Toon.decode", side_effect=Exception("Toon decode failed")):
        result = toon_decode("key: value")
        assert result == {"key": "value"}
        assert "Toon.decode failed, trying fallback" in caplog.text

def test_toon_decode_hack():
    # Test the regex hack: s_hacked = re.sub(r"(\w+)\[\d+\](\{.*?\})", r"\1[999999]\2", s)
    toon_str = "actions[0]{type,path}:"
    # We can't easily see s_hacked, but we can verify it still works
    decoded = toon_decode(toon_str)
    # If it works, it means the hack didn't break things or helped
    assert "actions" in decoded

def test_normalize_all_lists_empty():
    assert _normalize_all_lists([]) == []

def test_normalize_all_lists_non_dict_list():
    assert _normalize_all_lists([1, 2, 3]) == [1, 2, 3]

def test_toon_encode_non_dict_list():
    assert toon_encode("just a string") == "just a string"
    assert toon_encode(123) == "123"
