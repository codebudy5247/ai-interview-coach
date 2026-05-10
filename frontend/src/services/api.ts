import axios from 'axios'
import type { AnalyzeResponse, FeedbackResponse, SSEEvent, SessionListResponse } from '../types/api'

// All calls go through the Vite proxy: /api → http://localhost:8000/api
const http = axios.create({ baseURL: '/api' })

/**
 * POST /api/analyze — upload MP3 + question, get back session_id
 */
export async function analyzeAnswer(
  question: string,
  audioFile: File,
): Promise<AnalyzeResponse> {
  const form = new FormData()
  form.append('question', question)
  form.append('audio', audioFile)
  const { data } = await http.post<AnalyzeResponse>('/analyze', form)
  return data
}

/**
 * GET /api/feedback/:sessionId — returns full feedback JSON once pipeline is done.
 * Throws if the pipeline is still running (202) or errored (5xx).
 */
export async function getFeedback(sessionId: string): Promise<FeedbackResponse> {
  const { data, status } = await http.get<FeedbackResponse>(`/feedback/${sessionId}`, {
    // Don't throw on 202 so we can handle it ourselves
    validateStatus: (s) => s < 500,
  })
  if (status === 202) {
    throw new Error('Pipeline is still processing. Please wait a moment and refresh.')
  }
  if (status !== 200) {
    throw new Error(`Unexpected response (HTTP ${status})`)
  }
  return data
}

/**
 * GET /api/progress/:sessionId — opens an SSE stream and calls callbacks on each event.
 * Returns a cleanup function that closes the stream.
 */
export function openProgressStream(
  sessionId: string,
  onEvent: (event: SSEEvent) => void,
  onDone: () => void,
  onError: (message: string) => void,
): () => void {
  const es = new EventSource(`/api/progress/${sessionId}`)

  es.onmessage = (e: MessageEvent) => {
    try {
      const event: SSEEvent = JSON.parse(e.data as string)
      onEvent(event)
      if (event.step === 'done') {
        es.close()
        onDone()
      } else if (event.step === 'error') {
        es.close()
        onError(event.message)
      }
    } catch {
      // silently ignore malformed SSE payloads
    }
  }

  es.onerror = () => {
    es.close()
    onError('Lost connection to the server. Please try again.')
  }

  return () => es.close()
}

/**
 * GET /api/report/:sessionId — triggers a browser download of the .txt report
 */
export function downloadReport(sessionId: string): void {
  window.open(`/api/report/${sessionId}`, '_blank')
}

/**
 * GET /api/sessions — list all saved sessions with optional search and sort
 */
export async function getSessions(
  search?: string,
  sort: string = 'newest',
): Promise<SessionListResponse> {
  const params = new URLSearchParams()
  if (search) params.set('search', search)
  if (sort) params.set('sort', sort)
  const { data } = await http.get<SessionListResponse>(`/sessions?${params}`)
  return data
}

/**
 * GET /api/sessions/:sessionId — get full session detail with feedback
 */
export async function getSessionDetail(sessionId: string): Promise<{
  id: string
  question: string
  transcript: string
  overall_score: number
  feedback: FeedbackResponse
  created_at: string
}> {
  const { data } = await http.get(`/sessions/${sessionId}`)
  return data
}

/**
 * DELETE /api/sessions/:sessionId — delete a session from history
 */
export async function deleteSession(sessionId: string): Promise<void> {
  await http.delete(`/sessions/${sessionId}`)
}
