import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import FeedbackReport from '../components/FeedbackReport'
import { getFeedback, getSessionDetail, downloadReport } from '../services/api'
import type { FeedbackResponse } from '../types/api'

export default function FeedbackPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()

  const [feedback, setFeedback] = useState<FeedbackResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const [processing, setProcessing] = useState(false)
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const attemptsRef = useRef(0)
  const MAX_ATTEMPTS = 30 // 30 × 2 s = 60 s max wait

  useEffect(() => {
    if (!sessionId) return

    async function tryFetch() {
      attemptsRef.current += 1
      try {
        const data = await getFeedback(sessionId!)
        setFeedback(data)
        setLoading(false)
        setProcessing(false)
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Could not load feedback.'
        // If pipeline still running, retry up to MAX_ATTEMPTS
        if (msg.includes('still processing') && attemptsRef.current < MAX_ATTEMPTS) {
          setProcessing(true)
          retryRef.current = setTimeout(tryFetch, 2000)
        } else {
          // Try loading from DB (in-memory session may be gone after server restart)
          try {
            const sessionData = await getSessionDetail(sessionId!)
            setFeedback(sessionData.feedback)
            setLoading(false)
            setProcessing(false)
          } catch (dbErr) {
            setError(msg)
            setLoading(false)
          }
        }
      }
    }

    tryFetch()
    return () => { if (retryRef.current) clearTimeout(retryRef.current) }
  }, [sessionId])

  // Loading / waiting state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-400 text-sm animate-pulse">
            {processing
              ? '⏳ Pipeline still running — fetching feedback…'
              : 'Loading feedback…'}
          </p>
          {processing && (
            <p className="text-slate-600 text-xs mt-1">
              This can take up to 60 s. Hang tight!
            </p>
          )}
        </div>
      </div>
    )
  }

  // Error state
  if (error || !feedback) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-4">
        <div className="w-full max-w-md rounded-xl border border-rose-800 bg-rose-950/30 p-6 text-center">
          <p className="text-rose-300 font-medium mb-1">Failed to load feedback</p>
          <p className="text-rose-400 text-sm mb-4">{error}</p>
          <button
            id="btn-go-home"
            type="button"
            onClick={() => navigate('/')}
            className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
          >
            ← Start Over
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col items-center px-4 py-12">
      <div className="w-full max-w-2xl">

        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-100">📋 Feedback Report</h1>
            <p className="text-slate-500 text-sm mt-1">
              Session: {sessionId?.slice(0, 8)}
            </p>
          </div>
          <Link
            to="/history"
            className="text-sm text-indigo-400 hover:text-indigo-300"
          >
            📚 View History
          </Link>
        </div>

        <FeedbackReport
          feedback={feedback}
          onDownload={() => sessionId && downloadReport(sessionId)}
          onRestart={() => navigate('/')}
        />
      </div>
    </div>
  )
}
