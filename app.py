#!/usr/bin/env python3
"""Streamlit application for Instagram Reel Analyzer."""

import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from acquire import acquire_reel

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

        llm_mode = st.selectbox(
            "LLM Mode",
            ["local", "cloud"],
            index=0
        )

        config.LLM_MODE = llm_mode

        if llm_mode == "local":
            config.OLLAMA_MODEL = st.text_input(
                "Ollama Model",
                value=config.OLLAMA_MODEL
            )
        else:
            config.CLOUD_API_KEY = st.text_input(
                "Cloud API Key",
                value=config.CLOUD_API_KEY,
                type="password"
            )

            config.CLOUD_MODEL = st.text_input(
                "Cloud Model",
                value=config.CLOUD_MODEL
            )

        model_size = st.selectbox(
            "Whisper Model",
            ["tiny", "base", "small", "medium"],
            index=2
        )

        config.WHISPER_MODEL_SIZE = model_size

        st.info("Using local processing where possible.")

    reel_url = st.text_input(
        "Instagram Reel URL",
        placeholder="https://www.instagram.com/reel/..."
    )


    if st.button("Analyze"):

        if not reel_url:
            st.error("Please enter a Reel URL.")
            return


        progress = st.progress(0)
        status = st.empty()


        def update(step, total, msg):
            progress.progress(step / total)
            status.write(msg)


        total_steps = 8


        try:

            # -----------------------------
            # Step 1: Acquire Reel
            # -----------------------------
            update(
                1,
                total_steps,
                "Downloading Reel using yt-dlp..."
            )

            video_path = acquire_reel(reel_url)


            if not video_path.exists():
                raise FileNotFoundError(
                    "Downloaded reel.mp4 was not created."
                )


            # -----------------------------
            # Step 2: Audio extraction
            # -----------------------------
            update(
                2,
                total_steps,
                "Extracting audio..."
            )

            audio_path = extract_audio.extract_audio(
                video_path,
                config.AUDIO_FILE
            )


            # -----------------------------
            # Step 3: Whisper
            # -----------------------------
            update(
                3,
                total_steps,
                "Transcribing audio..."
            )

            transcript_result = transcribe.transcribe(
                str(audio_path),
                model_size=config.WHISPER_MODEL_SIZE
            )

            transcript_text = transcript_result.get(
                "text",
                ""
            )


            # -----------------------------
            # Step 4: Frames
            # -----------------------------
            update(
                4,
                total_steps,
                "Extracting frames..."
            )

            frames_dir = frames.extract_frames(
                video_path,
                config.FRAMES_DIR,
                fps=config.FPS
            )


            # -----------------------------
            # Step 5: OCR
            # -----------------------------
            update(
                5,
                total_steps,
                "Running OCR..."
            )

            ocr_texts = ocr.run_ocr(frames_dir)


            # -----------------------------
            # Step 6: Resource extraction
            # -----------------------------
            update(
                6,
                total_steps,
                "Extracting resources..."
            )

            combined_text = (
                transcript_text
                + "\n"
                + "\n".join(ocr_texts)
            )

            resources = regex.extract_resources(
                combined_text
            )


            # No browser now, so caption extraction removed
            caption_text = ""


            merged_text = merge.merge_data(
                transcript_text,
                ocr_texts,
                caption_text,
                resources
            )


            # -----------------------------
            # Step 7: Summary
            # -----------------------------
            update(
                7,
                total_steps,
                "Generating summary..."
            )

            summary_data = summarize.summarize(
                merged_text
            )


            # -----------------------------
            # Step 8: Save
            # -----------------------------
            update(
                8,
                total_steps,
                "Saving results..."
            )


            import uuid

            reel_id = str(uuid.uuid4())[:8]


            result = {
                "reel_url": reel_url,
                "transcript_text": transcript_text,
                "transcript_segments": transcript_result.get(
                    "segments",
                    []
                ),
                "ocr_text": ocr_texts,
                "caption": caption_text,
                "resources": resources,
                "summary": summary_data,
            }


            json_path = save_json.save_json(
                result,
                reel_id
            )

            md_path = save_md.save_md(
                result,
                reel_id
            )


            progress.progress(1.0)

            status.success(
                "Analysis complete!"
            )


            # Display results

            st.subheader("Results")

            st.write(
                f"**Reel ID:** `{reel_id}`"
            )

            st.write(
                f"**Output JSON:** `{json_path}`"
            )

            st.write(
                f"**Output Markdown:** `{md_path}`"
            )


            col1, col2 = st.columns(2)


            with col1:

                st.subheader("Transcript")

                st.text_area(
                    "Text",
                    transcript_text,
                    height=200
                )


                with st.expander(
                    "Segments with timestamps"
                ):

                    for seg in transcript_result.get(
                        "segments",
                        []
                    ):

                        st.write(
                            f"{seg['start']:.2f}s - "
                            f"{seg['end']:.2f}s: "
                            f"{seg['text']}"
                        )


            with col2:

                st.subheader("Summary")

                if isinstance(summary_data, dict):
                    st.json(summary_data)
                else:
                    st.write(str(summary_data))


            st.subheader(
                "Resources Detected"
            )

            st.json(resources)


            st.subheader(
                "Download"
            )


            with open(
                json_path,
                "r",
                encoding="utf-8"
            ) as f:

                st.download_button(
                    "Download JSON",
                    f.read(),
                    file_name=f"reel_{reel_id}.json"
                )


            with open(
                md_path,
                "r",
                encoding="utf-8"
            ) as f:

                st.download_button(
                    "Download Markdown",
                    f.read(),
                    file_name=f"reel_{reel_id}.md"
                )


        except Exception as e:

            status.error(
                f"Error: {e}"
            )

            import traceback

            st.code(
                traceback.format_exc()
            )


if __name__ == "__main__":
    main()