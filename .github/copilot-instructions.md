# Copilot instructions for media_utils

Purpose
- Project: Media Subtitle Translator — Python CLI scripts + FastAPI web UI that translates English SRT -> polite Korean using pluggable LLM providers (Google Gemini, OpenRouter-compatible models, etc.).

Quick commands
- Setup virtualenv & deps:
  - python -m venv .venv
  - .\.venv\Scripts\Activate.ps1 (or .\.venv\Scripts\activate for cmd)
  - pip install -r requirements.txt

- Start web UI (dev):
  - python web_server.py
  - Alternative: uvicorn web_server:app --reload --host 127.0.0.1 --port 8000

- Run single scripts:
  - Preprocess a folder: python pre_srt.py C:\path\to\dir
  - Verify two files: python verify_srt.py C:\path\to\file_pre.srt C:\path\to\file\ (kr).srt
  - Postprocess a folder: python post_srt.py C:\path\to\dir
  - Merge/merge-target: python mergy_srt.py <file_or_directory>
  - Download (example): python download_yt.py (script contains example URLs)

Notes on tests/lint
- No test suite or linter configured in the repository. (No pytest/flake8/black configs found.)
- To run a single test would require adding a test runner; none exist currently.

High-level architecture (big picture)
- Core pipeline (CLI or Web UI):
  1. pre_srt.py — clean noise (filters.json) and merge adjacent SRT blocks using heuristic rules.
  2. web_server.py / translate endpoint — loads the preprocessed file, splits blocks into chunks of 100, calls the configured LLM provider per-chunk (e.g., Google Gemini via google-genai or OpenRouter-compatible models), verifies each chunk 1:1 (indices & timestamps), falls back to an alternate model on failure, then concatenates results.
  3. verify_srt.py — strict 1:1 comparator used both standalone and by web_server for final validation (exit code 0 on success, 1 on failure).
  4. post_srt.py — regex-based cleanup producing fixed_*.srt then used to overwrite translated result.
- Support tools: mergy_srt.py (merge/normalize blocks), download_yt.py (yt-dlp wrapper), compress_video.py and trim_video.py for media tasks.
- Web UI: static files served from static/; FastAPI exposes endpoints: /api/scan, /api/translate (SSE), /api/key_status, /api/default_directory.

Key repository conventions & patterns
- File naming conventions used by scripts and UI (important to preserve):
  - Preprocessed files: *_pre.srt
  - Final translated file: original name + " (kr).srt" (note the space before (kr))
  - Postprocessed temporary files: fixed_<original>.srt
  - Merged output: *_merged.srt
- Chunking policy: translation is done per 100 SRT blocks (chunk size = 100) to limit request size and enable partial retries.
- Strict 1:1 verification: verify_srt.parse_srt_content and verify_srt.verify_srt_files enforce exact match of index/start/end for every block; web_server uses this after every chunk and at final assembly.
- Noise filters: pre_srt.load_remove_targets() reads filters.json (remove_targets key). Keep that file near scripts; pre_srt expects it in the same directory as the script.
- pre_srt scan behavior: pre_srt.process_file and main() only process files in the specified directory (no recursion — os.listdir used intentionally).
- post_srt behavior: post_srt.process_srt writes fixed_*.srt for every .srt in target dir and expects the web flow to rename/clean up those files.
- API key / secrets: Support for multiple providers is available. Environment variables used by the project should include one or more of:
  - GEMINI_API_KEY (for google-genai)
  - OPENROUTER_API_KEY (for OpenRouter-compatible providers)
  - OPENROUTER_BASE_URL (optional; set when using a self-hosted OpenRouter endpoint)
  Do NOT commit keys; keep them in .env or CI secrets.

- Model provider usage specifics (web_server.py):
  - google-genai: Uses google.genai.Client with model names passed from the UI when GEMINI_API_KEY is present.
  - OpenRouter-compatible providers: If OPENROUTER_API_KEY is present and the UI/provider selection is set to `openrouter`, web_server should use an OpenRouter HTTP client (requests) or an existing OpenRouter client to POST generation requests with the chosen model name. OpenRouter commonly provides a `/models` endpoint to list available models — implement a small helper to cache that list for the UI.
  - UI/provider behavior: Add a provider dropdown (e.g., `gemini`, `openrouter`) and a freeform model input field. Allow specifying both a primary and a fallback model per provider. The backend should accept provider + model names in the translate request and construct calls accordingly.
  - Client abstraction: Create a get_model_client(provider, api_key, base_url=None) helper in web_server.py that returns a thin wrapper with a consistent generate(model, prompt, temperature) interface; keep Gemini path using google.genai and implement OpenRouter via requests.
  - Temperature and streaming: Map temperature directly; prefer low temperature (0.2) for format stability. If using OpenRouter streaming, ensure streamed output is reassembled before parse and keep verification steps unchanged.
  - Error/retry semantics: Maintain current 429/503 retry logic and fallback-model flow across providers. When parsing provider error messages, detect 429/503 equivalents from OpenRouter responses.


Where to look first for relevant changes
- To change translation constraints: web_server.translate_chunk_with_gemini() and the system_instruction there.
- To adjust merging heuristics: pre_srt.merge_logic() and mergy_srt.process_srt()
- To change postprocessing rules: post_srt.process_srt() (regex patterns p1, p2).
- To alter remove targets: filters.json.

Other AI-assistant & config files
- No CLAUDE.md, AGENTS.md, .cursorrules, .windsurfrules or similar assistant config files detected. If you add assistant guidance there, mirror important rules (e.g., strict 1:1 requirement).

Editing and safety notes for Copilot sessions
- Preserve naming patterns (_pre.srt, (kr), fixed_) — UI and scripts rely on those exact suffixes/prefixes.
- Avoid changing verify_srt's strict checks unless updating the UI/workflow accordingly.
- When modifying web_server retry/backoff behavior, ensure error paths still trigger fallback model or halt cleanly; the UI expects SSE log events with "step" and "status" keys.

MCP servers
- This is a web/UI project (FastAPI + static). Would you like me to configure an MCP server for Playwright-based E2E testing or a headless browser runner for the web UI? (ask to add if desired)

Summary
- Added repository-specific Copilot instructions with run commands, architecture overview, and conventions to help future Copilot sessions. Reply if you want adjustments (more examples, more CLI flags, or adding linter/test recommendations).