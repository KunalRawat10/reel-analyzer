#!/usr/bin/env python3
"""End-to-end test using dummy data (no Instagram browser)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from parser import regex, merge
from summarizer import summarize

def main():
    dummy_text = """
    Welcome to this Python tutorial. Check out github.com/user/repo for code.
    Email me at hello@example.com. Follow @python on twitter. #coding
    """
    resources = regex.extract_resources(dummy_text)
    combined = merge.merge_data(dummy_text, ["some frame text"], "Dummy caption", resources)
    print("Merged text length:", len(combined))

    # Test local LLM mode (requires ollama running with gemma:2b or similar)
    # If ollama isn't running, this will print an error but won't crash hard
    print("\nTrying summarizer (local mode)...")
    summary = summarize.summarize(combined)
    print("Summary result type:", type(summary))
    print("Summary keys/preview:", str(summary)[:500])

if __name__ == "__main__":
    main()
