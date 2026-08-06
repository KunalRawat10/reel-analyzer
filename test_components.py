#!/usr/bin/env python3
"""Quick component tests without Instagram or heavy models."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from parser import regex

def test_regex():
    text = "Check out https://github.com/user/repo and email me at test@example.com or @twitter. #python"
    resources = regex.extract_resources(text)
    assert "https://github.com/user/repo" in resources.get("urls", [])
    assert "github.com/user/repo" in resources.get("github_repos", [])
    assert "test@example.com" in resources.get("emails", [])
    assert "#python" in resources.get("hashtags", [])
    print("[PASS] regex parser")

def test_merge():
    from parser import merge
    combined = merge.merge_data("hello world", ["text line"], "some caption", {"urls": ["https://example.com"]})
    assert "TRANSCRIPT" in combined
    assert "https://example.com" in combined
    print("[PASS] merge")

def test_config():
    assert config.BASE_DIR.exists()
    assert (config.BASE_DIR / "output").exists()
    print("[PASS] config")

if __name__ == "__main__":
    test_config()
    test_regex()
    test_merge()
