import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import QuestionInput from '../components/QuestionInput'
import AudioUploader from '../components/AudioUploader'
import { analyzeAnswer } from '../services/api'

export default function UploadPage() {
  const navigate = useNavigate()
  const [question, setQuestion] = useState('')
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const canSubmit = question.trim().length > 0 && audioFile !== null && !loading

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!canSubmit) return

    setLoading(true)
    setSubmitError(null)

    try {
      const { session_id } = await analyzeAnswer(question.trim(), audioFile!)
      navigate(`/progress/${session_id}`)
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : 'Upload failed. Make sure the backend is running and try again.'
      setSubmitError(msg)
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-2xl">

        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-slate-100 tracking-tight">
            🎯 Interview Coach
          </h1>
          <p className="mt-2 text-slate-400 text-sm">
            Practice. Get AI Feedback. Improve.
          </p>
          <Link
            to="/history"
            className="mt-3 inline-block text-sm text-indigo-400 hover:text-indigo-300"
          >
            📚 View History
          </Link>
        </div>

        {/* Form card */}
        <form
          id="upload-form"
          onSubmit={handleSubmit}
          className="rounded-xl border border-slate-800 bg-slate-900 p-6 flex flex-col gap-6"
        >
          <QuestionInput
            value={question}
            onChange={setQuestion}
            disabled={loading}
          />

          <AudioUploader
            file={audioFile}
            onFileChange={setAudioFile}
            disabled={loading}
          />

          {/* Submit error */}
          {submitError && (
            <div
              id="submit-error"
              role="alert"
              className="rounded-lg border border-rose-800 bg-rose-950/40 px-4 py-3 text-sm text-rose-300"
            >
              ⚠ {submitError}
            </div>
          )}

          <button
            id="btn-submit"
            type="submit"
            disabled={!canSubmit}
            className="w-full rounded-lg bg-indigo-600 px-4 py-3 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Uploading…' : '🚀 Analyze My Answer'}
          </button>

          {/* Validation hint */}
          {!canSubmit && !loading && (
            <p className="text-xs text-slate-500 text-center -mt-3">
              {!question.trim() && !audioFile
                ? 'Add your question and an audio file to continue'
                : !question.trim()
                ? 'Please enter the interview question'
                : 'Please provide an audio file'}
            </p>
          )}
        </form>

      </div>
    </div>
  )
}
