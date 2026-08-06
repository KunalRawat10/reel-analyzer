#!/usr/bin/env python3
"""Standalone test: Persistent Playwright profile for Instagram login persistence."""
import sys
from pathlib import Path
import time
from playwright.sync_api import sync_playwright

# Dedicated persistent profile directory (Windows-compatible absolute path)
PROFILE_DIR = Path(r"C:\Users\kunal\OneDrive\Desktop\reel-analyzer\persistent_profile")
REEL_URL = "https://www.instagram.com/reel/DYhyWWKSPRT/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA=="


def main():
    print("=== Persistent Profile Test ===")
    print(f"Profile directory: {PROFILE_DIR}")
    print(f"Profile exists: {PROFILE_DIR.exists()}")

    p = sync_playwright().start()
    # Launch persistent browser context with dedicated user data directory
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=False,
        args=[
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
        ],
    )
    page = context.new_page()

    try:
        profile_is_new = not any(PROFILE_DIR.iterdir()) if PROFILE_DIR.exists() else True
        if profile_is_new:
            print("[1] Profile is new. Navigating to Instagram for manual login...")
            page.goto("https://www.instagram.com/", timeout=60000)
            print("[2] Please log in manually in the browser window.")
            print("[3] Once logged in and you see your feed, press ENTER here...")
            input()
            # Persistent context saves automatically; no explicit save needed
            print("[4] Login completed. Profile will be reused on future runs.")
        else:
            print("[1] Reusing existing persistent profile.")

        print(f"[5] Navigating to Reel URL: {REEL_URL}")
        page.goto(REEL_URL, timeout=60000)
        time.sleep(5)

        # Check for redirection to login or recaptcha
        final_url = page.evaluate("() => window.location.href")
        page_title = page.evaluate("() => document.title")
        body_text = page.evaluate("() => document.body.innerText || ''")

        redirect_indicators = ["login", "accounts/login", "recaptcha", "challenge", "verify", "security"]
        redirected = False
        final_url_lower = final_url.lower()
        body_text_lower = body_text.lower()
        for indicator in redirect_indicators:
            if indicator in final_url_lower or indicator in body_text_lower:
                print(f"[FAIL] Redirected or blocked. Final URL: {final_url}")
                print(f"[FAIL] Page title: {page_title}")
                if "login" in final_url_lower:
                    print("[FAIL] DIAGNOSTIC: Redirected to Instagram login. Persistent profile did not avoid redirection.")
                elif "recaptcha" in final_url_lower or "challenge" in final_url_lower:
                    print("[FAIL] DIAGNOSTIC: Blocked by recaptcha/challenge. Persistent profile may be flagged.")
                elif "security" in final_url_lower:
                    print("[FAIL] DIAGNOSTIC: Security verification required.")
                else:
                    print(f"[FAIL] DIAGNOSTIC: Indicator '{indicator}' found in URL or body.")
                redirected = True
                break

        if redirected:
            # Print PASS/FAIL clearly as requested
            print("PASS" if False else "FAIL")
            return

        print(f"[6] Final URL: {final_url}")
        print(f"[6] Page title: {page_title}")

        print("[7] Waiting for video element (up to 30s)...")
        try:
            page.wait_for_selector("video", timeout=30000)
            print("[PASS] Video element found.")
        except Exception as e:
            print(f"[FAIL] Video element not found within 30s: {e}")
            print(f"[FAIL] Final URL at timeout: {final_url}")
            return

        # Verify playing state briefly
        time.sleep(2)
        playing_check = page.evaluate("""
            () => {
                const v = document.querySelector('video');
                return v ? { present: true, paused: v.paused, currentTime: v.currentTime, duration: v.duration || 0 } : { present: false };
            }
        """)
        print(f"[8] Playback check: present={playing_check.get('present')}, paused={playing_check.get('paused')}, currentTime={playing_check.get('currentTime')}, duration={playing_check.get('duration')}")

        print("[PASS] Persistent profile works. Video element present. No redirection to login/recaptcha.")

    finally:
        print("[9] Closing browser...")
        context.close()
        p.stop()
        print(f"[10] Profile saved at: {PROFILE_DIR.resolve() if PROFILE_DIR.exists() else 'Not found'}")


if __name__ == "__main__":
    main()
