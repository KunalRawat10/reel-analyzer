"""Video download and streaming with fragment detection and range merging."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import requests
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import config


def _validate_mp4(file_path: Path) -> bool:
    """Validate MP4 using FFmpeg. Returns True if valid."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(file_path), "-f", "null", "-"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # FFmpeg returns 0 for valid files even with warnings; check stderr for fatal errors
        stderr_lower = result.stderr.lower()
        has_fatal = any(k in stderr_lower for k in [
            "invalid data", "could not find corresponding trex",
            "moov atom not found", "error reading header",
            "invalid mp4", "corrupt", "truncated"
        ])
        # Also check if output file has a reasonable size (> 1KB)
        file_size = file_path.stat().st_size
        is_too_small = file_size < 1024
        return not has_fatal and not is_too_small and result.returncode in (0, 1)
    except Exception:
        return False


def download_video(url: str, output_path: Path | None = None) -> Path:
    """Download video from URL to local file, or validate an existing recording file."""
    if output_path is None:
        output_path = config.TEMP_DIR / "reel.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # If url refers to the browser recording (local file path), validate and return it
    if url and (url.startswith("/") or url.startswith("C:") or url.startswith("\\") or url.startswith(".") or url.startswith("/") or url.startswith("C:")):
        # It's likely a file path; check directly
        file_path = Path(url)
        if file_path.exists() and file_path.is_file():
            print(f"[Video Download] Using recorded file path: {file_path}")
            file_size = file_path.stat().st_size
            is_valid = _validate_mp4(file_path)
            print(f"[Video Download] File size: {file_size} bytes")
            print(f"[Video Download] Content-Type: video/mp4 (recorded file)")
            print(f"[Video Download] Response status: N/A (local recording file)")
            print(f"[Video Download] FFmpeg validation passed: {is_valid}")
            if is_valid and file_size > 1024:
                # Copy or link to output_path if different
                if file_path.resolve() != output_path.resolve():
                    import shutil
                    shutil.copy2(str(file_path), str(output_path))
                    print(f"[Video Download] Copied recording to: {output_path}")
                else:
                    print(f"[Video Download] Recording already at output path: {output_path}")
                return output_path
            else:
                raise ValueError(f"Recorded file is invalid or too small: {file_path} (valid={is_valid}, size={file_size} bytes)")
        else:
            # Try the default recording location
            default_recorded = config.TEMP_DIR / "reel.mp4"
            if default_recorded.exists():
                file_path = default_recorded
                file_size = file_path.stat().st_size
                is_valid = _validate_mp4(file_path)
                print(f"[Video Download] Using default recording: {file_path}")
                print(f"[Video Download] File size: {file_size} bytes")
                print(f"[Video Download] Content-Type: video/mp4 (recorded file)")
                print(f"[Video Download] Response status: N/A (local recording file)")
                print(f"[Video Download] FFmpeg validation passed: {is_valid}")
                if is_valid and file_size > 1024:
                    if file_path.resolve() != output_path.resolve():
                        import shutil
                        shutil.copy2(str(file_path), str(output_path))
                    return output_path
                else:
                    raise ValueError(f"Recorded file is invalid or too small: {file_path} (valid={is_valid}, size={file_size} bytes)")
            else:
                # Not a file path; fall through to URL download
                pass

    # Normal URL download logic continues (including fragment detection)

    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    has_range_params = "bytestart" in params or "byteend" in params

    # Print initial URL info
    print(f"[Video Download] Original URL: {url}")
    print(f"[Video Download] Contains bytestart/byteend: {has_range_params}")

    # Try to reconstruct full URL by removing range query parameters
    clean_params = {k: v for k, v in params.items() if k not in ("bytestart", "byteend")}
    clean_query = urlencode(clean_params, doseq=True)
    clean_url = urlunparse(parsed._replace(query=clean_query))

    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    final_path = output_path

    response = None
    try:
        # Strategy 1: Try full file download (without range params)
        print(f"[Video Download] Attempting clean URL: {clean_url}")
        try:
            response = requests.get(clean_url, stream=True, timeout=60)
            print(f"[Video Download] Response status: {response.status_code}")
            print(f"[Video Download] Content-Type: {response.headers.get('content-type', 'unknown')}")
            response.raise_for_status()
            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        except requests.RequestException as e:
            print(f"[Video Download] Clean URL download failed: {e}")
            response = None
            # If clean URL failed, fall through to range-based approach

        # Strategy 2: If clean URL produced something, validate it
        if temp_path.exists() and temp_path.stat().st_size > 0:
            file_size = temp_path.stat().st_size
            print(f"[Video Download] File size: {file_size} bytes")
            is_valid = _validate_mp4(temp_path)
            print(f"[Video Download] FFmpeg validation passed: {is_valid}")

            if is_valid:
                # Move temp to final path
                temp_path.rename(final_path)
                print(f"[Video Download] Saved valid MP4: {final_path}")
                return final_path
            else:
                print(f"[Video Download] File is not a valid MP4 (likely fragment). Trying range merge...")
                # Clear temp for range merge attempt
                temp_path.unlink(missing_ok=True)
        else:
            print(f"[Video Download] Clean URL produced empty file.")

        # Strategy 3: Range-based download (if clean URL failed or produced fragment)
        # Make a HEAD request to determine if server supports ranges
        head_resp = None
        try:
            head_resp = requests.head(clean_url, timeout=30)
            print(f"[Video Download] HEAD status: {head_resp.status_code}")
            print(f"[Video Download] HEAD Content-Type: {head_resp.headers.get('content-type', 'unknown')}")
            accept_ranges = head_resp.headers.get("accept-ranges", "none")
            content_length = head_resp.headers.get("content-length")
            print(f"[Video Download] HEAD Accept-Ranges: {accept_ranges}")
            print(f"[Video Download] HEAD Content-Length: {content_length}")
        except Exception as e:
            print(f"[Video Download] HEAD request failed: {e}")

        # If server supports ranges and we know total length, download in chunks
        if head_resp and head_resp.status_code == 200:
            total_length_str = head_resp.headers.get("content-length")
            if total_length_str and total_length_str.isdigit():
                total_length = int(total_length_str)
                chunk_size = min(total_length, 1024 * 1024) if total_length > 0 else 1024 * 1024
                chunk_size = max(chunk_size, 1024 * 1024)

                merged_path = output_path.with_suffix(output_path.suffix + ".merged.tmp")
                with open(merged_path, "wb") as out:
                    start = 0
                    chunk_index = 0
                    while start < total_length:
                        end = min(start + chunk_size - 1, total_length - 1)
                        range_header = f"bytes={start}-{end}"
                        print(f"[Video Download] Downloading range: {range_header}")
                        range_resp = requests.get(
                            clean_url,
                            headers={"Range": range_header},
                            stream=True,
                            timeout=60,
                        )
                        print(f"[Video Download] Range response status: {range_resp.status_code}")
                        print(f"[Video Download] Range Content-Type: {range_resp.headers.get('content-type', 'unknown')}")
                        range_resp.raise_for_status()
                        for chunk in range_resp.iter_content(chunk_size=8192):
                            out.write(chunk)
                        start = end + 1
                        chunk_index += 1
                        # Stop after a reasonable number of chunks to avoid infinite loops
                        if chunk_index > 200:
                            print("[Video Download] Too many chunks; stopping range download.")
                            break

                # Validate merged file
                file_size = merged_path.stat().st_size
                print(f"[Video Download] Merged file size: {file_size} bytes")
                is_valid = _validate_mp4(merged_path)
                print(f"[Video Download] FFmpeg validation passed: {is_valid}")

                if is_valid and file_size > 1024:
                    merged_path.rename(final_path)
                    print(f"[Video Download] Saved valid merged MP4: {final_path}")
                    return final_path
                else:
                    # Even after range merge, file is invalid -> raise clear exception
                    msg = (
                        f"Downloaded file is only a fragment (size: {file_size} bytes, "
                        f"valid MP4: False, original URL had bytestart/byteend: {has_range_params}). "
                        f"The intercepted URL '{url}' points to a byte-range segment, not a complete video file. "
                        f"Range merge produced an invalid MP4. The CDN may require sequential segment assembly (DASH/MPD) which is not fully supported."
                    )
                    # Clean up temporary files
                    merged_path.unlink(missing_ok=True)
                    temp_path.unlink(missing_ok=True)
                    raise ValueError(f"Fragment detected: {msg}")
            else:
                # No total length info; try downloading the exact range from URL params
                # If we have exact range params, download just that segment and raise fragment exception
                range_start = params.get("bytestart", [None])[0]
                range_end = params.get("byteend", [None])[0]
                if range_start and range_end:
                    msg = (
                        f"Fragment URL detected (bytestart={range_start}, byteend={range_end}). "
                        f"Only a partial byte-range segment was downloaded. The full MP4 cannot be reconstructed "
                        f"without the complete segment manifest (MPD/M3U8). Original URL: {url}"
                    )
                    # Write nothing or keep partial (raise instead)
                    temp_path.unlink(missing_ok=True)
                    raise ValueError(msg)
                else:
                    msg = f"No range parameters found but download produced invalid/empty file. URL: {url}"
                    temp_path.unlink(missing_ok=True)
                    raise ValueError(msg)
        else:
            # HEAD request failed or no range support; raise exception clearly
            file_size = temp_path.stat().st_size if temp_path.exists() else 0
            msg = (
                f"Fragment detected or download failed. File size: {file_size} bytes. "
                f"Response status: {response.status_code if response else 'N/A'}. "
                f"Content-Type: {response.headers.get('content-type') if response else 'unknown'}. "
                f"FFmpeg validation: False. URL: {url}"
            )
            temp_path.unlink(missing_ok=True)
            raise ValueError(msg)
    finally:
        # Clean up temporary files if something went wrong
        if temp_path.exists() and not final_path.exists():
            # Only clean temp if final wasn't successfully created
            pass  # Keep for debugging if needed
        # If final path exists but is invalid, it will be handled by exception above

    # At this point final_path should exist and be valid
    file_size = final_path.stat().st_size
    print(f"[Video Download] Final file: {final_path}")
    print(f"[Video Download] Final file size: {file_size} bytes")
    # Final validation check
    is_valid = _validate_mp4(final_path)
    print(f"[Video Download] Final FFmpeg validation passed: {is_valid}")
    if not is_valid:
        raise ValueError(f"Downloaded file is not a valid MP4 (fragment or corrupt): {final_path}")
    return final_path
