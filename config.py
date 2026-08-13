"""Configuration settings for Reel Analyzer."""
import os
from pathlib import Path

# Load .env before reading configuration variables
try:
    from dotenv import load_dotenv
    load_dotenv(str(Path(__file__).resolve().parent / ".env"), override=False)
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp"

# Ensure directories exist
OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

# Browser
INSTAGRAM_URL = "https://www.instagram.com"
BROWSER_SESSION_PATH = BASE_DIR / ".instagram_session"
VIDEO_TIMEOUT = 60

# Audio
AUDIO_FILE = TEMP_DIR / "audio.wav"

# Whisper
WHISPER_MODEL_SIZE = "small"

# Frame extraction
FRAMES_DIR = TEMP_DIR / "frames"
FPS = 1

# OCR
OCR_CONFIDENCE = 0.5

# LLM settings
LLM_MODE = os.getenv("LLM_MODE", "local")  # "local" or "cloud"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
CLOUD_API_KEY = os.getenv("CLOUD_API_KEY", "")
CLOUD_API_URL = os.getenv("CLOUD_API_URL", "https://api.openai.com/v1/chat/completions")
CLOUD_MODEL = os.getenv("CLOUD_MODEL", "gpt-3.5-turbo")

# Regex patterns
URL_PATTERN = r"https?://[^\s<>\"{}|\\^`\[\]]+"
GITHUB_REPO = r"github\.com/[\w\-]+/[\w\-\.]+"
EMAIL_PATTERN = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
INSTAGRAM_HANDLE = r"(?:@|\b)instagram\.com/([\w\.]+)"
TWITTER_HANDLE = r"(?:@|\b)twitter\.com/([A-Za-z0-9_]+)|(?:@|\b)x\.com/([A-Za-z0-9_]+)"
YOUTUBE_LINK = r"(?:youtube\.com|youtu\.be)/[A-Za-z0-9_\-]+"
DISCORD_LINK = r"discord\.(gg|com)/[A-Za-z0-9_\-]+"
HASHTAG = r"#[\w\-]+"
PHONE_NUMBER = r"(?:\+\d{1,3}[\s\-.]?)?\(?\d{2,4}\)?[\s\-.]?\d{3,4}[\s\-.]?\d{3,4}"
