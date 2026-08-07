"""OCR using EasyOCR — optimized pipeline."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import time
import easyocr
import cv2
import numpy as np

UI_BLACKLIST = {
    "home", "search", "reels", "profile", "following", "like", "likes",
    "comment", "comments", "share", "message", "messages", "explore",
    "sponsored", "follow", "followers", "following", "next", "previous",
    "play", "pause", "volume", "mute", "unmute",
}


def _hash_distance(hash1: bytes, hash2: bytes) -> int:
    # Compute Hamming distance between two byte hashes of same length
    return sum(b1 ^ b2 for b1, b2 in zip(hash1, hash2))


def _average_hash(img: np.ndarray) -> bytes:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
    avg = resized.mean()
    bits = (resized > avg).astype(np.uint8)
    return bits.tobytes()


def _normalize(text: str) -> str:
    text = text.lower()
    text = " ".join(text.split())
    return text


def _is_ui_text(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 4:
        return True
    lower = stripped.lower()
    for word in UI_BLACKLIST:
        if word in lower:
            return True
    return False


def _is_numbers_only(text: str) -> bool:
    stripped = text.replace(" ", "").replace(",", "").replace(".", "")
    return stripped and all(ch.isdigit() or ch in "$€£¥" for ch in stripped)


def _is_isolated_symbol(text: str) -> bool:
    stripped = text.strip()
    return len(stripped) <= 3 and not any(ch.isalpha() for ch in stripped)


def _box_area(box: list) -> int:
    # EasyOCR box format: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
    pts = np.array(box, dtype=np.int32)
    area = cv2.contourArea(pts.reshape((-1, 1, 2)))
    return int(area)


def _merge_nearby(results: list, img_shape: tuple, max_gap: int = 40) -> list:
    # Sort results horizontally by first point x-coordinate, then group nearby boxes into sentences
    if not results:
        return results
    # Extract (bbox, text, confidence) tuples
    items = []
    for r in results:
        if len(r) >= 2:
            bbox = r[0]
            text = r[1]
            conf = r[2] if len(r) >= 3 else 1.0
            items.append((bbox, text, conf))
    # Sort by x1 coordinate
    items.sort(key=lambda i: min(p[0] for p in i[0]))
    # Simple grouping: merge items with small horizontal gap
    merged = []
    current_group = [items[0]] if items else []
    for item in items[1:]:
        last_box = current_group[-1][0]
        current_box = item[0]
        last_x = max(p[0] for p in last_box)
        current_x = min(p[0] for p in current_box)
        gap = current_x - last_x
        # Vertical distance between centers
        last_y_center = sum(p[1] for p in last_box) / len(last_box)
        current_y_center = sum(p[1] for p in current_box) / len(current_box)
        v_gap = abs(current_y_center - last_y_center)
        # Merge on both horizontal and vertical proximity so wrapped subtitles become one sentence
        if gap <= max_gap and v_gap <= max_gap:
            current_group.append(item)
        else:
            # Merge texts in group
            texts = [t for _, t, _ in current_group]
            # Filter out empty/symbol-only pieces before merging
            clean_texts = [t for t in texts if len(t.strip()) > 0 and not _is_isolated_symbol(t) and not _is_numbers_only(t)]
            if clean_texts:
                merged_text = " ".join(clean_texts)
                # Use first bbox as representative
                merged.append((current_group[0][0], merged_text, max(c for _, _, c in current_group)))
            current_group = [item]
    if current_group:
        texts = [t for _, t, _ in current_group]
        clean_texts = [t for t in texts if len(t.strip()) > 0 and not _is_isolated_symbol(t) and not _is_numbers_only(t)]
        if clean_texts:
            merged_text = " ".join(clean_texts)
            merged.append((current_group[0][0], merged_text, max(c for _, _, c in current_group)))
    return merged


def run_ocr(frames_dir: Path) -> list[str]:
    reader = easyocr.Reader(["en"], gpu=False)
    texts = set()
    original_texts = {}
    frames = sorted(Path(frames_dir).glob("*.png"))
    if not frames:
        print("OCR: No frames found")
        return []
    total = len(frames)
    skipped = 0
    ocr_processed = 0
    subtitle_crop_successes = 0
    fallback_count = 0
    print(f"OCR: Processing {total} frames (0.5 FPS rate)")
    prev_hash = None
    start_time = time.time()
    for idx, frame in enumerate(frames, start=1):
        try:
            img = cv2.imread(str(frame))
            if img is None:
                print(f"OCR: Could not read frame {frame.name}")
                continue

            # Resize to ~50% before any comparison or OCR
            h, w = img.shape[:2]
            resized = cv2.resize(img, (w // 2, h // 2), interpolation=cv2.INTER_AREA)

            current_hash = _average_hash(resized)
            if prev_hash is not None and _hash_distance(prev_hash, current_hash) <= 5:
                skipped += 1
                print(f"OCR: Skipping duplicate frame {frame.name}")
                continue
            prev_hash = current_hash

            ocr_processed += 1
            print(f"OCR: Processing frame {idx}/{total}")

            # Get full image dimensions for filtering
            img_h, img_w = img.shape[:2]
            margin_px = int(min(img_w, img_h) * 0.08)

            # Primary: subtitle crop (bottom 38%)
            crop_h = int(img_h * 0.38)
            crop_y_start = max(img_h - crop_h, 0)
            subtitle_crop = resized[crop_y_start:img_h, 0:img_w]

            # Try subtitle crop first (NumPy array directly, no PNG decode)
            subtitle_results = reader.readtext(subtitle_crop)
            # Filter subtitle results by minimum width, height, aspect ratio (reject only tiny UI boxes)
            filtered_subtitle = []
            for r in subtitle_results:
                if len(r) >= 2:
                    bbox = r[0]
                    x_points = [p[0] for p in bbox]
                    y_points = [p[1] for p in bbox]
                    min_x, max_x = min(x_points), max(x_points)
                    min_y, max_y = min(y_points), max(y_points)
                    box_w = max_x - min_x
                    box_h = max_y - min_y
                    if box_w < 15 or box_h < 8:
                        continue
                    aspect = box_w / max(box_h, 1)
                    if aspect < 0.05 or aspect > 40:
                        continue
                    # Ignore boxes near left/right margins (UI elements)
                    margin_px = int(min(img_w, img_h) * 0.08)
                    if min_x < margin_px or max_x > img_w - margin_px:
                        text = r[1]
                        if isinstance(text, str):
                            stripped = text.strip()
                            if len(stripped) < 4 or _is_ui_text(stripped):
                                continue
                    text = r[1]
                    if isinstance(text, str):
                        stripped = text.strip()
                        if len(stripped) < 4 or _is_ui_text(stripped):
                            continue
                    filtered_subtitle.append(r)

            results_to_use = filtered_subtitle
            if results_to_use:
                subtitle_crop_successes += 1

            # Fallback: full resized image if subtitle crop yields nothing useful
            if not results_to_use:
                fallback_count += 1
                print(f"OCR: Falling back to full frame {frame.name}")
                full_results = reader.readtext(resized)
                filtered_full = []
                for r in full_results:
                    if len(r) >= 2:
                        bbox = r[0]
                        x_points = [p[0] for p in bbox]
                        y_points = [p[1] for p in bbox]
                        min_x, max_x = min(x_points), max(x_points)
                        min_y, max_y = min(y_points), max(y_points)
                        box_w = max_x - min_x
                        box_h = max_y - min_y
                        if box_w < 15 or box_h < 8:
                            continue
                        aspect = box_w / max(box_h, 1)
                        if aspect < 0.05 or aspect > 40:
                            continue
                        margin_px = int(min(img_w, img_h) * 0.08)
                        if min_x < margin_px or max_x > img_w - margin_px:
                            text = r[1]
                            if isinstance(text, str):
                                stripped = text.strip()
                                if len(stripped) < 4 or _is_ui_text(stripped):
                                    continue
                        text = r[1]
                        if isinstance(text, str):
                            stripped = text.strip()
                            if len(stripped) < 4 or _is_ui_text(stripped):
                                continue
                        confidence = float(r[2]) if len(r) >= 3 else 1.0
                        if confidence < 0.60:
                            continue
                        filtered_full.append(r)
                results_to_use = filtered_full

            # Merge nearby boxes into subtitle sentences
            merged_results = _merge_nearby(results_to_use, img.shape)

            count = 0
            for item in merged_results:
                bbox, text, confidence = item
                confidence_val = confidence if isinstance(confidence, float) else (float(confidence) if isinstance(confidence, (int, float, str)) else 1.0)
                if isinstance(text, str) and text:
                    stripped = text.strip()
                    if len(stripped) >= 4 and not _is_numbers_only(stripped) and not _is_isolated_symbol(stripped) and confidence_val >= 0.60:
                        # Filter out common UI text after merge
                        if not _is_ui_text(stripped):
                            normalized = _normalize(stripped)
                            texts.add(normalized)
                            original_texts[normalized] = stripped
                            count += 1
            print(f"OCR: Extracted {count} text regions from {frame.name}")
        except Exception as e:
            print(f"OCR failed {frame}: {e}")
            continue
    output = sorted(texts)
    elapsed = time.time() - start_time
    print(f"Frames total: {total}")
    print(f"Frames skipped: {skipped}")
    print(f"Frames OCR processed: {ocr_processed}")
    print(f"Subtitle crop successes: {subtitle_crop_successes}")
    print(f"Fallback count: {fallback_count}")
    print(f"Unique OCR sentences: {len(output)}")
    print(f"OCR runtime: {elapsed:.2f} seconds")
    print(f"OCR completed in {elapsed:.2f} seconds. OCR found {len(output)} unique text lines.")
    return output
