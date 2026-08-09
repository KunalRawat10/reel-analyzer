"""Mentioned resource extraction from existing summarizer output."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Verified official-resource mapping (curated, no fabrication)
# Only resources with high-confidence official URLs are included.
# Aliases are noted explicitly (e.g., Codium -> Qodo).
OFFICIAL_RESOURCES = {
    "cursor": "https://cursor.com/",
    "codium": "https://qodo.ai/",
    "tabnine": "https://www.tabnine.com/",
    "tab9": "https://www.tabnine.com/",
    "react": "https://react.dev/",
    "node.js": "https://nodejs.org/",
    "nodejs": "https://nodejs.org/",
    "openai": "https://openai.com/",
    "anthropic": "https://www.anthropic.com/",
    "claude": "https://www.anthropic.com/",
}

# Alias / resolution notes (used when official URL is set but original name differs)
ALIAS_NOTES = {
    "codium": "Formerly Codium; now known as Qodo",
    "qodo": "Previously Codium",
    "cursor ai": None,
    "tab nine": "Alias: Tabnine",
    "tab9": "Alias: Tabnine (shortened form)",
    "react.js": None,
    "node": "Alias: Node.js",
    "claude": "Product of Anthropic",
}

GENERIC_FILTER = {
    "tool", "software", "ai", "coding", "website", "app", "program",
    "browser", "extension", "video", "project", "code", "system",
    "platform", "service", "product", "solution",
}


def _is_generic_word(name: str) -> bool:
    cleaned = name.lower().strip()
    # Remove common punctuation
    cleaned = cleaned.replace(".", "").replace(",", "").replace("-", " ")
    words = cleaned.split()
    # Filter out pure single letters, very short tokens, or tokens that are exactly generic words
    for w in words:
        if w in GENERIC_FILTER:
            return True
    # Also reject names that are mostly numbers or very short
    if len(name.strip()) < 2:
        return True
    return False


def extract_mentioned_resources(summary_data: dict) -> list:
    """Extract mentioned resources from existing structured summary output.

    Reuses summarize.summarize() results without any additional LLM call.
    Official URLs are intentionally set to None (null) to avoid fabrication.
    PRIMARY SOURCE: tools_mentioned is treated as the authoritative list for mentioned tools.
    """
    mentioned = []
    seen = set()

    # PRIMARY SOURCE: structured tools_mentioned from summary
    # Processed independently to ensure nothing from this authoritative list is lost.
    primary_items = summary_data.get("tools_mentioned") if isinstance(summary_data, dict) else None
    if isinstance(primary_items, list):
        for item in primary_items:
            if isinstance(item, str) and item.strip():
                name = item.strip()
                # Skip direct URLs
                if name.startswith(("http://", "https://", "www.")):
                    continue
                # Skip direct repo/video links handled by regex
                if "/" in name and any(d in name for d in ["github.com", "youtube.com", "youtu.be"]):
                    continue
                # Skip generic words
                if _is_generic_word(name):
                    continue
                # Skip duplicates
                key_for_dup = (name.lower(), "tool")
                if key_for_dup in seen:
                    continue
                seen.add(key_for_dup)
                # Resolve official URL using verified curated mapping
                official_url = None
                resolution_status = "unresolved"
                resolution_note = None
                # Direct key lookup (normalized)
                lookup_name = name.lower().strip()
                matched_url = None
                matched_note = None
                if lookup_name in OFFICIAL_RESOURCES:
                    matched_url = OFFICIAL_RESOURCES[lookup_name]
                    matched_note = ALIAS_NOTES.get(lookup_name)
                else:
                    # Try alias or variant lookup against official resource keys
                    # (e.g., "cursor ai" should match "cursor"; "node" should match "node.js")
                    for key, url_val in OFFICIAL_RESOURCES.items():
                        if lookup_name.startswith(key.lower()) or key.lower().startswith(lookup_name):
                            if lookup_name == key.lower() or lookup_name.startswith(key.lower() + " ") or key.lower().startswith(lookup_name + " "):
                                matched_url = url_val
                                matched_note = ALIAS_NOTES.get(key) or ALIAS_NOTES.get(lookup_name)
                                break
                if matched_url is not None:
                    official_url = matched_url
                    resolution_status = "official"
                    if matched_note is not None:
                        resolution_note = matched_note

                mentioned.append({
                    "name": name,
                    "type": "tool",
                    "official_url": official_url,
                    "source": "summary",
                    "resolution_status": resolution_status,
                    "resolution_note": resolution_note,
                })

    # Supplementary sources: companies, frameworks, and public resources
    # These supplement the primary tool list but do not replace it.
    supplementary_mapping = [
        ("companies_mentioned", "company"),
        ("frameworks_mentioned", "framework"),
        ("public_resources", "resource"),
    ]
    for key, resource_type in supplementary_mapping:
        items = summary_data.get(key) if isinstance(summary_data, dict) else None
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, str) or not item.strip():
                    continue
                name = item.strip()
                # Skip direct URLs
                if name.startswith(("http://", "https://", "www.")):
                    continue
                # Skip direct repo/video links handled by regex
                if "/" in name and any(d in name for d in ["github.com", "youtube.com", "youtu.be"]):
                    continue
                # Skip generic words
                if _is_generic_word(name):
                    continue
                # Skip duplicates (same name + same type; different type allowed for supplementary)
                key_for_dup = (name.lower(), resource_type)
                if key_for_dup in seen:
                    continue
                seen.add(key_for_dup)
                # Resolve official URL using verified curated mapping
                official_url = None
                resolution_status = "unresolved"
                resolution_note = None
                lookup_name = name.lower().strip()
                matched_url = None
                matched_note = None
                if lookup_name in OFFICIAL_RESOURCES:
                    matched_url = OFFICIAL_RESOURCES[lookup_name]
                    matched_note = ALIAS_NOTES.get(lookup_name)
                else:
                    # Try alias or variant lookup against official resource keys
                    for key, url_val in OFFICIAL_RESOURCES.items():
                        if lookup_name.startswith(key.lower()) or key.lower().startswith(lookup_name):
                            if lookup_name == key.lower() or lookup_name.startswith(key.lower() + " ") or key.lower().startswith(lookup_name + " "):
                                matched_url = url_val
                                matched_note = ALIAS_NOTES.get(key) or ALIAS_NOTES.get(lookup_name)
                                break
                if matched_url is not None:
                    official_url = matched_url
                    resolution_status = "official"
                    if matched_note is not None:
                        resolution_note = matched_note

                mentioned.append({
                    "name": name,
                    "type": resource_type,
                    "official_url": official_url,
                    "source": "summary",
                    "resolution_status": resolution_status,
                    "resolution_note": resolution_note,
                })

    # Sort by type then name for consistent output
    mentioned.sort(key=lambda x: (x["type"], x["name"]))
    return mentioned
