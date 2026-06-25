// All TypeScript types mirroring the backend Pydantic schemas

export interface FeedbackScore {
  score: number       // 1–10
  feedback: string    // per-dimension explanation
}

export interface FeedbackResponse {
  overall_score: number
  scores: {
    correctness: FeedbackScore
    clarity: FeedbackScore
    structure: FeedbackScore
    relevance: FeedbackScore
  }
  what_went_well: string[]
  what_was_missed: string[]
  improvements: string[]
  ideal_answer: string
  ideal_code?: string
  transcript: string
  audio_url?: string
  code_snippet?: string
  code_language?: string
}

export interface SSEEvent {
  step: string    // 'uploaded' | 'transcribing' | 'analyzing' | 'saving_report' | 'done' | 'error'
  status: string  // 'in_progress' | 'done' | 'error' | 'retrying' | ...
  message: string
}

export interface AnalyzeResponse {
  session_id: string
}

export interface SessionSummary {
  id: string
  question: string
  overall_score: number
  created_at: string
}

export interface SessionListResponse {
  sessions: SessionSummary[]
  total: number
}
