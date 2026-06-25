import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { History, Target, Search, Trash2 } from 'lucide-react'
import { getSessions, deleteSession } from '../services/api'
import type { SessionSummary } from '../types/api'

type SortOption = 'newest' | 'oldest' | 'highest' | 'lowest'

export default function HistoryPage() {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState<SortOption>('newest')
  const [deleteId, setDeleteId] = useState<string | null>(null)

  useEffect(() => {
    loadSessions()
  }, [search, sort])

  async function loadSessions() {
    setLoading(true)
    try {
      const data = await getSessions(search, sort)
      setSessions(data.sessions)
    } catch (err) {
      console.error('Failed to load sessions:', err)
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(sessionId: string) {
    try {
      await deleteSession(sessionId)
      setSessions(sessions.filter((s) => s.id !== sessionId))
    } catch (err) {
      console.error('Failed to delete session:', err)
    }
    setDeleteId(null)
  }

  function formatDate(dateStr: string) {
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  }

  function getScoreColor(score: number) {
    if (score >= 8) return 'text-emerald-400'
    if (score >= 5) return 'text-amber-400'
    return 'text-rose-400'
  }

  // Loading skeleton component
  function SessionSkeleton() {
    return (
      <div className="rounded-xl bg-surface ring-1 ring-white/[0.06] p-4 animate-pulse">
        <div className="h-5 bg-surface-2 rounded w-3/4 mb-3" />
        <div className="h-4 bg-surface-2 rounded w-1/4" />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col items-center px-4 py-12">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="flex items-center gap-2.5 text-3xl font-bold text-slate-100 tracking-tight">
              <History className="h-7 w-7 text-indigo-400" strokeWidth={2.25} />
              Session History
            </h1>
            <p className="mt-2 text-slate-400 text-sm">
              Browse and review your past practice sessions
            </p>
          </div>
          <button
            onClick={() => navigate('/')}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-500 transition-colors"
          >
            <Target className="h-4 w-4" />
            New Session
          </button>
        </div>

        {/* Search and Sort */}
        <div className="flex gap-4 mb-6">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search questions..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-lg bg-surface ring-1 ring-white/[0.06] pl-9 pr-4 py-2 text-sm text-slate-200 placeholder-slate-500 focus:ring-indigo-500 focus:outline-none transition-shadow"
            />
          </div>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortOption)}
            className="rounded-lg bg-surface ring-1 ring-white/[0.06] px-4 py-2 text-sm text-slate-200 focus:ring-indigo-500 focus:outline-none transition-shadow"
          >
            <option value="newest">Newest</option>
            <option value="oldest">Oldest</option>
            <option value="highest">Highest Score</option>
            <option value="lowest">Lowest Score</option>
          </select>
        </div>

        {/* Session List */}
        {loading ? (
          <div className="flex flex-col gap-4">
            <SessionSkeleton />
            <SessionSkeleton />
            <SessionSkeleton />
          </div>
        ) : sessions.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-slate-400 mb-4">No sessions yet.</p>
            <button
              onClick={() => navigate('/')}
              className="text-indigo-400 hover:text-indigo-300 transition-colors"
            >
              Start your first practice session →
            </button>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {sessions.map((session) => (
              <div
                key={session.id}
                className="rounded-xl bg-surface ring-1 ring-white/[0.06] hover:ring-white/[0.12] p-4 flex items-center justify-between transition-shadow"
              >
                <div
                  className="flex-1 min-w-0 cursor-pointer"
                  onClick={() => navigate(`/feedback/${session.id}`)}
                >
                  <p className="text-slate-200 font-medium truncate">{session.question}</p>
                  <div className="flex items-center gap-3 mt-1 text-sm">
                    <span className={getScoreColor(session.overall_score)}>
                      Score: {session.overall_score}/10
                    </span>
                    <span className="text-slate-600">•</span>
                    <span className="text-slate-500">{formatDate(session.created_at)}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2 ml-4">
                  <button
                    onClick={() => navigate(`/feedback/${session.id}`)}
                    className="px-3 py-1.5 rounded-lg bg-surface-2 text-slate-300 text-sm hover:bg-white/[0.08] transition-colors"
                  >
                    View
                  </button>
                  <button
                    onClick={() => setDeleteId(session.id)}
                    aria-label="Delete session"
                    className="p-2 rounded-lg bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 transition-colors"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Delete Confirmation Modal */}
        {deleteId && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="rounded-xl bg-surface ring-1 ring-white/[0.1] p-6 max-w-sm w-full">
              <h3 className="text-lg font-semibold text-slate-100 mb-2">Delete Session?</h3>
              <p className="text-slate-400 text-sm mb-4">
                This action cannot be undone. The session and its feedback will be permanently
                deleted.
              </p>
              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setDeleteId(null)}
                  className="px-4 py-2 rounded-lg bg-surface-2 text-slate-300 text-sm hover:bg-white/[0.08] transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={() => handleDelete(deleteId)}
                  className="px-4 py-2 rounded-lg bg-rose-600 text-white text-sm hover:bg-rose-500 transition-colors"
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
