import os
import json
import socket
import urllib.request
import urllib.error
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# Force IPv4 to avoid Docker Desktop WSL2 IPv6 socket hangs
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_getaddrinfo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "practice_history.md")
ENV_FILE = os.path.join(BASE_DIR, "ielts-coach", ".env")
PORT = int(os.getenv("PORT", "8501"))


def load_default_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if key:
        return key
    for env_path in [os.path.join(BASE_DIR, ".env"), ENV_FILE]:
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


MASTER_SYSTEM_PROMPT = """You are an expert IELTS General Training Writing Examiner helping a student move from Band 6.5 to Band 7.5+ (CLB 9–10).

STUDENT PATTERNS TO WATCH:
- Missing/extra articles (a/an/the), subject-verb agreement, passive participles (e.g., "are burdened"), comma splices, unnatural collocations, and writing a "Discuss Both Views" intro on an "Opinion (Agree/Disagree)" prompt.

TASK 2 STRUCTURAL STANDARDS (250+ WORDS TOTAL, 40 MINUTES):
1. Introduction (2–3 sentences, ~40–55 words): Paraphrase prompt + clear thesis answering every part and previewing ONLY 2 main ideas.
2. Body Paragraph 1 — PEEL (5–6 sentences, ~90–105 words): Point, Explain, Example, Link.
3. Body Paragraph 2 — PEEL (5–6 sentences, ~90–105 words): Second distinct idea using PEEL (1:1 solutions for Problem–Solution; both sides fairly for Discuss Both Views; Q1 in Body 1 & Q2 in Body 2 for Double Question).
4. Conclusion (2 sentences, ~35–45 words): Restate thesis + summarize both main points (no new arguments).

STRICT OUTPUT RULES FOR REVIEWS (MODES A, B, C):
- Keep it VERY SHORT, direct, and plain text.
- DO NOT use Markdown symbols like ###, **, *, `, or ---.
- DO NOT write long paragraphs or full model essays.
- Use this exact simple layout:

For MODE A (Single Section Review) and MODE C (Rewrite Comparison):
Estimated Band: <score, e.g. 6.0>

Main Issues:
- <short 1-line issue, e.g. Grammar error: "X" -> "Y".>
- <short 1-line issue, e.g. Length/structure/PEEL/article issue.>
(Max 3–4 short bullets. For Mode C, start with one bullet confirming what was fixed.)

Suggested Corrections:
1. "<exact corrected sentence or phrase>" — (<short 3–6 word reason>)
2. "<exact corrected sentence or phrase>" — (<short 3–6 word reason>)
(List only the key fixes, max 4 items.)

For MODE B (Full Essay Review):
Estimated Band: <overall> (TR: <score> | CC: <score> | LR: <score> | GRA: <score>)

Main Issues:
- <short 1-line issue>
- <weakest paragraph + 1-line reason>
(Max 4–5 short bullets.)

Suggested Corrections:
1. "<exact corrected sentence or phrase>" — (<short 3–6 word reason>)
2. "<exact corrected sentence or phrase>" — (<short 3–6 word reason>)
(Max 5 items.)

For MODE D (New Topic Generation):
Follow the exact PROMPT / PLANNING HINT format requested in the user message.
"""


def init_history_file():
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            f.write("# IELTS General Task 2 — Practice & Error Log\n\n")
            f.write("**Target:** Band 6.5 → **Band 7.5+ (CLB 9–10)**\n")
            f.write("**Format:** Auto-logged practice sessions, section drills, rewrites, and line-by-line examiner feedback.\n\n---\n\n")


def append_to_history(essay_type: str, topic: str, mode_label: str, attempt_label: str, draft: str, feedback: str):
    init_history_file()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    word_count = len(draft.split())
    entry = (
        f"## [{timestamp}] {essay_type} — {mode_label} ({attempt_label})\n\n"
        f"**Topic:** {topic}\n\n"
        f"**Word Count:** {word_count} words\n\n"
        f"### Your Draft\n```text\n{draft.strip()}\n```\n\n"
        f"### Gemini Review & Changes\n{feedback.strip()}\n\n"
        f"---\n\n"
    )
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(entry)


def read_history() -> str:
    init_history_file()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return f.read()


def call_gemini(api_key: str, model_name: str, user_prompt: str) -> str:
    api_key = (api_key or load_default_api_key()).strip()
    if not api_key:
        raise ValueError("Missing Gemini API Key. Please enter your API key in the top bar.")

    # Map any deprecated 2.x model names from cached browser tabs
    if not model_name or model_name.startswith("gemini-2."):
        model_name = "gemini-3.5-flash-lite"

    # Candidate models in priority order (selected model first, reliable fallback second)
    candidates = [model_name, "gemini-3.5-flash-lite", "gemini-3.8-flash"]
    seen = []
    for m in candidates:
        if m and m not in seen:
            seen.append(m)

    payload = {
        "systemInstruction": {
            "parts": [{"text": MASTER_SYSTEM_PROMPT}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.4
        }
    }
    data_bytes = json.dumps(payload).encode("utf-8")

    last_error = ""
    for m in seen:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=35) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                candidates_list = resp_data.get("candidates", [])
                if candidates_list:
                    parts = candidates_list[0].get("content", {}).get("parts", [])
                    text = "".join(p.get("text", "") for p in parts)
                    if text:
                        return text
                return "No response text returned from Gemini."
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            last_error = f"HTTP {e.code} ({m}): {err_body}"
            continue
        except Exception as e:
            last_error = str(e)
            continue

    raise RuntimeError(f"Gemini API call failed. Details: {last_error}")


