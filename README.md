# 🚀 AI-Powered Instagram Reel Analyzer

Extract structured knowledge from Instagram Reels using a fully local AI pipeline.

Instead of simply downloading reels, this project converts them into searchable knowledge by combining speech transcription, OCR, resource extraction, and local LLM summarization.

---

## ✨ Features

- 📥 Automatic Instagram Reel acquisition using **yt-dlp**
- 🎙 Speech transcription with **Faster-Whisper**
- 🖼 Frame extraction using **FFmpeg**
- 🔍 On-screen text extraction using **EasyOCR**
- 🔗 Automatic extraction of:
  - URLs
  - GitHub repositories
  - Emails
  - Instagram handles
  - X (Twitter) handles
  - YouTube links
  - Discord links
  - Phone numbers
  - Hashtags
- 🧠 Local AI summarization using **Ollama + Qwen2.5:7B**
- 📄 Export structured JSON reports
- 📝 Export Markdown notes
- 💻 Streamlit web interface
- 🔒 Privacy-first (runs locally)

---

# 🏗 Architecture

```
                 Instagram Reel URL
                         │
                         ▼
                  yt-dlp Acquisition
                         │
                         ▼
                    reel.mp4 (local)
                         │
          ┌──────────────┴──────────────┐
          │                             │
          ▼                             ▼
 FFmpeg Audio Extraction        Frame Extraction
          │                             │
          ▼                             ▼
 Faster-Whisper                 EasyOCR
          │                             │
          └──────────────┬──────────────┘
                         ▼
              Transcript + OCR Merge
                         │
                         ▼
             Resource Extraction (Regex)
                         │
                         ▼
          Ollama (Qwen2.5:7B Local LLM)
                         │
                         ▼
          Structured Knowledge Extraction
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
        JSON Report            Markdown Notes
```

---

# 📸 Screenshots

## Main Interface

> *(Add screenshot later)*

```
docs/main-ui.png
```

## Example Analysis

> *(Add screenshot later)*

```
docs/example-output.png
```

---

# 🛠 Tech Stack

| Category | Technology |
|----------|------------|
| UI | Streamlit |
| Acquisition | yt-dlp |
| Audio | FFmpeg |
| Speech-to-Text | Faster-Whisper |
| OCR | EasyOCR |
| Local LLM | Ollama |
| Model | Qwen2.5:7B |
| Language | Python 3.12 |

---

# 📂 Project Structure

```
reel-analyzer/
│
├── app.py
├── acquire.py
├── config.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
│
├── audio/
│   └── extract_audio.py
│
├── browser/
│
├── downloader/
│   └── video.py
│
├── parser/
│   ├── regex.py
│   └── merge.py
│
├── storage/
│   ├── save_json.py
│   └── save_md.py
│
├── summarizer/
│   ├── ollama_client.py
│   └── summarize.py
│
├── vision/
│   ├── frames.py
│   └── ocr.py
│
├── whisper/
│   └── transcribe.py
│
├── output/
│
└── temp/
```

---

# ⚙ Installation

## 1. Clone the repository

```bash
git clone https://github.com/<your-username>/reel-analyzer.git

cd reel-analyzer
```

---

## 2. Create a virtual environment

Windows

```bash
python -m venv .venv

.venv\Scripts\activate
```

Linux / macOS

```bash
python3 -m venv .venv

source .venv/bin/activate
```

---

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Install FFmpeg

Ensure FFmpeg is available in your system PATH.

Verify:

```bash
ffmpeg -version
```

---

## 5. Install Ollama

Download:

https://ollama.com/download

Pull the local model:

```bash
ollama pull qwen2.5:7b
```

Verify:

```bash
ollama list
```

---

## 6. Start Ollama

```bash
ollama serve
```

If Ollama is already running, this command is not required.

---

## 7. Configure Environment Variables

Create a `.env` file from `.env.example`.

Example:

```env
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_HOST=http://localhost:11434
```

---

# 🚀 Usage

Launch the application:

```bash
streamlit run app.py
```

Open the local Streamlit URL in your browser.

Paste an Instagram Reel URL and click **Analyze**.

The application will automatically:

1. Download the reel
2. Extract audio
3. Transcribe speech
4. Extract video frames
5. Perform OCR
6. Detect useful resources
7. Generate a structured AI summary
8. Save JSON and Markdown reports

---

# 📤 Output

Each analysis generates:

```
output/

├── reel_xxxxxxxx.json

└── reel_xxxxxxxx.md
```

The JSON report includes:

- Transcript
- OCR text
- Caption
- URLs
- GitHub repositories
- Emails
- Social handles
- Phone numbers
- AI-generated summary
- Action items
- Key concepts

---

# 🔒 Privacy

This project is designed to run locally.

Your data stays on your machine.

No transcripts, screenshots, or summaries are uploaded to external services when using the local Ollama mode.

Cloud LLM support is optional.

---

# 📈 Roadmap

## Phase 1 ✅

- Reel acquisition
- Whisper transcription
- OCR
- Local LLM
- JSON export
- Markdown export

## Phase 2 🚧

- Better prompting
- Richer summaries
- Improved OCR merging
- Timestamp linking
- Better UI

## Phase 3

- Vision-language models
- Diagram understanding
- Code detection
- Slide summarization

## Phase 4

Personal searchable knowledge base.

Examples:

- "Show every reel mentioning LangGraph."
- "Find all startup fundraising reels."
- "Everything I've learned about RAG."

---

# 🤝 Contributing

Contributions, feature requests, and bug reports are welcome.

Feel free to open an issue or submit a pull request.

---

# 📄 License

MIT License

---

# ⭐ If you found this project useful...

Please consider giving it a star.