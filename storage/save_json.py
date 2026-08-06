"""Save results as JSON."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json
from pathlib import Path
import config


def save_json(data: dict, reel_id: str = None) -> Path:
    if reel_id is None:
        import uuid
        reel_id = str(uuid.uuid4())[:8]
    path = config.OUTPUT_DIR / f"reel_{reel_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"JSON saved to {path}")
    return path
