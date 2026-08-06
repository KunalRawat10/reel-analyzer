"""Audio extraction using FFmpeg."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import subprocess
from pathlib import Path
import config


def extract_audio(video_path: Path, output_path: Path | None = None) -> Path:
    """Extract audio from video and convert to WAV."""
    if output_path is None:
        output_path = config.AUDIO_FILE
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        "-y",
        str(output_path),
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FFmpeg stderr: {result.stderr}")
    else:
        print(f"Audio extracted: {output_path}")
    return output_path
