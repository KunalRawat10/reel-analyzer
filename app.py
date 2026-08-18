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
from parser import regex, merge, mentioned_resources
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
        llm_options = ["local", "cloud"]
        llm_index = llm_options.index(config.LLM_MODE) if config.LLM_MODE in llm_options else 0
        llm_mode = st.selectbox("LLM Mode", llm_options, index=llm_index)
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

            caption_text = acquire.get_description(reel_url)
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

            # Build mentioned resources from existing summary output (no new LLM call)
            mentioned_resources_list = mentioned_resources.extract_mentioned_resources(summary_data)
            resources["mentioned_resources"] = mentioned_resources_list

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
            # Direct links (existing regex categories)
            direct_categories = {
                k: v for k, v in resources.items()
                if k != "mentioned_resources" and v
            }
            if direct_categories:
                st.markdown("**Direct Links**")
                for cat, items in direct_categories.items():
                    st.write(f"- **{cat.replace('_', ' ').title()}**: {', '.join(str(i) for i in items)}")
            else:
                st.markdown("*No direct links detected.*")

            # Mentioned resources (from summarizer, no fabricated URLs)
            mentioned = resources.get("mentioned_resources", [])
            if mentioned:
                st.markdown("**Mentioned Resources**")
                for item in mentioned:
                    official = item.get("official_url") or "Not resolved"
                    source = item.get("source", "summary")
                    status_text = item.get("resolution_status", "unresolved")
                    name_display = item.get("name", "Unknown")
                    type_display = item.get("type", "unknown")
                    resolution_note = item.get("resolution_note")
                    note_line = f"  Note: `{resolution_note}`" if resolution_note else ""
                    st.markdown(
                        f"- **{name_display}** (type: {type_display})  \n"
                        f"  Official URL: `{official}`  \n"
                        f"  Source: `{source}`  \n"
                        f"  Resolution: `{status_text}`"
                        + (f"  \n{note_line}" if note_line else "")
                    )
            else:
                st.markdown("*No mentioned resources detected.*")

            # Raw JSON for debugging
            with st.expander("Raw JSON (debug)"):
                st.json(resources)

            # Persist completed analysis in session state for Q&A reuse
            st.session_state["reel_result"] = result
            st.session_state["reel_url"] = reel_url
            st.session_state["json_path"] = json_path
            st.session_state["md_path"] = md_path

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



    # Phase 4: Persistent Q&A over analyzed Reel (uses session_state; does NOT rerun pipeline)
    analysis_result = st.session_state.get("reel_result")
    if analysis_result is not None:
        st.subheader("Ask a question about this Reel")
        user_question = st.text_input(
            "Your question:",
            key="qa_input",
            placeholder="What tools were mentioned? Was Cursor discussed?",
        )
        # Persist question in session_state so it survives reruns
        # Note: key="qa_input" manages this automatically; do NOT assign manually

        if st.button("Ask", key="ask_btn"):
            if not user_question or not user_question.strip():
                st.info("Please enter a question.")
            else:
                with st.spinner("Thinking..."):
                    context_parts = []
                    context_parts.append("=== REEL ANALYSIS CONTEXT ===")
                    context_parts.append(f"Reel URL: {analysis_result.get('reel_url', '')}")
                    context_parts.append(f"\n--- TRANSCRIPT ---\n{analysis_result.get('transcript_text', '')}")
                    segments = analysis_result.get('transcript_segments', [])
                    if segments:
                        context_parts.append("\n--- TRANSCRIPT SEGMENTS ---")
                        for seg in segments:
                            context_parts.append(f"{seg.get('start', 0)} - {seg.get('end', 0)}: {seg.get('text', '')}")
                    ocr_text = analysis_result.get('ocr_text', [])
                    if ocr_text:
                        context_parts.append(f"\n--- OCR DETECTED TEXT ---\n" + "\n".join(str(t) for t in ocr_text))
                    resources_data = analysis_result.get('resources', {})
                    # Direct links (exclude mentioned_resources for separate section)
                    direct_resources = {k: v for k, v in resources_data.items() if k != "mentioned_resources" and v}
                    if direct_resources:
                        context_parts.append(f"\n--- RESOURCES (DIRECT LINKS) ---")
                        for cat, items in direct_resources.items():
                            context_parts.append(f"{cat}: {', '.join(str(i) for i in items)}")
                    mentioned_resources_list = resources_data.get("mentioned_resources", []) if isinstance(resources_data, dict) else []
                    if mentioned_resources_list:
                        context_parts.append(f"\n--- MENTIONED_RESOURCES ---")
                        for item in mentioned_resources_list:
                            name = item.get("name", "Unknown") if isinstance(item, dict) else str(item)
                            official = item.get("official_url") or "Not resolved"
                            source = item.get("source", "summary")
                            status_text = item.get("resolution_status", "unresolved")
                            note = item.get("resolution_note", "")
                            note_str = f" Note: {note}" if note else ""
                            context_parts.append(f"- {name} (official: {official}, source: {source}, status: {status_text}){note_str}")
                    summary_data_result = analysis_result.get('summary', {})
                    if isinstance(summary_data_result, dict):
                        context_parts.append(f"\n--- SUMMARY ---")
                        for k, v in summary_data_result.items():
                            if v is not None and v != [] and v != {}:
                                context_parts.append(f"{k}: {v}")
                    context_text = "\n".join(context_parts)

                    qa_prompt = f"""You are answering a user's question about an Instagram Reel based ONLY on the provided analysis data below.
When answering:
- Prefer direct evidence from TRANSCRIPT, OCR, RESOURCES (direct links), and MENTIONED_RESOURCES over SUMMARY.
- For each claim, state which source(s) support it (TRANSCRIPT / OCR / RESOURCES / MENTIONED_RESOURCES / SUMMARY).
- If sources disagree, explicitly mention the disagreement.
- If a claim is supported only by SUMMARY and not by transcript/OCR/resources/mentioned_resources, explicitly say that it comes only from the summary.
If the requested information is NOT present in the transcript, OCR text, resources, or summary, reply exactly with:
"This information was not found in the analyzed Reel."
DO NOT invent URLs, names, facts, or conclusions not supported by the data.

=== REEL DATA ===
{context_text}

=== USER QUESTION ===
{user_question}

=== ANSWER (use only the Reel data above; say 'not found' if missing): ==="""

                    qa_answer = ""
                    if config.LLM_MODE == "local":
                        try:
                            from summarizer import ollama_client
                            if ollama_client.health_check() and ollama_client.verify_model():
                                qa_answer_text = ollama_client.call_ollama(qa_prompt, model=config.OLLAMA_MODEL)
                                qa_answer = qa_answer_text.strip()
                            else:
                                qa_answer = "Ollama server unavailable or model missing. Please start 'ollama serve' and ensure the model is installed."
                        except Exception as e_qa:
                            qa_answer = f"Local LLM error: {str(e_qa)}"
                    else:
                        try:
                            import requests
                            headers = {
                                "Content-Type": "application/json",
                                "Authorization": f"Bearer {config.CLOUD_API_KEY}",
                            }
                            payload = {
                                "model": config.CLOUD_MODEL,
                                "messages": [
                                    {"role": "system", "content": "Answer questions strictly based on the provided Reel analysis. If missing, say 'not found'. Never invent information."},
                                    {"role": "user", "content": qa_prompt},
                                ],
                                "temperature": 0.1,
                            }
                            response = requests.post(config.CLOUD_API_URL.rstrip("/") + "/chat/completions", headers=headers, json=payload, timeout=120)
                            response.raise_for_status()
                            content = response.json()["choices"][0]["message"]["content"]
                            qa_answer = content.strip()
                        except Exception as e_qa_cloud:
                            qa_answer = f"Cloud API error: {str(e_qa_cloud)}"

                    st.session_state["qa_answer"] = qa_answer

        # Always display the most recent answer if available (persists across reruns)
        if "qa_answer" in st.session_state:
            st.subheader("Answer")
            st.write(st.session_state["qa_answer"])
            if "not found" in st.session_state["qa_answer"].lower() or "This information was not found" in st.session_state["qa_answer"]:
                st.info("The requested information was not present in the Reel's transcript, OCR, summary, or resources.")

if __name__ == "__main__":
    main()
