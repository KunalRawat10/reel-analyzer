"""Browser automation for Instagram Reels."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from playwright.sync_api import sync_playwright, Browser, Page
import time
import config


def launch_browser() -> tuple[Browser, Page]:
    """Launch Chromium with persistent session and high-quality video recording."""
    p = sync_playwright().start()
    browser = p.chromium.launch(
        headless=False,
        args=[
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    )
    # Try to reuse session
    session_path = config.BROWSER_SESSION_PATH
    # Enable high-quality browser tab recording (video + audio)
    context_options = dict(
        record_video_dir=str(config.TEMP_DIR),
        record_video_size={"width": 1920, "height": 1080},
    )
    if session_path.exists():
        context_options["storage_state"] = str(session_path)
    else:
        context_options["storage_state"] = None
    # Remove None values so Playwright doesn't receive storage_state=None
    filtered_options = {k: v for k, v in context_options.items() if v is not None}
    context = browser.new_context(**filtered_options)
    page = context.new_page()
    return browser, page


def open_instagram(page: Page) -> None:
    """Open Instagram homepage."""
    page.goto(config.INSTAGRAM_URL, timeout=30000)
    time.sleep(2)


def open_reel(page: Page, reel_url: str) -> None:
    """Navigate to a Reel URL and wait for playback."""
    # Initialize recording state
    page.__recording_path = None
    # Initialize captured video URLs (kept for diagnostics)
    page.__captured_video_urls = []

    def handle_request(request):
        url = request.url
        # Filter media-related requests
        is_media = any(ext in url for ext in [".mp4", ".m4s", ".mpd", ".m3u8", ".ts", "/video/"])
        has_media_keyword = any(k in url.lower() for k in ["video", "media", "reel", "stream"])
        if not (is_media or has_media_keyword):
            return
        method = request.method
        headers = request.headers
        has_mp4 = ".mp4" in url
        has_m4s = ".m4s" in url
        has_mpd = ".mpd" in url
        has_m3u8 = ".m3u8" in url
        has_bytestart = "bytestart" in url
        has_byteend = "byteend" in url
        # Check request body/headers for init segment indicators
        init_indicators = False
        user_agent = headers.get("user-agent", "")
        if "init" in url.lower() or "moof" in url.lower() or "ftyp" in url.lower():
            init_indicators = True
        print("\n=== MEDIA REQUEST ===")
        print(f"URL: {url}")
        print(f"Method: {method}")
        print(f"Request Headers: {dict(headers)}")
        print(f"Contains .mp4: {has_mp4}")
        print(f"Contains .m4s: {has_m4s}")
        print(f"Contains .mpd: {has_mpd}")
        print(f"Contains .m3u8: {has_m3u8}")
        print(f"Contains bytestart: {has_bytestart}")
        print(f"Contains byteend: {has_byteend}")
        print(f"Init segment indicators: {init_indicators}")

    def handle_response(response):
        url = response.url
        # Filter media-related responses
        is_media = any(ext in url for ext in [".mp4", ".m4s", ".mpd", ".m3u8", ".ts", "/video/"])
        has_media_keyword = any(k in url.lower() for k in ["video", "media", "reel", "stream"])
        if not (is_media or has_media_keyword):
            return
        status = response.status
        headers = response.headers
        content_type = headers.get("content-type", "")
        content_length = headers.get("content-length", "N/A")
        accept_ranges = headers.get("accept-ranges", "N/A")
        method = response.request.method if response.request else "N/A"
        has_mp4 = ".mp4" in url
        has_m4s = ".m4s" in url
        has_mpd = ".mpd" in url
        has_m3u8 = ".m3u8" in url
        has_bytestart = "bytestart" in url
        has_byteend = "byteend" in url
        init_indicators = False
        if "init" in url.lower() or "moof" in url.lower() or "ftyp" in url.lower():
            init_indicators = True
        # Also check response headers/body references
        response_headers_dict = dict(headers)
        print("\n=== MEDIA RESPONSE ===")
        print(f"URL: {url}")
        print(f"Request Method: {method}")
        print(f"Status Code: {status}")
        print(f"Content-Type: {content_type}")
        print(f"Content-Length: {content_length}")
        print(f"Accept-Ranges: {accept_ranges}")
        print(f"Response Headers: {response_headers_dict}")
        print(f"Contains .mp4: {has_mp4}")
        print(f"Contains .m4s: {has_m4s}")
        print(f"Contains .mpd: {has_mpd}")
        print(f"Contains .m3u8: {has_m3u8}")
        print(f"Contains bytestart: {has_bytestart}")
        print(f"Contains byteend: {has_byteend}")
        print(f"Init segment indicators: {init_indicators}")

    # Intercept request and response events for media requests
    page.on("request", handle_request)
    page.on("response", handle_response)

    print(f"Navigating to {reel_url}")
    page.goto(reel_url, timeout=60000)
    time.sleep(3)
    # Wait for video element
    try:
        page.wait_for_selector("video", timeout=config.VIDEO_TIMEOUT * 1000)
        print("Video element found.")
    except Exception as e:
        print(f"Video not found immediately: {e}")
    # Try clicking to start playback to trigger media network requests and recording
    try:
        video = page.query_selector("video")
        if video:
            page.evaluate("document.querySelector('video').play()")
        time.sleep(3)
    except Exception as e:
        print(f"Playback start issue: {e}")

    # Recording management: wait until Reel ends or 90 seconds elapsed
    print("[Recording] Recording started.")
    start_time = time.time()
    recording_started = True
    while True:
        # Check if video has ended
        try:
            ended = page.evaluate("""
                () => {
                    const v = document.querySelector('video');
                    return v ? (v.ended || (v.duration > 0 && v.currentTime >= v.duration - 0.5)) : false;
                }
            """)
        except Exception:
            ended = False
        elapsed = time.time() - start_time
        if ended:
            print(f"[Recording] Recording stopped: Reel ended at {elapsed:.1f}s.")
            break
        if elapsed >= 90:
            print(f"[Recording] Recording stopped: 90-second timeout reached ({elapsed:.1f}s).")
            break
        time.sleep(2)
    duration = time.time() - start_time
    print(f"[Recording] Recording duration: {duration:.1f}s.")

    # Find the most recent .webm file produced by Playwright recording
    import subprocess
    temp_dir = Path(config.TEMP_DIR)
    webm_files = sorted(temp_dir.glob("*.webm"), key=lambda f: f.stat().st_mtime, reverse=True)
    if webm_files:
        webm_path = webm_files[0]
        output_mp4 = config.TEMP_DIR / "reel.mp4"
        print(f"[Recording] Source .webm found: {webm_path}")
        print(f"[Recording] Converting to MP4: {output_mp4}")
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(webm_path),
                    "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                    "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart",
                    str(output_mp4),
                ],
                capture_output=True, text=True, timeout=180,
            )
            print(f"[Recording] FFmpeg conversion return code: {result.returncode}")
            if result.returncode != 0:
                stderr_preview = result.stderr[-800:] if len(result.stderr) > 800 else result.stderr
                print(f"[Recording] FFmpeg stderr preview: {stderr_preview}")
        except Exception as conv_e:
            print(f"[Recording] FFmpeg conversion exception: {conv_e}")

        # Validate the converted MP4
        from downloader import video as video_downloader
        file_size = 0
        if output_mp4.exists():
            file_size = output_mp4.stat().st_size
        is_valid = False
        if output_mp4.exists() and file_size > 1024:
            is_valid = video_downloader._validate_mp4(output_mp4)
        print(f"[Recording] Output path: {output_mp4}")
        print(f"[Recording] File size: {file_size} bytes")
        print(f"[Recording] FFmpeg validation: {is_valid}")

        if is_valid and file_size > 1024:
            page.__recording_path = str(output_mp4)
            print(f"[Recording] Recording validated and saved: {output_mp4}")
        else:
            msg = (
                f"Recording failed: converted MP4 is invalid or too small "
                f"(valid={is_valid}, size={file_size} bytes, duration={duration:.1f}s, source={webm_path})"
            )
            print(f"[Recording] [ERROR] {msg}")
            raise ValueError(msg)
    else:
        msg = f"Recording failed: no .webm file found in {temp_dir} after {duration:.1f}s."
        print(f"[Recording] [ERROR] {msg}")
        raise ValueError(msg)


def get_video_source(page: Page) -> str | None:
    """Return recorded video path if available; otherwise fall back to network capture."""
    # Priority 1: return the validated browser recording (.mp4)
    recording_path = getattr(page, "__recording_path", None)
    if recording_path:
        path = Path(recording_path)
        if path.exists():
            print(f"[Recording] Returning recorded video path: {path}")
            return str(path)
    # Priority 2: try intercepted network responses (legacy fallback)
    captured = getattr(page, "__captured_video_urls", [])
    if captured:
        # Filter only URLs that end with .mp4/.m4v or contain video host patterns
        real_urls = [
            url for url in captured
            if ".mp4" in url or ".m4v" in url or "video/" in url
        ]
        if real_urls:
            # Return the last (most recent) captured real video URL
            url = real_urls[-1]
            print(f"[Network Intercept] Returning real video URL: {url}")
            return url
        # If we have URLs but none match .mp4 explicitly, return the last captured
        url = captured[-1]
        if url.startswith("blob:"):
            pass  # Skip blob URLs
        else:
            print(f"[Network Intercept] Returning captured URL: {url}")
            return url

    # Fallback: try reading from the DOM (may return blob: URLs which are not downloadable)
    try:
        src = page.evaluate("""
            () => {
                const video = document.querySelector('video');
                if (video && video.src) return video.src;
                const sources = document.querySelectorAll('video source');
                for (let s of sources) {
                    if (s.src) return s.src;
                }
                return null;
            }
        """)
        # Only return DOM source if it's a real (non-blob) URL
        if src and not src.startswith("blob:"):
            return src
        elif src and src.startswith("blob:"):
            print(f"[Warning] DOM returned blob URL (not downloadable): {src}")
            return None
    except Exception as e:
        print(f"Could not get video source from DOM: {e}")
    return None


def save_session(browser: Browser, page: Page) -> None:
    """Save current session state."""
    context = page.context
    context.storage_state(path=str(config.BROWSER_SESSION_PATH))
    print(f"Session saved to {config.BROWSER_SESSION_PATH}")
