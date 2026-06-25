# Swap LLM Provider: Azure OpenAI primary, Gemini fallback, remove Ollama

## Context
The app currently generates interview feedback with **Gemini (primary) → Ollama llama3.2 (local fallback)**. We are switching to **Azure OpenAI (primary) → Gemini (fallback)** and removing Ollama entirely (no more local model, no `ollama serve` dependency).

Decisions (confirmed with user):
- **Eval harness** (`backend/evals/run_eval.py`) migrates to Azure too.
- **Missing Azure key** → gracefully skip to Gemini fallback (mirrors current "blank GEMINI_API_KEY skips Gemini" behavior).
- **Azure config**: standard env var names + JSON mode (`response_format={"type":"json_object"}`).

Provider logic is localized — almost all real work is in `backend/services/feedback_service.py`. Everything else is config, docs, one UI string, and the eval script.

## Provider chain (new)
1. **Azure OpenAI** (primary) — skipped if `AZURE_OPENAI_API_KEY` blank. Retried `MAX_RETRIES` times; rate-limit (429) honors retry-after.
2. **Gemini** (fallback) — existing `_call_gemini` + retry/quota logic kept as-is, just demoted from primary to fallback.
3. Both exhausted → `FeedbackServiceError` (unchanged).

## Changes

### 1. `backend/services/feedback_service.py` (core)
- **Remove Ollama**: delete `import ollama` (line 22), `OLLAMA_MODEL` (line 38), `_call_ollama` (lines 210-221), and the entire Ollama fallback block + "blank GEMINI key → use Ollama directly" branch in `get_feedback` (lines 310-348).
- **Add Azure**: `from openai import AzureOpenAI`. New config from env:
  - `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`.
- **New `_call_azure(prompt)`**: build `AzureOpenAI(api_key=..., azure_endpoint=..., api_version=...)`, call `client.chat.completions.create(model=AZURE_OPENAI_DEPLOYMENT, messages=[{"role":"user","content":prompt}], response_format={"type":"json_object"})`, take `response.choices[0].message.content`, feed through existing `_parse_json` (keep as JSON-fence safety net).
- **Azure rate-limit helper**: `_azure_retry_delay(exc)` analogous to existing `_gemini_retry_delay` — `openai.RateLimitError` exposes 429; parse `retry-after` if present else `RETRY_DELAY`.
- **Rewrite `get_feedback` chain**:
  - PRIMARY = Azure (guard `if AZURE_OPENAI_API_KEY:`), retry loop mirroring current Gemini loop; `on_status("azure", attempt, ...)`.
  - On Azure exhaustion / blank key → emit `"fallback"` and fall through to Gemini.
  - FALLBACK = Gemini loop (reuse existing `_call_gemini`, `_gemini_retry_delay`, `_is_quota_exhausted`), `on_status("gemini", ...)`.
  - Keep `on_status(provider, attempt, status, message)` signature and status strings (`in_progress`/`done`/`retrying`/`fallback`/`quota_exhausted`) so SSE + frontend keep working untouched. `analyze.py` callback (`routers/analyze.py:115-124`) needs no change.
- Update module docstring (lines 1-15) to describe Azure→Gemini.

### 2. `backend/requirements.txt`
- Remove `ollama` (line 5).
- Add `openai` (>=1.0, provides `AzureOpenAI`). Keep `google-genai`.

### 3. `backend/.env.example` + note for `backend/.env`
- Remove any Ollama mention; keep `MAX_RETRIES`, `RETRY_DELAY`.
- Add Azure block:
  ```
  AZURE_OPENAI_API_KEY=
  AZURE_OPENAI_ENDPOINT=
  AZURE_OPENAI_DEPLOYMENT=
  AZURE_OPENAI_API_VERSION=2024-10-21
  ```
- Keep `GEMINI_API_KEY` (now fallback).
- `backend/.env` is gitignored/local — user adds real Azure values themselves; plan only edits `.env.example`.

### 4. `backend/evals/run_eval.py`
- Swap Gemini client (lines 11, 19-20, 29-31, 45, 90-96, 130) to Azure OpenAI using the same env vars + `_call_azure`-style call. Update the "requires GEMINI_API_KEY or exit" guard to require Azure vars. Report label (line 130) → Azure deployment name.

### 5. `frontend/src/pages/ProgressPage.tsx:55`
- Update hardcoded text `"Usually ~30s with Gemini, 1–2 min with Ollama fallback. Hang tight!"` → reference Azure OpenAI primary / Gemini fallback (drop Ollama). No type/logic changes — SSE status strings unchanged.

### 6. Docs — `README.md` + `CLAUDE.md`
- `README.md`: lines 6, 16, 37 (intro), 58-70 (delete Ollama setup section), 72-82 (Gemini → now fallback wording), 166-168 (model table: Azure OpenAI primary, Gemini fallback, drop llama3.2), Quick Start tabs (remove `ollama serve` tab).
- `CLAUDE.md`: line 7 (overview), lines 16-20 (delete Ollama prereq), lines 82-88 (config: replace `OLLAMA_MODEL` with Azure vars, note Gemini is fallback).

### 7. Tests
- `backend/tests/test_analyze.py:69` — comment mentions "Gemini → Ollama"; update to "Azure → Gemini". No assertion logic depends on provider.

## Files NOT changing
- `routers/analyze.py` — callback signature + status strings preserved, so no edit needed (verify after).
- `models/schemas.py`, frontend types — SSEEvent shape unchanged.

## Verification
1. **Unit-ish**: `python -c "from services.feedback_service import get_feedback, _call_azure"` from `backend/` (venv active) — imports resolve, no `ollama` import error.
2. **Pip**: `pip install -r requirements.txt` succeeds with `openai`, no `ollama`.
3. **Azure-primary path**: set Azure vars in `.env`, run backend, drive E2E via Playwright (question + audio → feedback). Confirm SSE shows "Analyzing with Azure...", feedback renders, session persists. Backend log shows Azure call, not Gemini.
4. **Fallback path**: set a bogus `AZURE_OPENAI_API_KEY` (valid Gemini key present) → run pipeline → confirm it retries Azure, emits `fallback`, then succeeds via Gemini. SSE/frontend still render correctly.
5. **No-Azure path**: blank `AZURE_OPENAI_API_KEY` → pipeline skips straight to Gemini, succeeds.
6. **Eval**: `python evals/run_eval.py` with Azure configured → report generated against Azure deployment.
7. **Grep clean**: `grep -ri "ollama\|llama3" backend/ frontend/src README.md CLAUDE.md` returns nothing (except maybe historical plan/ files, which we leave).
