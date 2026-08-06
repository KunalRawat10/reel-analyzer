#!/usr/bin/env python3
"""Standalone proof-of-concept: Playwright browser recording with video.captureStream() + MediaRecorder."""
import sys
from pathlib import Path
import subprocess
import time
from playwright.sync_api import sync_playwright

REEL_URL = "https://www.instagram.com/reel/DYhyWWKSPRT/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA=="
# Use the same session file as the main project (reel-analyzer/.instagram_session)
# Adjust this path if your workspace is elsewhere
SESSION_FILE = Path(__file__).resolve().parent.parent / "reel-analyzer" / ".instagram_session"
# Fallback: check relative to current working directory
if not SESSION_FILE.exists():
    SESSION_FILE = Path("reel-analyzer/.instagram_session")
OUTPUT_WEBM = Path("C:\\temp\\reel_capture.webm")  # Windows path
OUTPUT_MP4 = Path("C:\\temp\\reel_capture.mp4")


def main():
    print("=== Proof of Concept: Browser Capture Stream ===")
    print(f"[INIT] Session file: {SESSION_FILE}")
    print(f"[INIT] Session exists: {SESSION_FILE.exists() if SESSION_FILE else False}")

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=False)

    # Reuse session file from main project
    session_str = str(SESSION_FILE) if SESSION_FILE and SESSION_FILE.exists() else None
    if session_str:
        print(f"[INIT] Using saved session: {session_str}")
        context = browser.new_context(storage_state=session_str)
    else:
        print("[INIT] No saved session found. Starting fresh browser context.")
        context = browser.new_context()

    page = context.new_page()

    try:
        # Step 1: Verify login before opening Reel
        print("[STEP 1] Verifying Instagram login...")
        page.goto("https://www.instagram.com/", timeout=60000)
        time.sleep(5)

        # Check for common login indicators: either profile avatar or redirect to login
        # If we see a login form or "Log in" prominently, we're not logged in
        login_indicators = page.evaluate("""
            () => {
                const loginText = document.body.innerText || '';
                const hasLoginForm = !!document.querySelector('form[action*="/accounts/login/"]');
                const hasLoginButton = !!document.querySelector('a[href*="/accounts/login/"]');
                const hasProfileAvatar = !!document.querySelector('header img, nav img, [aria-label*="Profile"]');
                return {
                    bodyTextLength: document.body.innerText.length,
                    hasLoginForm: hasLoginForm,
                    hasLoginButton: hasLoginButton,
                    hasProfileAvatar: hasProfileAvatar,
                    title: document.title,
                    url: window.location.href
                };
            }
        """)
        print(f"[LOGIN CHECK] Title: {login_indicators.get('title')}")
        print(f"[LOGIN CHECK] URL: {login_indicators.get('url')}")
        print(f"[LOGIN CHECK] Has profile avatar: {login_indicators.get('hasProfileAvatar')}")
        print(f"[LOGIN CHECK] Has login form: {login_indicators.get('hasLoginForm')}")
        print(f"[LOGIN CHECK] Has login button: {login_indicators.get('hasLoginButton')}")

        if login_indicators.get("hasLoginForm") or login_indicators.get("hasLoginButton"):
            if not login_indicators.get("hasProfileAvatar"):
                print("[LOGIN CHECK] DIAGNOSTIC: Not logged in. Instagram shows login page.")
                print("[LOGIN CHECK] DIAGNOSTIC: Please save a session using browser/instagram.py save_session() or log in manually.")
                # Continue anyway; the Reel may still show content or "Post isn't available"
            else:
                print("[LOGIN CHECK] DIAGNOSTIC: Profile avatar found, likely logged in.")
        else:
            print("[LOGIN CHECK] DIAGNOSTIC: No login form detected. Proceeding with Reel URL.")

        # Step 2: Open the Reel URL
        print(f"[STEP 2] Navigating to Reel URL: {REEL_URL}")
        page.goto(REEL_URL, timeout=60000)
        time.sleep(5)

        # Step 3: Check page content for "Post isn't available" or similar errors
        print("[STEP 3] Checking page content for errors or availability messages...")
        page_content_text = page.evaluate("() => document.body.innerText || ''")
        page_title = page.evaluate("() => document.title || ''")
        print(f"[PAGE CHECK] Title: {page_title}")
        print(f"[PAGE CHECK] URL: {page.evaluate('() => window.location.href')}")
        # Look for common "not available" indicators
        not_available_indicators = [
            "isn't available", "is not available", "post isn't available",
            "post is not available", "not available", "unavailable",
            "this post", "post", "reel", "instagram"
        ]
        found_unavailable = False
        for indicator in not_available_indicators:
            if indicator.lower() in page_content_text.lower():
                print(f"[PAGE CHECK] Found indicator in page text: '{indicator}'")
                # Check specifically for the exact error message
                if "isn't available" in page_content_text or "is not available" in page_content_text:
                    found_unavailable = True
        if found_unavailable:
            print("[DIAGNOSTIC] The page shows 'Post isn't available' (or similar).")
            print("[DIAGNOSTIC] This usually means:")
            print("    - The Reel URL requires an active Instagram login session.")
            print(f"    - The session file '{SESSION_FILE}' may be missing, expired, or invalid.")
            print("    - Instagram may have blocked the request due to cookie/session issues.")
            print("    - Try saving a fresh session with the main project's browser/instagram.py or log in manually.")
        else:
            print("[PAGE CHECK] No 'Post isn't available' message detected. Proceeding...")

        # Step 4: Wait for video element
        print("[STEP 4] Waiting for video element (timeout 30s)...")
        try:
            page.wait_for_selector("video", timeout=30000)
            print("[STEP 4] Video element found in DOM.")
        except Exception as e:
            print(f"[STEP 4] ERROR: Video element not found within 30s: {e}")
            print("[STEP 4] DIAGNOSTIC: The Reel may not have loaded correctly. Check URL, login, or network.")
            page.screenshot(path="C:\\temp\\reel_error_screenshot.png")
            print("[STEP 4] Screenshot saved to C:\\temp\\reel_error_screenshot.png")
            raise

        # Step 5: Check if video is actually playing (not just present)
        print("[STEP 5] Checking video playback state...")
        # Try to play
        try:
            page.evaluate("document.querySelector('video').play()")
            print("[STEP 5] Playback command sent.")
        except Exception as e:
            print(f"[STEP 5] Could not send play command: {e}")

        # Wait for video to actually start playing
        playing_confirmed = False
        for attempt in range(10):
            time.sleep(2)
            video_state = page.evaluate("""
                () => {
                    const v = document.querySelector('video');
                    if (!v) return { present: false, playing: false, paused: true, readyState: -1, currentTime: 0, duration: 0 };
                    return {
                        present: true,
                        playing: !v.paused,
                        paused: v.paused,
                        readyState: v.readyState,
                        currentTime: v.currentTime,
                        duration: v.duration || 0,
                        ended: v.ended
                    };
                }
            """)
            print(f"[STEP 5] Video state (attempt {attempt + 1}): present={video_state.get('present')}, playing={video_state.get('playing')}, paused={video_state.get('paused')}, readyState={video_state.get('readyState')}, currentTime={video_state.get('currentTime'):.2f}, duration={video_state.get('duration'):.2f}, ended={video_state.get('ended')}")
            if video_state.get("present") and video_state.get("playing") and video_state.get("readyState", 0) >= 3:
                print("[STEP 5] DIAGNOSTIC: Video is actually playing (readyState >= 3, not paused, currentTime > 0).")
                playing_confirmed = True
                break
            if video_state.get("present") and video_state.get("readyState", 0) >= 3 and not video_state.get("paused", True) and video_state.get("currentTime", 0) > 0:
                print("[STEP 5] DIAGNOSTIC: Video is playing (currentTime advancing).")
                playing_confirmed = True
                break
        if not playing_confirmed:
            print("[STEP 5] DIAGNOSTIC: Video is present but may not be actively playing. Proceeding with capture anyway.")
            # Even if not confirmed playing, we proceed - captureStream works with loaded video

        # Step 6: Inject captureStream + MediaRecorder
        print("[STEP 6] Injecting captureStream + MediaRecorder script...")
        page.evaluate("""
            () => {
                window.__reelRecorder = null;
                window.__reelChunks = [];
                const video = document.querySelector('video');
                if (!video) {
                    console.error('No video element');
                    return;
                }
                const startRec = () => {
                    try {
                        const stream = video.captureStream ? video.captureStream() : null;
                        if (!stream) {
                            console.error('captureStream not supported');
                            return;
                        }
                        const recorder = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp8,opus' });
                        window.__reelRecorder = recorder;
                        const chunks = [];
                        recorder.ondataavailable = (e) => {
                            if (e.data && e.data.size > 0) chunks.push(e.data);
                        };
                        recorder.onstop = () => {
                            const blob = new Blob(chunks, { type: 'video/webm' });
                            window.__reelAudioBlob = blob;
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = 'reel_capture.webm';
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            console.log('Download triggered. Blob size:', blob.size, 'bytes');
                        };
                        recorder.start(500);
                        console.log('MediaRecorder started');
                        setTimeout(() => {
                            if (recorder && recorder.state === 'recording') {
                                recorder.stop();
                                console.log('Auto-stopped after 90s');
                            }
                        }, 90000);
                    } catch (err) {
                        console.error('captureStream error:', err);
                    }
                };
                if (video.readyState >= 3) {
                    startRec();
                } else {
                    video.addEventListener('loadeddata', startRec, { once: true });
                }
                video.addEventListener('ended', () => {
                    setTimeout(() => {
                        if (window.__reelRecorder && window.__reelRecorder.state === 'recording') {
                            window.__reelRecorder.stop();
                            console.log('Stopped by video.ended');
                        }
                    }, 500);
                }, { once: true });
            }
        """)

        print("[STEP 7] Waiting for download to complete (up to 95s)...")
        start_time = time.time()
        downloaded = False
        while time.time() - start_time < 95:
            if OUTPUT_WEBM.exists() and OUTPUT_WEBM.stat().st_size > 1024:
                finished = page.evaluate("""
                    () => window.__reelAudioBlob ? window.__reelAudioBlob.size > 1024 : false
                """)
                if finished:
                    print(f"[STEP 7] Download complete after {time.time() - start_time:.1f}s")
                    downloaded = True
                    break
            try:
                ended = page.evaluate("""
                    () => {
                        const v = document.querySelector('video');
                        return v ? v.ended : false;
                    }
                """)
                if ended:
                    print("[STEP 7] Video ended, giving extra 3s for download...")
                    time.sleep(3)
                    if OUTPUT_WEBM.exists() and OUTPUT_WEBM.stat().st_size > 1024:
                        finished = page.evaluate("""
                            () => window.__reelAudioBlob ? window.__reelAudioBlob.size > 1024 : false
                        """)
                        if finished:
                            downloaded = True
                    break
            except Exception:
                pass
            time.sleep(2)

        duration = time.time() - start_time
        print(f"[STEP 8] Recording duration: {duration:.1f}s")

        if OUTPUT_WEBM.exists():
            size_bytes = OUTPUT_WEBM.stat().st_size
            print(f"[STEP 9] .webm file saved: {OUTPUT_WEBM} ({size_bytes} bytes)")
        else:
            print(f"[STEP 9] WARNING: .webm file not found at {OUTPUT_WEBM}")
            # Print diagnostic for missing download
            blob_size = page.evaluate("""
                () => window.__reelAudioBlob ? window.__reelAudioBlob.size : 0
            """)
            print(f"[STEP 9] DIAGNOSTIC: Browser blob size (bytes): {blob_size}")
            if blob_size == 0:
                print("[STEP 9] DIAGNOSTIC: Blob not created. Possible reasons:")
                print("    - Video did not play (paused, muted, or blocked by Instagram)")
                print("    - captureStream not supported (old Chromium version)")
                print("    - MediaRecorder failed due to missing codecs or permissions")
            elif blob_size < 1024:
                print("[STEP 9] DIAGNOSTIC: Blob exists but is very small (< 1KB). Video may have ended immediately.")

    finally:
        print("[STEP 10] Closing browser...")
        page.close()
        browser.close()
        p.stop()

    # Convert .webm to .mp4 (Windows-compatible paths)
    print("[STEP 11] Converting .webm to .mp4 with FFmpeg...")
    webm_path_str = str(OUTPUT_WEBM)
    mp4_path_str = str(OUTPUT_MP4)
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", webm_path_str,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            mp4_path_str,
        ], check=True, capture_output=True, timeout=180)
        print(f"[STEP 11] MP4 saved: {OUTPUT_MP4}")
    except subprocess.CalledProcessError as e:
        stderr_text = e.stderr.decode("utf-8", errors="ignore") if e.stderr else "unknown error"
        print(f"[STEP 11] FFmpeg conversion failed: {stderr_text[-500:]}")
        return

    # Run ffprobe
    print("[STEP 12] Running ffprobe on final MP4...")
    result = subprocess.run([
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        mp4_path_str,
    ], capture_output=True, text=True)

    print("\n" + "="*60)
    print("FFPROBE OUTPUT:")
    print("="*60)
    try:
        import json
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        format_data = data.get("format", {})
        for s in streams:
            print(f"  Stream: index={s.get('index')}, codec_name={s.get('codec_name')}, codec_type={s.get('codec_type')}, codec_tag_string={s.get('codec_tag_string')}")
        print(f"  Format: filename={format_data.get('filename')}, format_name={format_data.get('format_name')}, duration={format_data.get('duration')}")
    except Exception:
        print(result.stdout)

    video_found = any(s.get("codec_type") == "video" for s in data.get("streams", []))
    audio_found = any(s.get("codec_type") == "audio" for s in data.get("streams", []))

    print("\n" + "="*60)
    print("SUCCESS CRITERIA CHECK:")
    print("="*60)
    print(f"  codec_type=video: {'PASS' if video_found else 'FAIL'}")
    print(f"  codec_type=audio: {'PASS' if audio_found else 'FAIL'}")
    if video_found and audio_found:
        print("  RESULT: SUCCESS - Both video and audio streams detected.")
    else:
        print(f"  RESULT: FAILURE - Only video found: {video_found}, audio: {audio_found}")
        if not audio_found:
            print("  NOTE: If audio is missing, check that the video actually plays.")
            print("  The captureStream API requires the video element to be actively playing.")

    # Clean up temporary .webm
    try:
        OUTPUT_WEBM.unlink(missing_ok=True)
        print(f"[Cleanup] Removed temporary .webm: {OUTPUT_WEBM}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
