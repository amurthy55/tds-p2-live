---
title: Tds P2
emoji: ⚡
colorFrom: green
colorTo: purple
sdk: docker
pinned: false
---
Quiz Automation Project

A fully automated pipeline to scrape, extract, analyse, solve, and submit quiz answers using FastAPI, Playwright, Whisper, and LLMs (OpenAI / AI Pipe).
This project is designed to run locally or on Hugging Face Spaces (Docker runtime).

🚀 Features
Phase 1 — Extraction

Scrapes quiz webpages using Playwright & BeautifulSoup

Extracts:

Questions

Options

Images

Audio → converted to text via Whisper

PDFs via PyPDF2

Automatic asset downloading via utility modules

Supports dynamic JS-rendered pages

Outputs structured JSON

Phase 2 — Solving

Sends extracted question data to an LLM (OpenAI or AI Pipe)

Generates structured reasoning and answers

Builds an automated quiz-submission script

Executes and submits answers for supported platforms

📂 Project Structure
app
 ┣ utils
 ┃ ┣ file_tools.py
 ┃ ┗ url_tools.py
 ┣ browser.py
 ┣ config.py
 ┣ main.py
 ┣ phase1_extractor.py
 ┣ phase2_dispatcher.py
 ┣ phase2_executor.py
 ┣ phase2_llm.py
 ┣ phase2_models.py
 ┣ phase2_script_builder.py
 ┣ phase2_submitter.py
 ┣ scrapers.py
 ┣ solver.py
 ┣ test.json
 ┗ __init__.py
requirements.txt
README.md
Dockerfile


This folder layout remains the same when deployed to Hugging Face Spaces.

⚙️ Environment Variables

Create a .env file in the project root:

OPENAI_API_KEY=sk-proj-xxxx
AIPIPE_API_KEY=eyxxxxxx
STUDENT_SECRET=0ct0b3r


These are used by config.py to load API keys securely.

▶️ Running Locally
Install dependencies
pip install -r requirements.txt

Start FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000

Visit API docs
http://localhost:8000/docs

☁️ Deploying on Hugging Face Spaces (Docker)

This repository includes a Dockerfile compatible with Hugging Face.
HF automatically builds the container and runs your FastAPI app on port 7860.

The app will be available at:
https://<your-space>.hf.space

🔧 Included Technologies
Component	Purpose
FastAPI	HTTP API framework
Playwright	Browser automation & JS rendering
Whisper (openai-whisper)	Audio transcription
Torch	Whisper backend
BeautifulSoup4	HTML parsing
PyPDF2	PDF extraction
OpenAI / AI Pipe	LLM solving
Pandas / Numpy	Data processing
Python-Multipart	File uploads
Python-dotenv	Environment variable loading
🎤 Audio → Text

Audio files from quizzes are automatically:

Downloaded

Loaded using soundfile / librosa

Transcribed with Whisper

Passed into LLM reasoning

🧪 Testing

Tests can be added and executed using:

pytest

📜 License

This project uses the MIT License.
The recommended filename is:

LICENSE

🤝 Contributions

Pull requests welcome — especially around:

More quiz platform support

Additional extraction models

Phase 2 auto-submission scripts

📬 Contact / Support

For issues or improvements, open a GitHub Issue in the repository.
If running on HF Spaces, logs are visible in the Space console.

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference
