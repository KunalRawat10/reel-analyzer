"""Save results as Markdown."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pathlib import Path
import config


def save_md(data: dict, reel_id: str = None) -> Path:
    if reel_id is None:
        import uuid
        reel_id = str(uuid.uuid4())[:8]
    path = config.OUTPUT_DIR / f"reel_{reel_id}.md"
    lines = []
    lines.append(f"# Reel Analysis: {reel_id}")
    lines.append("")
    summary_dict = data.get("summary", {})
    if isinstance(summary_dict, dict):
        summary_text = summary_dict.get("short_summary", summary_dict.get("summary", summary_dict.get("Short summary", str(summary_dict))))
    else:
        summary_text = str(summary_dict)
    lines.append(f"## Summary\n{summary_text}\n")
    lines.append("## Key Concepts")
    def get_from_summary(key, alt_key=None):
        summary_dict = data.get("summary", {})
        if isinstance(summary_dict, dict):
            for k in [key, alt_key, key.lower(), (alt_key or key).lower()]:
                if k and k in summary_dict:
                    return summary_dict[k]
        return data.get(key, data.get(alt_key, []))
    key_concepts = get_from_summary("key_concepts", "Key concepts")
    if isinstance(key_concepts, list):
        for concept in key_concepts:
            lines.append(f"- {concept}")
    elif isinstance(key_concepts, str) and key_concepts:
        lines.append(f"- {key_concepts}")
    lines.append("")
    lines.append("## Tools / Technologies")
    tools = get_from_summary("important_tools", "Important tools")
    if isinstance(tools, list):
        for tool in tools:
            lines.append(f"- {tool}")
    elif isinstance(tools, str) and tools:
        lines.append(f"- {tools}")
    lines.append("")
    lines.append("## Resources")
    resources = data.get("resources", {})
    for category, items in resources.items():
        if items:
            lines.append(f"### {category.replace('_', ' ').title()}")
            for item in items:
                lines.append(f"- {item}")
    lines.append("")
    lines.append("## Action Items")
    actions = get_from_summary("action_items", "Action items")
    if isinstance(actions, list):
        for action in actions:
            lines.append(f"- {action}")
    elif isinstance(actions, str) and actions:
        lines.append(f"- {actions}")
    lines.append("")
    lines.append("## Tags")
    tags = get_from_summary("tags", "Tags")
    if isinstance(tags, list):
        for tag in tags:
            lines.append(f"- #{tag}")
    elif isinstance(tags, str) and tags:
        lines.append(f"- #{tags}")
    lines.append("")
    lines.append("---")
    lines.append(f"Transcript snippet: {data.get('transcript_text', '')[:500]}...")
    content = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Markdown saved to {path}")
    return path
