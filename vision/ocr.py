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

_reader = None


def get_reader():
    global _reader
    if _reader is None:
        print("OCR: Loading reader...")
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def _hash_distance(hash1: bytes, hash2: bytes) -> int:
    return sum(b1 ^ b2 for b1, b2 in zip(hash1, hash2))


def _average_hash(img: np.ndarray) -> bytes:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
    avg = small.mean()
    bits = (small > avg).astype(np.uint8)
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


def _merge_nearby(results: list, max_gap: int = 40) -> list:
    if not results:
        return results
    items = []
    for r in results:
        if len(r) >= 2:
            bbox = r[0]
            text = r[1]
            conf = r[2] if len(r) >= 3 else 1.0
            items.append((bbox, text, conf))
    items.sort(key=lambda i: min(p[0] for p in i[0]))
    merged = []
    current_group = [items[0]] if items else []
    for item in items[1:]:
        last_box = current_group[-1][0]
        current_box = item[0]
        last_x = max(p[0] for p in last_box)
        current_x = min(p[0] for p in current_box)
        gap = current_x - last_x
        last_y_center = sum(p[1] for p in last_box) / len(last_box)
        current_y_center = sum(p[1] for p in current_box) / len(current_box)
        v_gap = abs(current_y_center - last_y_center)
        if gap <= max_gap and v_gap <= 25:
            current_group.append(item)
        else:
            texts = [t for _, t, _ in current_group]
            clean_texts = [t for t in texts if len(t.strip()) > 0 and not _is_isolated_symbol(t) and not _is_numbers_only(t)]
            if clean_texts:
                merged_text = " ".join(clean_texts)
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
    reader = get_reader()
    texts = set()
    frames = sorted(Path(frames_dir).glob("*.png"))
    if not frames:
        print("OCR: No frames found")
        return []
    total = len(frames)
    skipped = 0
    ocr_processed = 0
    subtitle_crop_successes = 0
    fallback_count = 0
    full_frame_ocr_calls = 0
    print(f"OCR: Processing {total} frames")
    prev_hash = None
    start_time = time.time()
    for idx, frame in enumerate(frames, start=1):
        try:
            img = cv2.imread(str(frame))
            if img is None:
                print("OCR: Could not read frame")
                continue

            h, w = img.shape[:2]
            resized = cv2.resize(img, (w // 2, h // 2), interpolation=cv2.INTER_AREA)

            current_hash = _average_hash(resized)
            if prev_hash is not None and _hash_distance(prev_hash, current_hash) <= 5:
                skipped += 1
                print("OCR: Skipped duplicate")
                del resized
                del img
                prev_hash = current_hash
                continue
            prev_hash = current_hash

            ocr_processed += 1
            print(f"OCR: Processing frame {idx}/{total}")

            rh, rw = resized.shape[:2]
            crop_start = int(rh * 0.62)
            subtitle_crop = resized[crop_start:, :]

            margin_px = int(min(rw, rh) * 0.08)

            subtitle_crop_valid = subtitle_crop is not None and subtitle_crop.shape[0] > 0 and subtitle_crop.shape[1] > 0 and subtitle_crop.size > 0

            if subtitle_crop_valid:
                subtitle_results = reader.readtext(subtitle_crop)
                filtered_subtitle = []
                for r in subtitle_results:
                    if len(r) >= 2:
                        bbox = r[0]
                        text = r[1]
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
                        if min_x < margin_px or max_x > rw - margin_px:
                            stripped = text.strip() if isinstance(text, str) else ""
                            if len(stripped) < 4 or _is_ui_text(stripped):
                                continue
                        text_val = r[1]
                        if isinstance(text_val, str):
                            stripped = text_val.strip()
                            if len(stripped) < 4 or _is_ui_text(stripped):
                                continue
                        confidence = float(r[2]) if len(r) >= 3 else 1.0
                        if confidence < 0.60:
                            continue
                        filtered_subtitle.append(r)

                results_to_use = filtered_subtitle
                if results_to_use:
                    subtitle_crop_successes += 1
                    print("OCR: Subtitle success")
                else:
                    fallback_count += 1
                    print("OCR: Fallback")
                    full_results = reader.readtext(resized)
                    full_frame_ocr_calls += 1
                    filtered_full = []
                    for r in full_results:
                        if len(r) >= 2:
                            bbox = r[0]
                            text = r[1]
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
                            if min_x < margin_px or max_x > rw - margin_px:
                                stripped = text.strip() if isinstance(text, str) else ""
                                if len(stripped) < 4 or _is_ui_text(stripped):
                                    continue
                            text_val = r[1]
                            if isinstance(text_val, str):
                                stripped = text_val.strip()
                                if len(stripped) < 4 or _is_ui_text(stripped):
                                    continue
                            confidence = float(r[2]) if len(r) >= 3 else 1.0
                            if confidence < 0.60:
                                continue
                            filtered_full.append(r)
                    results_to_use = filtered_full
            else:
                fallback_count += 1
                print("OCR: Fallback")
                full_results = reader.readtext(resized)
                full_frame_ocr_calls += 1
                filtered_full = []
                for r in full_results:
                    if len(r) >= 2:
                        bbox = r[0]
                        text = r[1]
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
                        if min_x < margin_px or max_x > rw - margin_px:
                            stripped = text.strip() if isinstance(text, str) else ""
                            if len(stripped) < 4 or _is_ui_text(stripped):
                                continue
                        text_val = r[1]
                        if isinstance(text_val, str):
                            stripped = text_val.strip()
                            if len(stripped) < 4 or _is_ui_text(stripped):
                                continue
                        confidence = float(r[2]) if len(r) >= 3 else 1.0
                        if confidence < 0.60:
                            continue
                        filtered_full.append(r)
                results_to_use = filtered_full

            merged_results = _merge_nearby(results_to_use)

            count = 0
            for item in merged_results:
                bbox, text, confidence = item
                confidence_val = confidence if isinstance(confidence, float) else (float(confidence) if isinstance(confidence, (int, float, str)) else 1.0)
                if isinstance(text, str) and text:
                    stripped = text.strip()
                    if len(stripped) >= 4 and not _is_numbers_only(stripped) and not _is_isolated_symbol(stripped) and confidence_val >= 0.60:
                        if not _is_ui_text(stripped):
                            normalized = _normalize(stripped)
                            texts.add(normalized)
                            count += 1

            del subtitle_crop
            del resized
            del img

            print(f"OCR: Completed")
        except Exception as e:
            print(f"OCR failed: {e}")
            try:
                del subtitle_crop
            except NameError:
                pass
            try:
                del resized
            except NameError:
                pass
            try:
                del img
            except NameError:
                pass
            continue
    output = sorted(texts)
    elapsed = time.time() - start_time
    print("Frames:")
    print(f"{total}")
    print("Processed:")
    print(f"{ocr_processed}")
    print("Skipped:")
    print(f"{skipped}")
    print("Subtitle successes:")
    print(f"{subtitle_crop_successes}")
    print("Fallbacks:")
    print(f"{fallback_count}")
    print("Full-frame OCR calls:")
    print(f"{full_frame_ocr_calls}")
    print("Unique sentences:")
    print(f"{len(output)}")
    print(f"Runtime: {elapsed:.2f} sec")
    return output
