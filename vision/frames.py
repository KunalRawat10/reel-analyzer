"""Frame extraction from video."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import subprocess
from pathlib import Path
import config


def extract_frames(video_path: Path, output_dir: Path = None, fps: int = None) -> Path:
    """Extract frames at 1 FPS using FFmpeg."""
    if output_dir is None:
        output_dir = config.FRAMES_DIR
    if fps is None:
        fps = config.FPS
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-vf", f"fps={fps}",
        str(output_dir / "frame_%04d.png"),
    ]
    print(f"Running frame extraction: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Frame extraction failed (exit {result.returncode}): {result.stderr[:500]}")
    else:
        extracted = sorted(output_dir.glob("frame_*.png"))
        if not extracted:
            print("Frame extraction: no PNG frames produced (check video input).")
        else:
            print(f"Frame extraction: {len(extracted)} frames saved to {output_dir}")
    return output_dir
