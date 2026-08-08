#!/usr/bin/env python3
"""Streamlit application for Instagram Reel Analyzer."""
import streamlit as st
import sys
from pathlib import Path
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config

import acquire
from downloader import video
from audio import extract_audio
from whisper import transcribe
from vision import frames, ocr
from parser import regex, merge
from summarizer import summarize
from storage import save_json, save_md


def reset_state():
    st.session_state.clear()


def main():
    st.set_page_config(page_title="Reel Analyzer", layout="wide")
    st.title("AI-Powered Instagram Reel Analyzer")
    st.write("Paste an Instagram Reel URL and click Analyze to process it locally.")

    # Sidebar settings
    with st.sidebar:
        st.subheader("Settings")
        llm_mode = st.selectbox("LLM Mode", ["local", "cloud"], index=0)
        config.LLM_MODE = llm_mode
        if llm_mode == "local":
            config.OLLAMA_MODEL = st.text_input("Ollama Model", value=config.OLLAMA_MODEL)
        else:
            config.CLOUD_API_KEY = st.text_input("Cloud API Key", value=config.CLOUD_API_KEY, type="password")
            config.CLOUD_MODEL = st.text_input("Cloud Model", value=config.CLOUD_MODEL)
        model_size = st.selectbox("Whisper Model", ["tiny", "base", "small", "medium"], index=2)
        config.WHISPER_MODEL_SIZE = model_size
        st.info("Using local processing where possible.")

    reel_url = st.text_input("Instagram Reel URL", placeholder="https://www.instagram.com/reel/...")

    if st.button("Analyze"):
        if not reel_url:
            st.error("Please enter a Reel URL.")
            return

        progress = st.progress(0)
        status = st.empty()

        def update(step, total, msg):
            progress.progress(step / total)
            status.write(msg)

        total_steps = 7
        timings = {}
        statuses = {}
        pipeline_start = time.time()
        try:
            # Step 1: Acquisition (yt-dlp)
            update(1, total_steps, "Acquiring Reel media via yt-dlp...")
            stage_name = "Download"
            stage_start = time.time()
            try:
                video_path = acquire.acquire_reel(reel_url, config.TEMP_DIR / "reel.mp4")
                timings[stage_name] = time.time() - stage_start
                statuses[stage_name] = "SUCCESS"
            except Exception as e:
                timings[stage_name] = time.time() - stage_start
                statuses[stage_name] = "FAILED"
                print(f"Stage failed: {stage_name}")
                print(f"Exception: {e}")
                raise

            # If acquisition produced an invalid/empty file, raise clearly
            if not video_path.exists() or video_path.stat().st_size == 0:
                raise ValueError(f"Acquisition produced empty or missing file. URL: {reel_url}. Check yt-dlp, cookies, or network.")

            # Step 2: Audio
            update(2, total_steps, "Extracting audio...")
            stage_name = "Audio Extraction"
            stage_start = time.time()
            try:
                audio_path = extract_audio.extract_audio(video_path, config.AUDIO_FILE)
                timings[stage_name] = time.time() - stage_start
                statuses[stage_name] = "SUCCESS"
            except Exception as e:
                timings[stage_name] = time.time() - stage_start
                statuses[stage_name] = "FAILED"
                print(f"Stage failed: {stage_name}")
                print(f"Exception: {e}")
                raise

            # Step 3: Transcribe
            update(3, total_steps, "Transcribing audio...")
            stage_name = "Whisper"
            stage_start = time.time()
            try:
                transcript_result = transcribe.transcribe(str(audio_path), model_size=config.WHISPER_MODEL_SIZE)
                transcript_text = transcript_result.get("text", "")
                timings[stage_name] = time.time() - stage_start
                statuses[stage_name] = "SUCCESS"
            except Exception as e:
                timings[stage_name] = time.time() - stage_start
                statuses[stage_name] = "FAILED"
                print(f"Stage failed: {stage_name}")
                print(f"Exception: {e}")
                raise

            # Step 4: Extract frames
            update(4, total_steps, "Extracting frames...")
            stage_name = "Frame Extraction"
            stage_start = time.time()
            try:
                frames_dir = frames.extract_frames(video_path, config.FRAMES_DIR, fps=config.FPS)
                timings[stage_name] = time.time() - stage_start
                statuses[stage_name] = "SUCCESS"
            except Exception as e:
                timings[stage_name] = time.time() - stage_start
                statuses[stage_name] = "FAILED"
                print(f"Stage failed: {stage_name}")
                print(f"Exception: {e}")
                raise

            # Step 5: OCR
            update(5, total_steps, "Running OCR...")
            stage_name = "OCR"
            stage_start = time.time()
            try:
                ocr_texts = ocr.run_ocr(frames_dir)
                timings[stage_name] = time.time() - stage_start
                statuses[stage_name] = "SUCCESS"
            except Exception as e:
                timings[stage_name] = time.time() - stage_start
                statuses[stage_name] = "FAILED"
                print(f"Stage failed: {stage_name}")
                print(f"Exception: {e}")
                raise

            # Step 6: Regex resources
            update(6, total_steps, "Extracting resources...")
            combined_for_regex = transcript_text + "\n" + "\n".join(ocr_texts)
            resources = regex.extract_resources(combined_for_regex)

            caption_text = ""
            # Merge
            merged_text = merge.merge_data(transcript_text, ocr_texts, caption_text, resources)

            # Step 7: Summarize
            update(7, total_steps, "Generating summary with LLM...")
            stage_name = "LLM"
            stage_start = time.time()
            try:
                summary_data = summarize.summarize(merged_text)
                timings[stage_name] = time.time() - stage_start
                statuses[stage_name] = "SUCCESS"
            except Exception as e:
                timings[stage_name] = time.time() - stage_start
                statuses[stage_name] = "FAILED"
                print(f"Stage failed: {stage_name}")
                print(f"Exception: {e}")
                raise

            # Assemble final result
            result = {
                "reel_url": reel_url,
                "transcript_text": transcript_text,
                "transcript_segments": transcript_result.get("segments", []),
                "ocr_text": ocr_texts,
                "caption": caption_text,
                "resources": resources,
                "summary": summary_data,
            }

            # Save
            import uuid
            reel_id = str(uuid.uuid4())[:8]
            stage_name_json = "JSON Save"
            stage_start_json = time.time()
            try:
                json_path = save_json.save_json(result, reel_id)
                timings[stage_name_json] = time.time() - stage_start_json
                statuses[stage_name_json] = "SUCCESS"
            except Exception as e:
                timings[stage_name_json] = time.time() - stage_start_json
                statuses[stage_name_json] = "FAILED"
                print(f"Stage failed: {stage_name_json}")
                print(f"Exception: {e}")
                raise
            stage_name_md = "Markdown Save"
            stage_start_md = time.time()
            try:
                md_path = save_md.save_md(result, reel_id)
                timings[stage_name_md] = time.time() - stage_start_md
                statuses[stage_name_md] = "SUCCESS"
            except Exception as e:
                timings[stage_name_md] = time.time() - stage_start_md
                statuses[stage_name_md] = "FAILED"
                print(f"Stage failed: {stage_name_md}")
                print(f"Exception: {e}")
                raise

            progress.progress(1.0)
            status.success("Analysis complete!")

            # Display results
            st.subheader("Results")
            st.write(f"**Reel ID:** `{reel_id}`")
            st.write(f"**Output JSON:** `{json_path}`")
            st.write(f"**Output Markdown:** `{md_path}`")

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Transcript")
                st.text_area("Text", transcript_text, height=200)
                with st.expander("Segments with Timestamps"):
                    for seg in transcript_result.get("segments", []):
                        st.write(f"{seg['start']:.2f}s - {seg['end']:.2f}s: {seg['text']}")
            with col2:
                st.subheader("Summary")
                if isinstance(summary_data, dict):
                    st.json(summary_data)
                else:
                    st.write(str(summary_data))

            st.subheader("Resources Detected")
            st.json(resources)

            st.subheader("Download")
            with open(json_path, "r", encoding="utf-8") as f:
                st.download_button("Download JSON", f.read(), file_name=f"reel_{reel_id}.json")
            with open(md_path, "r", encoding="utf-8") as f:
                st.download_button("Download Markdown", f.read(), file_name=f"reel_{reel_id}.md")

        except Exception as e:
            status.error(f"Error: {e}")
            import traceback
            st.code(traceback.format_exc())
        finally:
            total_elapsed = time.time() - pipeline_start if 'pipeline_start' in locals() else 0.0
            print("=" * 50)
            print("PIPELINE TIMINGS")
            print("=" * 50)
            stage_order = [
                ("Download", "Download"),
                ("Audio Extraction", "Audio Extraction"),
                ("Whisper", "Whisper"),
                ("Frame Extraction", "Frame Extraction"),
                ("OCR", "OCR"),
                ("LLM", "LLM"),
                ("JSON Save", "JSON Save"),
                ("Markdown Save", "Markdown Save"),
            ]
            for label, key in stage_order:
                elapsed = timings.get(key, 0.0)
                print(f"{label:<20} : {elapsed:.2f} s")
            print("-" * 42)
            print(f"{'TOTAL':<20} : {total_elapsed:.2f} s")
            print("=" * 50)
            print()
            print(f"Download: {statuses.get('Download', 'FAILED')} ({timings.get('Download', 0.0):.2f} s)")
            print(f"Whisper: {statuses.get('Whisper', 'FAILED')} ({timings.get('Whisper', 0.0):.2f} s)")
            print(f"Frames: {statuses.get('Frame Extraction', 'FAILED')} ({timings.get('Frame Extraction', 0.0):.2f} s)")
            print(f"OCR: {statuses.get('OCR', 'FAILED')} ({timings.get('OCR', 0.0):.2f} s)")
            print(f"LLM: {statuses.get('LLM', 'FAILED')} ({timings.get('LLM', 0.0):.2f} s)")
            try:
                if 'browser' in locals() and browser is not None:
                    browser.close()
            except Exception:
                pass
            # Clean up temporary files after successful analysis
            try:
                import shutil
                temp_dir = Path(config.TEMP_DIR)
                if temp_dir.exists():
                    for item in temp_dir.iterdir():
                        if item.is_file() and item.name != ".instagram_session":
                            item.unlink(missing_ok=True)
                        elif item.is_dir() and item.name != ".instagram_session":
                            shutil.rmtree(item, ignore_errors=True)
                # Clean frames directory
                frames_dir = Path(config.FRAMES_DIR)
                if frames_dir.exists():
                    shutil.rmtree(frames_dir, ignore_errors=True)
            except Exception:
                pass


if __name__ == "__main__":
    main()
