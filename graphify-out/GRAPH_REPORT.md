# Graph Report - /Users/ujjwal/Desktop/code/interview-coach  (2026-05-09)

## Corpus Check
- Corpus is ~8,583 words - fits in a single context window. You may not need a graph.

## Summary
- 98 nodes · 126 edges · 13 communities (11 shown, 2 thin omitted)
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 20 edges (avg confidence: 0.82)
- Token cost: 16,293 input · 16,292 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Main App & Router Logic|Main App & Router Logic]]
- [[_COMMUNITY_Project Setup & Config|Project Setup & Config]]
- [[_COMMUNITY_Feedback Service|Feedback Service]]
- [[_COMMUNITY_API Endpoints|API Endpoints]]
- [[_COMMUNITY_Data Models|Data Models]]
- [[_COMMUNITY_Transcription Service|Transcription Service]]
- [[_COMMUNITY_Analysis Results|Analysis Results]]
- [[_COMMUNITY_Plan Schemas|Plan Schemas]]
- [[_COMMUNITY_Plan Feedback|Plan Feedback]]

## God Nodes (most connected - your core abstractions)
1. `get_feedback()` - 9 edges
2. `_run_pipeline()` - 7 edges
3. `Implementation Plan` - 7 edges
4. `Interview Coach` - 6 edges
5. `Python Dependencies` - 6 edges
6. `get_session()` - 5 edges
7. `Gemini API` - 5 edges
8. `Ollama llama3.2` - 5 edges
9. `analyze()` - 4 edges
10. `download_report()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `google-genai` --semantically_similar_to--> `Gemini API`  [INFERRED] [semantically similar]
  backend/requirements.txt → README.md
- `ollama` --semantically_similar_to--> `Ollama llama3.2`  [INFERRED] [semantically similar]
  backend/requirements.txt → README.md
- `fastapi` --semantically_similar_to--> `FastAPI`  [INFERRED] [semantically similar]
  backend/requirements.txt → README.md
- `openai-whisper` --semantically_similar_to--> `OpenAI Whisper`  [INFERRED] [semantically similar]
  backend/requirements.txt → README.md
- `_run_pipeline()` --calls--> `transcribe()`  [INFERRED]
  routers/analyze.py → services/whisper_service.py

## Hyperedges (group relationships)
- **AI Pipeline Components** — readme_whisper, implementation_plan_whisper_service, readme_gemini_api, readme_ollama, implementation_plan_feedback_service [EXTRACTED 1.00]
- **Feedback Report Evaluation Structure** — analyze_response_ollama_feedback, analyze_response_gemini_feedback, implementation_plan_feedback_response, feedback_report_71eac94b, feedback_report_def93ad8 [EXTRACTED 1.00]
- **Backend Services** — implementation_plan_whisper_service, implementation_plan_feedback_service, implementation_plan_file_handler, implementation_plan_analyze_router [EXTRACTED 1.00]

## Communities (13 total, 2 thin omitted)

### Community 0 - "Main App & Router Logic"
Cohesion: 0.1
Nodes (19): startup_event(), analyze(), cleanup(), - Save the uploaded MP3 to temp/     - Register the session     - Kick off the A, Remove temp MP3 and session data., Full AI pipeline executed in a background thread so the POST /api/analyze     en, _run_pipeline(), delete_temp() (+11 more)

### Community 1 - "Project Setup & Config"
Cohesion: 0.15
Nodes (20): Implementation Plan, analyze.py router, feedback_service.py, file_handler.py, Retry Mechanism, Server-Sent Events, whisper_service.py, FastAPI (+12 more)

### Community 2 - "Feedback Service"
Cohesion: 0.15
Nodes (18): Exception, build_prompt(), _call_gemini(), _call_ollama(), FeedbackServiceError, _gemini_retry_delay(), get_feedback(), _is_quota_exhausted() (+10 more)

### Community 3 - "API Endpoints"
Cohesion: 0.27
Nodes (9): download_report(), get_feedback_endpoint(), get_session(), get_status(), routers/analyze.py ------------------ All API route handlers for the interview-c, Return the feedback JSON once the pipeline is done.     Returns 202 while still, Return the current pipeline status for a session.     Statuses: uploaded → trans, Serve the saved .txt feedback report as a file download.      Returns:         2 (+1 more)

### Community 4 - "Data Models"
Cohesion: 0.48
Nodes (6): BaseModel, AnalyzeResponse, CleanupResponse, FeedbackResponse, FeedbackScore, SSEEvent

### Community 5 - "Transcription Service"
Cohesion: 0.33
Nodes (5): _get_model(), whisper_service.py ------------------ Transcribes an MP3 file to text using Open, Lazy-load and cache the Whisper model., Transcribe the audio file at `mp3_path` and return the transcript string.      A, transcribe()

### Community 6 - "Analysis Results"
Cohesion: 0.38
Nodes (7): AI Response Analysis, Gemini Flash Feedback, Ollama llama3.2 Feedback, Interview Transcript, Feedback Report 71eac94b, Closures Question, Feedback Report def93ad8

## Knowledge Gaps
- **34 isolated node(s):** `routers/analyze.py ------------------ All API route handlers for the interview-c`, `Retrieve a session or raise 404.`, `Full AI pipeline executed in a background thread so the POST /api/analyze     en`, `- Save the uploaded MP3 to temp/     - Register the session     - Kick off the A`, `Return the feedback JSON once the pipeline is done.     Returns 202 while still` (+29 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_run_pipeline()` connect `Main App & Router Logic` to `Feedback Service`, `API Endpoints`, `Transcription Service`?**
  _High betweenness centrality (0.274) - this node is a cross-community bridge._
- **Why does `get_feedback()` connect `Feedback Service` to `Main App & Router Logic`?**
  _High betweenness centrality (0.189) - this node is a cross-community bridge._
- **Why does `transcribe()` connect `Transcription Service` to `Main App & Router Logic`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `_run_pipeline()` (e.g. with `transcribe()` and `get_feedback()`) actually correct?**
  _`_run_pipeline()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `routers/analyze.py ------------------ All API route handlers for the interview-c`, `Retrieve a session or raise 404.`, `Full AI pipeline executed in a background thread so the POST /api/analyze     en` to the rest of the system?**
  _34 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Main App & Router Logic` be split into smaller, more focused modules?**
  _Cohesion score 0.1 - nodes in this community are weakly interconnected._