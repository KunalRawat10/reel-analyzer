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

def test_mentioned_resources():
    from parser import mentioned_resources
    # Direct URL should NOT become mentioned resource
    summary_direct = {"tools_mentioned": ["https://cursor.com"], "companies_mentioned": []}
    mentioned = mentioned_resources.extract_mentioned_resources(summary_direct)
    assert len(mentioned) == 0, f"Expected 0 mentioned resources for URL input, got {mentioned}"

    # Tool mentioned without URL should become mentioned resource
    summary_tool = {
        "tools_mentioned": ["Cursor", "CodiumAI", "tool", "software"],
        "companies_mentioned": ["OpenAI"],
        "frameworks_mentioned": ["React", "AI"],
        "public_resources": ["https://github.com/user/repo"],
    }
    mentioned = mentioned_resources.extract_mentioned_resources(summary_tool)
    names = {m["name"] for m in mentioned}
    assert "Cursor" in names
    assert "CodiumAI" in names
    assert "OpenAI" in names
    assert "React" in names
    # Generic words filtered out
    assert "tool" not in names
    assert "software" not in names
    # URLs skipped
    assert "https://github.com/user/repo" not in names
    print("[PASS] mentioned_resources")

def test_resource_resolution():
    from parser import mentioned_resources
    # Known resources resolve to official URLs
    summary_known = {
        "tools_mentioned": ["Cursor", "Codium"],
        "companies_mentioned": ["Anthropic"],
    }
    mentioned = mentioned_resources.extract_mentioned_resources(summary_known)
    cursor = [m for m in mentioned if m["name"] == "Cursor"]
    assert cursor, "Cursor should be present"
    assert cursor[0]["official_url"] == "https://cursor.com/", f"Cursor URL incorrect: {cursor[0].get('official_url')}"
    assert cursor[0]["resolution_status"] == "official", f"Cursor status incorrect: {cursor[0].get('resolution_status')}"

    codium = [m for m in mentioned if m["name"] == "Codium"]
    assert codium, "Codium should be present"
    assert codium[0]["official_url"] == "https://qodo.ai/", f"Codium URL incorrect: {codium[0].get('official_url')}"
    assert codium[0]["resolution_status"] == "official", f"Codium status incorrect: {codium[0].get('resolution_status')}"
    assert "Qodo" in (codium[0].get("resolution_note") or ""), f"Codium alias note missing: {codium[0].get('resolution_note')}"

    anthropic = [m for m in mentioned if m["name"] == "Anthropic"]
    assert anthropic and anthropic[0]["official_url"] == "https://www.anthropic.com/", "Anthropic should resolve"

    # Unknown resource stays unresolved (no fabricated URL)
    summary_unknown = {"tools_mentioned": ["SomeUnknownTool", "Cursor"]}
    mentioned_unknown = mentioned_resources.extract_mentioned_resources(summary_unknown)
    unknown_items = [m for m in mentioned_unknown if m["name"] == "SomeUnknownTool"]
    assert unknown_items, "Unknown tool should appear"
    assert unknown_items[0]["official_url"] is None, "Unknown resource must not have fabricated URL"
    assert unknown_items[0]["resolution_status"] == "unresolved", "Unknown resource must have unresolved status"

    # Direct URLs excluded from mentioned resources
    summary_url = {"tools_mentioned": ["https://cursor.com/"]}
    mentioned_url = mentioned_resources.extract_mentioned_resources(summary_url)
    assert len(mentioned_url) == 0, "Direct URL should not become mentioned resource"

    # No duplicates for same resource with different casing
    summary_dup = {"tools_mentioned": ["Cursor", "cursor", "CURSOR"]}
    mentioned_dup = mentioned_resources.extract_mentioned_resources(summary_dup)
    cursor_items = [m for m in mentioned_dup if m["name"] == "Cursor" or m["name"] == "cursor" or m["name"] == "CURSOR"]
    # After normalization and dedup, only one entry should remain (with original first-cased form)
    cursor_count = sum(1 for m in mentioned_dup if m["name"].lower() == "cursor")
    assert cursor_count == 1, f"Cursor duplicate count incorrect: {cursor_count}"

    print("[PASS] resource_resolution")

if __name__ == "__main__":
    test_config()
    test_regex()
    test_merge()
    test_mentioned_resources()
    test_resource_resolution()
