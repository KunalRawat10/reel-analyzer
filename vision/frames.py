"""Frame extraction from video."""
import subprocess
import sys
from pathlib import Path
import config

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def extract_frames(video_path: Path, output_dir: Path = None, fps: float = None) -> Path:
    """Extract frames from a video using FFmpeg."""
    if output_dir is None:
        output_dir = config.FRAMES_DIR
    if fps is None:
        fps = 0.5
    output_dir.mkdir(parents=True, exist_ok=True)
    for existing in output_dir.glob("frame_*.png"):
        existing.unlink()
    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-vf", f"fps={fps}",
        str(output_dir / "frame_%04d.png"),
    ]
    print("Running frame extraction...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    extracted = sorted(output_dir.glob("frame_*.png"))
    count = len(extracted)
    if count == 0:
        raise RuntimeError("No frames were extracted.")
    print(f"Frame extraction: {count} frames saved")
    return output_dir
