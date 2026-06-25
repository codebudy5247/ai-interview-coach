import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Target, History, Sparkles, AlertTriangle } from 'lucide-react'
import QuestionInput from '../components/QuestionInput'
import AudioUploader from '../components/AudioUploader'
import CodeSnippetInput from '../components/CodeSnippetInput'
import { analyzeAnswer } from '../services/api'

export default function UploadPage() {
  const navigate = useNavigate()
  const [question, setQuestion] = useState('')
  const [codeSnippet, setCodeSnippet] = useState('')
  const [codeLanguage, setCodeLanguage] = useState('auto')
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
      const { session_id } = await analyzeAnswer(
        question.trim(),
        audioFile!,
        codeSnippet,
        codeLanguage
      )
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
          <h1 className="flex items-center justify-center gap-2.5 text-3xl font-bold text-slate-100 tracking-tight">
            <Target className="h-7 w-7 text-indigo-400" strokeWidth={2.25} />
            Interview Coach
          </h1>
          <p className="mt-2 text-slate-400 text-sm">
            Practice. Get AI Feedback. Improve.
          </p>
          <Link
            to="/history"
            className="mt-4 inline-flex items-center gap-1.5 text-sm text-indigo-400 hover:text-indigo-300 transition-colors"
          >
            <History className="h-4 w-4" />
            View History
          </Link>
        </div>

        {/* Form card */}
        <form
          id="upload-form"
          onSubmit={handleSubmit}
          className="rounded-xl bg-surface ring-1 ring-white/[0.06] p-6 flex flex-col gap-6"
        >
          <QuestionInput
            value={question}
            onChange={setQuestion}
            disabled={loading}
          />

          <CodeSnippetInput
            code={codeSnippet}
            language={codeLanguage}
            onCodeChange={setCodeSnippet}
            onLanguageChange={setCodeLanguage}
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
              className="flex items-start gap-2 rounded-lg ring-1 ring-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300"
            >
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{submitError}</span>
            </div>
          )}

          <button
            id="btn-submit"
            type="submit"
            disabled={!canSubmit}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-3 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <Sparkles className="h-4 w-4" />
            {loading ? 'Uploading…' : 'Analyze My Answer'}
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
