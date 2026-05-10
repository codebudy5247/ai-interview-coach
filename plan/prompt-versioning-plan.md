# Prompt Versioning Implementation Plan

This plan outlines a strategy for managing, versioning, and tracking the LLM prompts used to generate interview feedback. By extracting prompts from the codebase and tracking which version generated which feedback, we can safely iterate on prompts and A/B test their performance.

## Proposed Changes

### 1. Externalize Prompts

Currently, the evaluation prompt is hardcoded as a Python string inside `feedback_service.py`. We will extract it into dedicated template files.

#### [NEW] `backend/prompts/` Directory
- Create a new folder dedicated to storing prompt templates.
- **`backend/prompts/feedback_v1.txt`**: Move the current hardcoded prompt here. Use template placeholders (like `{question}`, `{transcript}`, `{rubric}`, and `{schema}`).
- **`backend/prompts/feedback_v2.txt`**: (Optional) An area to experiment with a new prompt structure.

### 2. Configuration & Service Updates

#### [MODIFY] `backend/.env` & `.env.example`
- Add a new environment variable to define the active prompt:
  ```env
  ACTIVE_PROMPT_VERSION=v1
  ```

#### [MODIFY] `backend/services/feedback_service.py`
- Refactor the `build_prompt()` function to dynamically load the text file corresponding to `ACTIVE_PROMPT_VERSION` (e.g., `prompts/feedback_v1.txt`).
- Use Python's `.format()` or a templating engine to inject the `question`, `transcript`, `rubric`, and `schema` into the loaded template.
- Make `get_feedback()` return the used `prompt_version` alongside the feedback payload so it can be saved.

### 3. Database Tracking (Data Lineage)

To properly evaluate prompts (especially with our offline evals), we need to know exactly which prompt version generated a specific feedback report in production.

#### [MODIFY] `backend/models/session_model.py`
- Add a new column to the `InterviewSession` model:
  `prompt_version = Column(String, default="v1")`
- *(Alternatively, if we are still avoiding DB schema migrations, we can append `prompt_version` to the `feedback_json` dictionary instead).*

#### [MODIFY] `backend/routers/analyze.py`
- Update the pipeline persistence step so that the `prompt_version` is correctly recorded in the database when the session is saved.

---

## Implementation Phases

### Phase 1: File Structure & Refactoring
- Create the `backend/prompts/` directory and `feedback_v1.txt`.
- Update `.env` with `ACTIVE_PROMPT_VERSION`.
- Refactor `feedback_service.py` to read from the file instead of the hardcoded string.

### Phase 2: Traceability & DB Updates
- Update `get_feedback()` to return the prompt version used.
- Update `InterviewSession` (or `feedback_json`) to store the `prompt_version` for historical tracking.

## Verification Plan
1. Start the backend with `ACTIVE_PROMPT_VERSION=v1`.
2. Submit a mock interview.
3. Verify that the feedback is generated successfully.
4. Verify in the database (or via the `/api/sessions/` endpoint) that the `prompt_version` is correctly saved alongside the session.
