"""LLM summarization — local Ollama structured knowledge extraction."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json
import requests
import config


def build_structured_prompt(merged_text: str) -> str:
    return f"""You are a structured knowledge extraction engine.
Analyze the following educational Instagram Reel content and return ONLY a valid JSON object with these exact keys:

- "summary": a concise 2-3 sentence summary of the Reel's core message
- "key_concepts": a list of the main ideas or concepts discussed
- "important_tools": a list of any tools, software, libraries, or platforms mentioned
- "action_items": a list of practical steps or takeaways for the viewer
- "technologies": a list of technologies or programming languages mentioned
- "learning_level": one of ["beginner", "intermediate", "advanced"] based on content complexity
- "tags": a list of 3-5 relevant hashtags or keywords

Do not include any text outside the JSON. Return only the JSON object.

CONTENT TO ANALYZE:
---
{merged_text}
---
JSON OUTPUT:"""


def summarize_local_structured(merged_text: str) -> dict:
    from summarizer import ollama_client

    if not ollama_client.health_check():
        return {
            "summary": "Ollama server unavailable. Please run 'ollama serve'.",
            "key_concepts": [],
            "important_tools": [],
            "action_items": ["Start Ollama server (ollama serve)"],
            "technologies": [],
            "learning_level": "unknown",
            "tags": ["ollama", "local-llm"],
        }

    if not ollama_client.verify_model():
        return {
            "summary": f"Local model '{config.OLLAMA_MODEL}' not installed. Please run: ollama pull {config.OLLAMA_MODEL}",
            "key_concepts": [],
            "important_tools": [],
            "action_items": [f"Install model: ollama pull {config.OLLAMA_MODEL}"],
            "technologies": [],
            "learning_level": "unknown",
            "tags": ["ollama", "model-install"],
        }

    prompt = build_structured_prompt(merged_text)
    try:
        result_text = ollama_client.call_ollama(prompt, model=config.OLLAMA_MODEL)
        result_text = result_text.strip()
        if result_text.startswith("```json"):
            result_text = result_text.replace("```json", "").replace("```", "").strip()
        elif result_text.startswith("```"):
            result_text = result_text.replace("```", "").strip()
        parsed = json.loads(result_text)
    except Exception as e:
        print(f"Ollama structured extraction parse error: {e}")
        return {
            "summary": f"Extraction parse error: {e}",
            "key_concepts": [],
            "important_tools": [],
            "action_items": ["Review source content manually"],
            "technologies": [],
            "learning_level": "unknown",
            "tags": [],
        }

    # Normalize to expected keys
    normalized = {}
    normalized["summary"] = parsed.get("summary", parsed.get("short_summary", parsed.get("Summary", str(parsed))))
    normalized["key_concepts"] = parsed.get("key_concepts", parsed.get("Key concepts", parsed.get("concepts", [])))
    normalized["important_tools"] = parsed.get("important_tools", parsed.get("Important tools", parsed.get("tools", [])))
    normalized["action_items"] = parsed.get("action_items", parsed.get("Action items", parsed.get("actions", [])))
    normalized["technologies"] = parsed.get("technologies", parsed.get("Technologies mentioned", parsed.get("tech", [])))
    normalized["learning_level"] = parsed.get("learning_level", parsed.get("Learning level", "intermediate"))
    normalized["tags"] = parsed.get("tags", parsed.get("Tags", parsed.get("keywords", [])))
    for key in ["key_concepts", "important_tools", "action_items", "tags"]:
        val = normalized.get(key)
        if isinstance(val, str):
            normalized[key] = [val] if val else []
        elif not isinstance(val, list):
            normalized[key] = []
    if isinstance(normalized.get("technologies"), str):
        normalized["technologies"] = [normalized["technologies"]] if normalized["technologies"] else []
    return normalized


def summarize_cloud_structured(merged_text: str) -> dict:
    # Preserve existing cloud interface but structure output the same way
    prompt = build_structured_prompt(merged_text)
    import requests
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.CLOUD_API_KEY}",
    }
    payload = {
        "model": config.CLOUD_MODEL,
        "messages": [
            {"role": "system", "content": "You are a structured knowledge extraction engine. Always return valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }
    response = requests.post(config.CLOUD_API_URL, headers=headers, json=payload, timeout=120)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    content = content.strip()
    if content.startswith("```json"):
        content = content.replace("```json", "").replace("```", "").strip()
    elif content.startswith("```"):
        content = content.replace("```", "").strip()
    try:
        parsed = json.loads(content)
    except Exception:
        parsed = {"summary": content}
    normalized = {}
    normalized["summary"] = parsed.get("summary", parsed.get("short_summary", parsed.get("Summary", str(parsed))))
    normalized["key_concepts"] = parsed.get("key_concepts", parsed.get("Key concepts", []))
    normalized["important_tools"] = parsed.get("important_tools", parsed.get("Important tools", []))
    normalized["action_items"] = parsed.get("action_items", parsed.get("Action items", []))
    normalized["technologies"] = parsed.get("technologies", parsed.get("Technologies mentioned", []))
    normalized["learning_level"] = parsed.get("learning_level", parsed.get("Learning level", "intermediate"))
    normalized["tags"] = parsed.get("tags", parsed.get("Tags", []))
    for key in ["key_concepts", "important_tools", "action_items", "tags"]:
        val = normalized.get(key)
        if isinstance(val, str):
            normalized[key] = [val] if val else []
        elif not isinstance(val, list):
            normalized[key] = []
    if isinstance(normalized.get("technologies"), str):
        normalized["technologies"] = [normalized["technologies"]] if normalized["technologies"] else []
    return normalized


def summarize(merged_text: str) -> dict:
    if config.LLM_MODE == "local":
        return summarize_local_structured(merged_text)
    else:
        return summarize_cloud_structured(merged_text)
