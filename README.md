# Band7.5+ Studio — IELTS General Task 2 Writing Coach

A lightweight, personal-use web app for practicing **IELTS General Training Writing Task 2** (targeting **Band 6.5 → 7.5+ / CLB 9–10**) powered by the Gemini API. Every draft, rewrite comparison, and examiner review is automatically logged to `practice_history.md`.

## Features

- **4-Section PEEL Drill:** Practice and review each section individually (*Introduction*, *Body Paragraph 1 (PEEL)*, *Body Paragraph 2 (PEEL)*, *Conclusion*) with live word counts and a combined 4-paragraph preview.
- **Full Essay Simulation (40 Min):** Built-in 40-minute countdown timer, word counter, and full 4-criteria IELTS band breakdown (`TR`, `CC`, `LR`, `GRA`).
- **6 Supported Task 2 Essay Types:**
  - Opinion (Agree / Disagree)
  - Discuss Both Views + Opinion
  - Problem–Solution
  - Causes & Effects
  - Advantages vs. Disadvantages
  - Double Question
- **Topic & Planning Generator:** Generates exam-style Task 2 prompts with a 3-bullet planning hint (thesis frame + Body 1 & Body 2 ideas).
- **Concise Examiner Feedback & Rewrite Tracking:** Returns short, plain-text `Estimated Band`, `Main Issues`, and `Suggested Corrections`, and compares rewrites against previous feedback.
- **Automatic Markdown Logging (`practice_history.md`):** Every submission and review is appended to `practice_history.md` on your machine and viewable/downloadable in the **History Log** tab.

## Quick Start (Docker Compose — Recommended)

1. Copy the example environment file and add your Gemini API key:
   ```bash
   cp .env.example .env
   ```
   Edit `.env`:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   PORT=8501
   ```

2. Build and start the container:
   ```bash
   docker compose up -d --build
   ```

3. Open **`http://localhost:8501`** in your browser.

`docker-compose.yml` mounts `./practice_history.md`, `./index.html`, and `./server.py` directly into the container, and configures IPv4 + DNS (`8.8.8.8`, `1.1.1.1`) for reliable API calls.

## Run Locally Without Docker (Python 3.12+)

No third-party `pip` packages are required—`server.py` uses Python's standard library.

```bash
python server.py
```

Then open **`http://localhost:8501`**.

## Project Structure

- `server.py` — Zero-dependency HTTP server (`ThreadingHTTPServer`), Gemini API client (`gemini-3.5-flash-lite` / `gemini-3.8-flash`), and `practice_history.md` logger.
- `index.html` — Single-page personal writing workspace and live Markdown history viewer.
- `practice_history.md` — Auto-generated Markdown log of all practice drafts, rewrites, and examiner reviews.
- `Dockerfile` & `docker-compose.yml` — Container setup for port `8501`.
- `.env.example` — Environment template (`.env` is gitignored).
