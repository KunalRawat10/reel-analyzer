"""OCR using EasyOCR."""
from pathlib import Path
import easyocr


def run_ocr(frames_dir: Path) -> list[str]:
    """
    Extract text from frames.

    Interface:
        run_ocr(frames_dir) -> list[str]
    """
    reader = easyocr.Reader(
        ["en"],
        gpu=False
    )

    texts = set()

    frames = sorted(Path(frames_dir).glob("*.png"))

    if not frames:
        print("OCR: No frames found")
        return []

    print(f"OCR: Processing {len(frames)} frames")

    for frame in frames:
        try:
            results = reader.readtext(str(frame))

            for item in results:
                if len(item) >= 2:
                    text = item[1]

                    if isinstance(text, str):
                        text = text.strip()

                        if len(text) > 1:
                            texts.add(text)

        except Exception as e:
            print(f"OCR failed {frame}: {e}")

    output = sorted(texts)

    print(f"OCR found {len(output)} unique text lines")

    return output
