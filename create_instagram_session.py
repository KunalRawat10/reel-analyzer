#!/usr/bin/env python3
"""Standalone script: Create Instagram Playwright session for reel-analyzer."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

SESSION_FILE = Path(r"C:\Users\kunal\OneDrive\Desktop\reel-analyzer\reel-analyzer\.instagram_session")


def main():
    print("=== Instagram Session Creator ===")
    print("Instructions:")
    print("  1. Log in to Instagram manually in the browser window.")
    print("  2. Once you see your feed/profile, press ENTER in this terminal.")
    print()

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    try:
        print("[1] Navigating to https://www.instagram.com/")
        page.goto("https://www.instagram.com/", timeout=60000)
        print("[2] Browser is open. Please log in manually.")
        print("[3] Once logged in and you see your Instagram feed, press ENTER here...")
        input()

        print("[4] Checking for logged-in username...")
        try:
            username = page.evaluate("""
                () => {
                    const userLink = document.querySelector('a[href*="/"]');
                    const meta = document.querySelector('meta[name="description"]');
                    const title = document.title;
                    // Try to find username from header/profile links
                    const links = document.querySelectorAll('a[href^="/"]');
                    for (let link of links) {
                        const href = link.getAttribute('href');
                        if (href && href.length > 1 && href[0] === '/' && !href.includes('explore') && !href.includes('accounts') && !href.includes('reels') && !href.includes('direct')) {
                            return href.replace('/', '');
                        }
                    }
                    return title || meta ? meta.getAttribute('content') : null;
                }
            """)
            if username and isinstance(username, str) and len(username) > 0:
                # Clean up username
                username = username.split()[0] if ' ' in username else username
                print(f"[5] Detected username/profile reference: {username}")
            else:
                print("[5] Could not extract username automatically (may still be logged in).")
        except Exception as e:
            print(f"[5] Could not detect username: {e}")

        print(f"[6] Saving session file to: {SESSION_FILE}")
        # Ensure parent directory exists
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(SESSION_FILE))

        print("[7] Verifying session file exists...")
        if SESSION_FILE.exists():
            file_size = SESSION_FILE.stat().st_size
            abs_path = SESSION_FILE.resolve()
            print(f"[8] Session file saved: {abs_path}")
            print(f"[9] File size: {file_size} bytes")
            print("[10] Verification: SUCCESS")
        else:
            print("[10] Verification: FAILED - File not found after save.")

    finally:
        print("[11] Closing browser and process...")
        page.close()
        browser.close()
        p.stop()
        if SESSION_FILE.exists():
            print(f"[12] Final confirmation: {SESSION_FILE.resolve()} exists ({SESSION_FILE.stat().st_size} bytes)")
        else:
            print("[12] Final confirmation: FILE MISSING")


if __name__ == "__main__":
    main()
