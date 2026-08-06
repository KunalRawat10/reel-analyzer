"""Merge transcript, OCR, caption, and resources."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pathlib import Path
import config


def merge_data(transcript_text: str, ocr_texts: list[str], caption: str, resources: dict) -> str:
    """Combine all extracted data into a single text document."""
    lines = []
    lines.append("=== TRANSCRIPT ===")
    lines.append(transcript_text)
    lines.append("")
    lines.append("=== OCR TEXT ===")
    lines.append("\n".join(ocr_texts))
    lines.append("")
    if caption:
        lines.append("=== CAPTION ===")
        lines.append(caption)
        lines.append("")
    lines.append("=== RESOURCES ===")
    for key, values in resources.items():
        if values:
            lines.append(f"{key.upper()}: {', '.join(values)}")
    combined = "\n".join(lines)
    # Save temporary merged text
    merge_path = config.TEMP_DIR / "merged.txt"
    merge_path.write_text(combined, encoding="utf-8")
    return combined
