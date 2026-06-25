import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Loader2, CheckCircle2, XCircle, ArrowLeft } from 'lucide-react'
import ProgressTracker from '../components/ProgressTracker'
import { openProgressStream } from '../services/api'
import type { SSEEvent } from '../types/api'

export default function ProgressPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()

  const [events, setEvents] = useState<SSEEvent[]>([])
  const [pipelineError, setPipelineError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  // Guard against React StrictMode double-mount
  const streamOpenedRef = useRef(false)

  useEffect(() => {
    if (!sessionId || streamOpenedRef.current) return
    streamOpenedRef.current = true

    const close = openProgressStream(
      sessionId,
      (event) => setEvents((prev) => [...prev, event]),
      () => {
        setDone(true)
        // Brief pause so user sees the completed steps before redirect
        setTimeout(() => navigate(`/feedback/${sessionId}`), 800)
      },
      (msg) => setPipelineError(msg),
    )

    return () => {
      close()
      // Reset guard so React StrictMode's unmount→remount can re-open the stream
      streamOpenedRef.current = false
    }
  }, [sessionId, navigate])

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-xl">

        {/* Header */}
        <div className="mb-6 text-center">
          <h1 className="flex items-center justify-center gap-2 text-xl font-semibold text-slate-100">
            {done ? (
              <>
                <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                Done! Redirecting…
              </>
            ) : pipelineError ? (
              <>
                <XCircle className="h-5 w-5 text-rose-400" />
                Something went wrong
              </>
            ) : (
              <>
                <Loader2 className="h-5 w-5 text-indigo-400 animate-spin" />
                Analyzing your answer…
              </>
            )}
          </h1>
          {!done && !pipelineError && (
            <p className="mt-1 text-sm text-slate-500">
              Usually ~30s with Azure OpenAI, a bit longer if it falls back to Gemini. Hang tight!
            </p>
          )}
        </div>

        {/* Steps */}
        <div className="rounded-xl bg-surface ring-1 ring-white/[0.06] p-4">
          <ProgressTracker events={events} pipelineError={pipelineError} />
        </div>

        {/* Error — retry button */}
        {pipelineError && (
          <div className="mt-4 text-center">
            <button
              id="btn-retry"
              type="button"
              onClick={() => navigate('/')}
              className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              Try Again
            </button>
          </div>
        )}

        {/* Session ID (small, for debugging) */}
        <p className="mt-6 text-center text-xs text-slate-700">
          Session: {sessionId?.slice(0, 8)}
        </p>
      </div>
    </div>
  )
}
