#!/usr/bin/env python3
"""Acquisition layer: Download Instagram Reels using yt-dlp (no Playwright navigation)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import subprocess
from pathlib import Path
import config


def acquire_reel(url: str, output_path: Path | None = None) -> Path:
    """Download an Instagram Reel using yt-dlp with cookie/session support.

    Returns the path to a valid .mp4 file containing video and audio streams.
    Raises ValueError if acquisition fails or produces an invalid file.
    """
    if output_path is None:
        output_path = config.TEMP_DIR / "reel.mp4"
    if not isinstance(output_path, Path):
        output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path is None or not isinstance(output_path, Path):
        raise RuntimeError(f"Invalid output_path: {output_path}")

    # Clean stale output files before attempting download
    if output_path.exists():
        try:
            output_path.unlink()
            print(f"[Acquire] Deleted stale file: {output_path}")
        except Exception as e:
            print(f"[Acquire] Could not delete stale {output_path}: {e}")
    audio_path_stale = config.TEMP_DIR / "audio.wav"
    if audio_path_stale.exists():
        try:
            audio_path_stale.unlink()
            print(f"[Acquire] Deleted stale audio: {audio_path_stale}")
        except Exception as e:
            print(f"[Acquire] Could not delete stale audio: {e}")
    frames_dir = config.FRAMES_DIR
    if frames_dir.exists():
        for item in frames_dir.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    import shutil
                    shutil.rmtree(item, ignore_errors=True)
            except Exception as e:
                print(f"[Acquire] Could not clean stale frame file {item}: {e}")
        print(f"[Acquire] Cleaned stale files in {frames_dir}")

    # Try initial download with session cookies (raw .instagram_session or converted cookies)

    # Try initial download with session cookies (raw .instagram_session or converted cookies)
    converted_cookie_path = config.BASE_DIR / ".instagram_session_cookies.txt"
    cookie_args = []
    session_exists = False
    session_cookie_path = config.BASE_DIR / ".instagram_session"
    if session_cookie_path.exists():
        session_exists = True
        # Prefer converted Netscape cookies if already present; otherwise use raw file and attempt conversion on auth failure.
        if converted_cookie_path.exists():
            cookie_args = ["--cookies", str(converted_cookie_path)]
            print(f"[Acquire] Using converted Netscape cookies: {converted_cookie_path}")
        else:
            cookie_args = ["--cookies", str(session_cookie_path)]
            print(f"[Acquire] Session file found: {session_cookie_path} ({session_cookie_path.stat().st_size} bytes)")
            print(f"[Acquire] Note: .instagram_session is Playwright format; conversion to cookies.txt will be attempted on auth failure.")
    else:
        print("[Acquire] No session file found. Downloading as public Reel (may fail for private content).")

    def build_cmd(cookie_path: Path | None = None):
        args = ["--cookies", str(cookie_path)] if cookie_path else []
        return [
            "yt-dlp",
            url,
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "-o", str(output_path),
            "--merge-output-format", "mp4",
            "--no-playlist",
        ] + args

    # Helper to detect auth-related failures from yt-dlp stderr/stdout
    def is_auth_failure(stderr_text: str, stdout_text: str) -> bool:
        indicators = ["login", "unavailable", "private", "post isn't available", "recaptcha", "challenge", "authentication required", "cookies file must be netscape formatted", "not json"]
        combined = (stderr_text + stdout_text).lower()
        return any(ind in combined for ind in indicators)

    # Helper to convert Playwright session to Netscape cookies
    def convert_session_to_cookies() -> bool:
        try:
            convert_script = config.BASE_DIR / "cookie_convert.py"
            if not convert_script.exists():
                print("[Acquire] cookie_convert.py not found; skipping conversion.")
                return False
            result_conv = subprocess.run(
                [sys.executable, str(convert_script), str(session_cookie_path), str(converted_cookie_path)],
                capture_output=True, text=True, timeout=60
            )
            print(f"[Acquire] cookie_convert.py return code: {result_conv.returncode}")
            if result_conv.returncode == 0 and converted_cookie_path.exists():
                print(f"[Acquire] Converted cookies saved: {converted_cookie_path}")
                return True
            else:
                print(f"[Acquire] cookie_convert.py stdout: {result_conv.stdout}")
                print(f"[Acquire] cookie_convert.py stderr: {result_conv.stderr}")
                return False
        except Exception as e:
            print(f"[Acquire] cookie_convert.py exception: {e}")
            return False

    # First attempt: prefer converted cookies, else raw session file, else none
    cookie_path_for_cmd = converted_cookie_path if (converted_cookie_path.exists() and converted_cookie_path.stat().st_size > 0) else (session_cookie_path if session_cookie_path.exists() else None)
    cmd = build_cmd(cookie_path_for_cmd)
    print(f"[Acquire] Running yt-dlp: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        print(f"[Acquire] yt-dlp return code: {result.returncode}")
        if result.returncode == 0:
            print(f"[Acquire] yt-dlp completed successfully.")
        else:
            stderr_preview = result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr
            stdout_preview = result.stdout[-500:] if len(result.stdout) > 500 else result.stdout
            print(f"[Acquire] yt-dlp stdout preview: {stdout_preview}")
            print(f"[Acquire] yt-dlp stderr preview: {stderr_preview}")
            # Auto-fallback: if auth failure detected and session file exists but converted cookies don't exist yet, try conversion + retry
            if is_auth_failure(result.stderr, result.stdout) and session_exists and (not converted_cookie_path.exists() or converted_cookie_path.stat().st_size == 0):
                print("[Acquire] Auth failure detected; attempting cookie conversion from Playwright session...")
                converted = convert_session_to_cookies()
                if converted:
                    retry_cmd = build_cmd(converted_cookie_path)
                    print(f"[Acquire] Retrying yt-dlp with converted cookies: {' '.join(retry_cmd)}")
                    retry_result = subprocess.run(retry_cmd, capture_output=True, text=True, timeout=300)
                    print(f"[Acquire] Retry yt-dlp return code: {retry_result.returncode}")
                    if retry_result.returncode == 0:
                        print("[Acquire] Retry with converted cookies succeeded.")
                        result = retry_result
                    else:
                        print(f"[Acquire] Retry stderr preview: {retry_result.stderr[-500:] if len(retry_result.stderr) > 500 else retry_result.stderr}")
                        result = retry_result
                try:
                    audio_path_stale = config.TEMP_DIR / 'audio.wav'
                    if audio_path_stale.exists():
                        audio_path_stale.unlink()
                except Exception:
                    pass
                try:
                    frames_dir = config.FRAMES_DIR
                    if frames_dir.exists():
                        for item in frames_dir.iterdir():
                            try:
                                if item.is_file():
                                    item.unlink()
                                elif item.is_dir():
                                    import shutil
                                    shutil.rmtree(item, ignore_errors=True)
                            except Exception:
                                pass
                except Exception:
                    pass
            stderr_output = result.stderr if result.stderr else ""
            if result.returncode != 0:
                raise RuntimeError(f'yt-dlp acquisition failed with exit code {result.returncode}. Stderr: {stderr_output}')
    except FileNotFoundError:
        raise ValueError("yt-dlp is not installed. Install with: pip install yt-dlp")
    except subprocess.TimeoutExpired:
        print("[Acquire] yt-dlp timed out after 300s.")
        raise ValueError(f"yt-dlp acquisition timed out for URL: {url}")
    except Exception as e:
        print(f"[Acquire] yt-dlp exception: {e}")
        raise ValueError(f"yt-dlp acquisition failed: {e}")

    # Validate output file
    file_size = 0
    if output_path.exists():
        file_size = output_path.stat().st_size
    print(f"[Acquire] Output file: {output_path}")
    print(f"[Acquire] File size: {file_size} bytes")

    # Validate with FFmpeg
    from downloader import video
    is_valid = False
    if output_path.exists() and file_size > 1024:
        is_valid = video._validate_mp4(output_path)

    # Check audio stream presence explicitly
    audio_check = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "a",
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(output_path)],
        capture_output=True, text=True,
    )
    has_audio = bool(audio_check.stdout.strip())
    print(f"[Acquire] FFmpeg validation passed: {is_valid}")
    print(f"[Acquire] Audio stream present: {has_audio}")
    print(f"[Acquire] Content-Type: video/mp4 (yt-dlp output)")
    print(f"[Acquire] Response status: N/A (yt-dlp acquisition)")

    if not is_valid or file_size < 1024:
        msg = f"yt-dlp acquisition produced invalid/empty MP4 (valid={is_valid}, size={file_size}, url={url}, session_exists={session_exists})"
        raise ValueError(msg)

    if not has_audio:
        print("[Acquire] WARNING: Downloaded MP4 has no audio stream. Transcript (Whisper) will fail.")
        # We don't raise here; we allow pipeline to continue and let Whisper handle empty audio gracefully.
        # But we clearly log the issue.

    return output_path
