# Pranay AI

A lightweight, customizable AI assistant with retrieval (RAG), built to run either:
- **Cloud**: OpenAI-compatible API (default), or
- **Local**: Ollama (no data leaves your machine).

## Features
- Chat with a **Pranay** persona tailored to study and productivity.
- Optional retrieval over your own notes and AP Biology resources.
- Simple web UI included (`web/index.html`).

## Quick start

### 1) Install dependencies
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
