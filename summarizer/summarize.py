"""LLM summarization — local Ollama structured knowledge extraction."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json
import requests
import config


def build_structured_prompt(merged_text: str) -> str:
    return f"""You are a structured knowledge extraction engine analyzing an Instagram Reel.
Analyze ALL available information together. Combine sources intelligently.
If OCR and transcript overlap, merge them. Never ignore OCR. Never ignore the caption.
If something is not mentioned in ANY source, return [] or null. Do NOT invent URLs, books, people, or tools.

-------------------------
TRANSCRIPT
-------------------------
{merged_text.split('=== TRANSCRIPT ===')[1].split('===')[0].strip() if '=== TRANSCRIPT ===' in merged_text else merged_text}

-------------------------
OCR TEXT
-------------------------
{merged_text.split('=== OCR TEXT ===')[1].split('===')[0].strip() if '=== OCR TEXT ===' in merged_text else ''}

-------------------------
CAPTION
-------------------------
{merged_text.split('=== CAPTION ===')[1].split('=== RESOURCES ===')[0].strip() if '=== CAPTION ===' in merged_text else (merged_text.split('=== RESOURCES ===')[0].strip() if '=== RESOURCES ===' in merged_text else merged_text)}

-------------------------
EXTRACTION RULES
-------------------------
- executive_summary: 2-3 concise sentences combining all sources
- core_idea: the main idea or message of the Reel
- key_lessons: practical concepts or takeaways
- actionable_takeaways: concrete steps a viewer can take
- tools_mentioned: software, libraries, platforms mentioned in transcript or OCR
- frameworks_mentioned: AI frameworks or methodologies
- books_or_courses: only if explicitly named in any source; else []
- people_mentioned: only if explicitly named; else []
- companies_mentioned: only if explicitly named; else []
- public_resources: GitHub repos, websites, links mentioned
- links: URLs found in any source; else []
- comment_trigger: detect exact phrases like "Comment AI", "Comment FREE", "DM me", "Link in bio", "Check bio", "Download below", "Get the prompt"; if none, null
- creator_cta: any call-to-action from the creator; if none, null
- keywords: 5-15 useful keywords combining all sources
- confidence: float between 0.0 and 1.0 based on how clearly the content supports the extraction

ANTI-HALLUCINATION:
- If a category has no evidence: return [] or null
- Do NOT guess URLs, books, people, companies, or frameworks
- Only extract what appears in transcript, OCR, or caption

OUTPUT FORMAT (ONLY JSON, NO OTHER TEXT):
{{
  "executive_summary": "",
  "core_idea": "",
  "key_lessons": [],
  "actionable_takeaways": [],
  "tools_mentioned": [],
  "frameworks_mentioned": [],
  "books_or_courses": [],
  "people_mentioned": [],
  "companies_mentioned": [],
  "public_resources": [],
  "links": [],
  "comment_trigger": null,
  "creator_cta": null,
  "keywords": [],
  "confidence": 0.0
}}

CONTENT:
---
{merged_text}
---
JSON OUTPUT ONLY:"""


def summarize_local_structured(merged_text: str) -> dict:
    from summarizer import ollama_client

    if not ollama_client.health_check():
        return {
            "executive_summary": "Ollama server unavailable. Please run 'ollama serve'.",
            "core_idea": "",
            "key_lessons": [],
            "actionable_takeaways": ["Start Ollama server (ollama serve)"],
            "tools_mentioned": [],
            "frameworks_mentioned": [],
            "books_or_courses": [],
            "people_mentioned": [],
            "companies_mentioned": [],
            "public_resources": [],
            "links": [],
            "comment_trigger": None,
            "creator_cta": None,
            "keywords": ["ollama", "local-llm"],
            "confidence": 0.0,
        }

    if not ollama_client.verify_model():
        return {
            "executive_summary": f"Local model '{config.OLLAMA_MODEL}' not installed. Please run: ollama pull {config.OLLAMA_MODEL}",
            "core_idea": "",
            "key_lessons": [],
            "actionable_takeaways": [f"Install model: ollama pull {config.OLLAMA_MODEL}"],
            "tools_mentioned": [],
            "frameworks_mentioned": [],
            "books_or_courses": [],
            "people_mentioned": [],
            "companies_mentioned": [],
            "public_resources": [],
            "links": [],
            "comment_trigger": None,
            "creator_cta": None,
            "keywords": ["ollama", "model-install"],
            "confidence": 0.0,
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
            "executive_summary": f"Extraction parse error: {e}",
            "core_idea": "",
            "key_lessons": [],
            "actionable_takeaways": ["Review source content manually"],
            "tools_mentioned": [],
            "frameworks_mentioned": [],
            "books_or_courses": [],
            "people_mentioned": [],
            "companies_mentioned": [],
            "public_resources": [],
            "links": [],
            "comment_trigger": None,
            "creator_cta": None,
            "keywords": [],
            "confidence": 0.0,
        }

    # Normalize to exact schema keys
    def get_list(val):
        if isinstance(val, list):
            return val
        if isinstance(val, str) and val:
            return [val]
        return []

    def get_str(val):
        if isinstance(val, str) and val:
            return val
        return ""

    def get_float(val):
        try:
            f = float(val)
            return max(0.0, min(1.0, f))
        except (TypeError, ValueError):
            return 0.0

    normalized = {
        "executive_summary": get_str(parsed.get("executive_summary", parsed.get("summary", parsed.get("short_summary", "")))),
        "core_idea": get_str(parsed.get("core_idea", parsed.get("main_idea", parsed.get("idea", "")))),
        "key_lessons": get_list(parsed.get("key_lessons", parsed.get("key_concepts", parsed.get("concepts", [])))),
        "actionable_takeaways": get_list(parsed.get("actionable_takeaways", parsed.get("action_items", parsed.get("actions", [])))),
        "tools_mentioned": get_list(parsed.get("tools_mentioned", parsed.get("important_tools", parsed.get("tools", [])))),
        "frameworks_mentioned": get_list(parsed.get("frameworks_mentioned", parsed.get("frameworks", parsed.get("technologies", [])))),
        "books_or_courses": get_list(parsed.get("books_or_courses", parsed.get("books", parsed.get("courses", [])))),
        "people_mentioned": get_list(parsed.get("people_mentioned", parsed.get("people", parsed.get("names", [])))),
        "companies_mentioned": get_list(parsed.get("companies_mentioned", parsed.get("companies", parsed.get("companies", [])))),
        "public_resources": get_list(parsed.get("public_resources", parsed.get("resources", parsed.get("github_repos", parsed.get("urls", []))))),
        "links": get_list(parsed.get("links", parsed.get("urls", parsed.get("public_resources", [])))),
        "comment_trigger": parsed.get("comment_trigger", parsed.get("trigger", None)) if isinstance(parsed.get("comment_trigger", parsed.get("trigger", None)), str) else (parsed.get("comment_trigger", parsed.get("trigger", None)) if parsed.get("comment_trigger", parsed.get("trigger")) else None),
        "creator_cta": parsed.get("creator_cta", parsed.get("cta", None)) if isinstance(parsed.get("creator_cta", parsed.get("cta", None)), str) else (parsed.get("creator_cta", parsed.get("cta", None)) if parsed.get("creator_cta", parsed.get("cta")) else None),
        "keywords": get_list(parsed.get("keywords", parsed.get("tags", parsed.get("keywords", [])))),
        "confidence": get_float(parsed.get("confidence", parsed.get("confidence_score", 0.5))),
    }
    return normalized


def summarize_cloud_structured(merged_text: str) -> dict:
    prompt = build_structured_prompt(merged_text)
    import requests
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.CLOUD_API_KEY}",
    }
    payload = {
        "model": config.CLOUD_MODEL,
        "messages": [
            {"role": "system", "content": "You are a structured knowledge extraction engine. Always return valid JSON only. Never include prose outside JSON."},
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

    def get_list(val):
        if isinstance(val, list):
            return val
        if isinstance(val, str) and val:
            return [val]
        return []

    def get_str(val):
        if isinstance(val, str) and val:
            return val
        return ""

    def get_float(val):
        try:
            f = float(val)
            return max(0.0, min(1.0, f))
        except (TypeError, ValueError):
            return 0.0

    normalized = {
        "executive_summary": get_str(parsed.get("executive_summary", parsed.get("summary", parsed.get("short_summary", str(parsed))))),
        "core_idea": get_str(parsed.get("core_idea", parsed.get("main_idea", parsed.get("idea", "")))),
        "key_lessons": get_list(parsed.get("key_lessons", parsed.get("key_concepts", []))),
        "actionable_takeaways": get_list(parsed.get("actionable_takeaways", parsed.get("action_items", []))),
        "tools_mentioned": get_list(parsed.get("tools_mentioned", parsed.get("important_tools", parsed.get("tools", [])))),
        "frameworks_mentioned": get_list(parsed.get("frameworks_mentioned", parsed.get("frameworks", []))),
        "books_or_courses": get_list(parsed.get("books_or_courses", parsed.get("books", parsed.get("courses", [])))),
        "people_mentioned": get_list(parsed.get("people_mentioned", parsed.get("people", []))),
        "companies_mentioned": get_list(parsed.get("companies_mentioned", parsed.get("companies", []))),
        "public_resources": get_list(parsed.get("public_resources", parsed.get("resources", parsed.get("github_repos", parsed.get("urls", []))))),
        "links": get_list(parsed.get("links", parsed.get("urls", []))),
        "comment_trigger": parsed.get("comment_trigger", parsed.get("trigger", None)) if isinstance(parsed.get("comment_trigger", parsed.get("trigger", None)), str) else (parsed.get("comment_trigger", parsed.get("trigger", None)) if parsed.get("comment_trigger", parsed.get("trigger")) else None),
        "creator_cta": parsed.get("creator_cta", parsed.get("cta", None)) if isinstance(parsed.get("creator_cta", parsed.get("cta", None)), str) else (parsed.get("creator_cta", parsed.get("cta", None)) if parsed.get("creator_cta", parsed.get("cta")) else None),
        "keywords": get_list(parsed.get("keywords", parsed.get("tags", []))),
        "confidence": get_float(parsed.get("confidence", parsed.get("confidence_score", 0.5))),
    }
    return normalized


def summarize(merged_text: str) -> dict:
    if config.LLM_MODE == "local":
        return summarize_local_structured(merged_text)
    else:
        return summarize_cloud_structured(merged_text)
