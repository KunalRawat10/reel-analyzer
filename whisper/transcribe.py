"""Speech-to-text using Faster-Whisper."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from faster_whisper import WhisperModel
import config


def transcribe(audio_path, model_size=config.WHISPER_MODEL_SIZE, language=None):
    """Transcribe audio file to text with timestamps."""
    print(f"Loading Whisper model: {model_size}")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    print(f"Transcribing {audio_path}")
    segments, info = model.transcribe(str(audio_path), beam_size=5, language=language)
    result = []
    for segment in segments:
        result.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip(),
        })
    full_text = " ".join([r["text"] for r in result])
    print(f"Transcription complete ({len(result)} segments).")
    return {
        "language": info.language if info else None,
        "segments": result,
        "text": full_text,
    }