class CoachHandler(BaseHTTPRequestHandler):
    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index.html") or self.path.startswith("/coach"):
            index_path = os.path.join(BASE_DIR, "index.html")
            with open(index_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == "/api/config":
            key = load_default_api_key()
            self._send_json({
                "hasDefaultKey": bool(key),
                "maskedKey": (key[:6] + "..." + key[-4:]) if len(key) > 10 else "",
                "historyPath": HISTORY_FILE,
            })
        elif self.path == "/api/history":
            self._send_json({
                "history": read_history(),
                "historyPath": HISTORY_FILE,
            })
        elif self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            body = json.loads(raw)
        except Exception:
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        try:
            if self.path == "/api/generate-topic":
                api_key = body.get("apiKey", "")
                model_name = body.get("model", "gemini-3.8-flash")
                essay_type = body.get("essayType", "Opinion (Agree / Disagree)")
                prompt = (
                    f"MODE D — NEW TOPIC GENERATION\n"
                    f"Generate ONE fresh, realistic IELTS General Training Task 2 prompt for the essay type: "
                    f"'{essay_type}'.\n"
                    f"Return strictly in this format:\n"
                    f"PROMPT: <the exact 2-sentence exam prompt>\n"
                    f"PLANNING HINT:\n"
                    f"- Thesis frame: ...\n"
                    f"- Body 1 idea: ...\n"
                    f"- Body 2 idea: ..."
                )
                result = call_gemini(api_key, model_name, prompt)
                topic = result.strip()
                hint = ""
                if "PLANNING HINT:" in result:
                    parts = result.split("PLANNING HINT:", 1)
                    topic = parts[0].replace("PROMPT:", "").strip()
                    hint = parts[1].strip()
                self._send_json({"topic": topic, "planningHint": hint})

            elif self.path == "/api/review":
                api_key = body.get("apiKey", "")
                model_name = body.get("model", "gemini-3.8-flash")
                essay_type = body.get("essayType", "Opinion (Agree / Disagree)")
                topic = body.get("topic", "")
                mode = body.get("mode", "section")  # "section" or "full"
                section_name = body.get("sectionName", "Introduction")
                section_guide = body.get("sectionGuide", "")
                draft = body.get("draft", "").strip()
                attempt_num = int(body.get("attemptNum", 0))
                prev_feedback = body.get("prevFeedback", "")
                prior_context = body.get("priorContext", "")

                if not draft:
                    self._send_json({"error": "Please write your draft before requesting a review."}, 400)
                    return

                wc = len(draft.split())
                is_rewrite = attempt_num > 0

                if mode == "section":
                    user_prompt = (
                        f"MODE: {'MODE C — REWRITE COMPARISON & ' if is_rewrite else ''}MODE A — SECTION-BY-SECTION REVIEW\n"
                        f"ESSAY TYPE: {essay_type}\n"
                        f"TOPIC PROMPT: {topic}\n"
                        f"TARGET SECTION: {section_name} ({section_guide})\n\n"
                        f"OTHER SECTIONS ALREADY WRITTEN BY STUDENT:\n{prior_context or '(None yet)'}\n\n"
                        f"CURRENT DRAFT OF {section_name.upper()} ({wc} words):\n{draft}\n\n"
                    )
                    if is_rewrite and prev_feedback:
                        user_prompt += (
                            f"PREVIOUS FEEDBACK GIVEN:\n{prev_feedback}\n\n"
                            f"Compare the rewrite against the previous feedback, confirm which errors were fixed, "
                            f"list any remaining changes needed in Original -> Band 7.5+ Fix format, and give the updated section band score."
                        )
                    feedback = call_gemini(api_key, model_name, user_prompt)
                    label = "Initial Draft" if attempt_num == 0 else f"Rewrite #{attempt_num}"
                    append_to_history(essay_type, topic, section_name, label, draft, feedback)
                else:
                    user_prompt = (
                        f"MODE: {'MODE C — REWRITE COMPARISON & ' if is_rewrite else ''}MODE B — FULL ESSAY REVIEW\n"
                        f"ESSAY TYPE: {essay_type}\n"
                        f"TOPIC PROMPT: {topic}\n"
                        f"WORD COUNT: {wc} words\n\n"
                        f"STUDENT ESSAY:\n{draft}\n"
                    )
                    if is_rewrite and prev_feedback:
                        user_prompt += (
                            f"\nPREVIOUS FEEDBACK:\n{prev_feedback}\n"
                            f"Highlight improvements made, list any remaining errors in Original -> Band 7.5+ Fix format, and give updated criteria scores."
                        )
                    feedback = call_gemini(api_key, model_name, user_prompt)
                    label = "Initial Full Draft" if attempt_num == 0 else f"Full Rewrite #{attempt_num}"
                    append_to_history(essay_type, topic, "Full Essay", label, draft, feedback)

                self._send_json({
                    "feedback": feedback,
                    "history": read_history(),
                    "historyPath": HISTORY_FILE,
                })
            else:
                self._send_json({"error": "Unknown endpoint"}, 404)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)


if __name__ == "__main__":
    init_history_file()
    print(f"IELTS Task 2 Coach running at http://localhost:{PORT}")
    print(f"Recording Markdown file: {HISTORY_FILE}")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), CoachHandler)
    server.serve_forever()
