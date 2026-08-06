"""Ollama client for structured local LLM extraction."""
import requests
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


def health_check() -> bool:
    """Check if Ollama server is running via /api/tags."""
    try:
        url = "http://localhost:11434/api/tags"
        response = requests.get(url, timeout=10)
        print(f"Ollama health check URL: {url}")
        print(f"Ollama health check HTTP status: {response.status_code}")
        if response.status_code == 200:
            return True
        else:
            print(f"Ollama server responded with status {response.status_code} but is available.")
            return True
    except Exception as e:
        print(f"Ollama server unavailable: {e}")
        print("Friendly error: Please start Ollama with 'ollama serve' before running analysis.")
        return False


def verify_model() -> bool:
    """Verify that the configured model (qwen2.5:7b) is available locally."""
    model = config.OLLAMA_MODEL
    print(f"Verifying local model: {model}")
    try:
        url = "http://localhost:11434/api/tags"
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"Model verification failed: server returned status {response.status_code}")
            print(f"Clear message: Model '{model}' not available. Please run: ollama pull {model}")
            return False
        tags = response.json()
        available_models = []
        if isinstance(tags, dict) and "models" in tags:
            available_models = [m.get("name", "") for m in tags.get("models", [])]
        elif isinstance(tags, list):
            available_models = [m.get("name", "") for m in tags]
        if model in available_models:
            print(f"Model '{model}' verified and available.")
            return True
        else:
            print(f"Clear message: Model '{model}' not found in installed models. Available: {available_models}")
            print(f"To install: ollama pull {model}")
            return False
    except Exception as e:
        print(f"Model verification error: {e}")
        print(f"Clear message: Could not verify '{model}' due to connection error.")
        return False


def call_ollama(prompt: str, model: str = None) -> str:
    """Send structured prompt to local Ollama with full debug logging."""
    if model is None:
        model = config.OLLAMA_MODEL
    url = "http://localhost:11434/api/generate"
    payload_size = len(prompt.encode("utf-8"))
    print(f"Ollama request URL: {url}")
    print(f"Ollama model: {model}")
    print(f"Ollama payload size: {payload_size} bytes")
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.1,
    }
    print(f"Ollama payload keys: {list(payload.keys())}")
    try:
        response = requests.post(url, json=payload, timeout=300)
        print(f"Ollama HTTP status: {response.status_code}")
        response.raise_for_status()
        result = response.json()["response"]
        first_500 = result[:500] if len(result) > 500 else result
        print(f"Ollama response (first 500 chars): {first_500}")
        return result
    except Exception as e:
        print(f"Ollama request error: {e}")
        raise
