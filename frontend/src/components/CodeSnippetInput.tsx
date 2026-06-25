import { useState, useRef, useEffect } from 'react'

interface CodeSnippetInputProps {
  code: string
  language: string
  onCodeChange: (code: string) => void
  onLanguageChange: (language: string) => void
  disabled?: boolean
}

const LANGUAGES = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'python', label: 'Python' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'typescript', label: 'TypeScript' },
  { value: 'java', label: 'Java' },
  { value: 'cpp', label: 'C++' },
  { value: 'go', label: 'Go' },
  { value: 'rust', label: 'Rust' },
  { value: 'sql', label: 'SQL' },
  { value: 'other', label: 'Other' },
]

const MAX_CHARS = 5000

export default function CodeSnippetInput({
  code,
  language,
  onCodeChange,
  onLanguageChange,
  disabled = false,
}: CodeSnippetInputProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Expand automatically if code is passed initially
  useEffect(() => {
    if (code.trim() && !isExpanded) {
      setIsExpanded(true)
    }
  }, [code, isExpanded])

  const remaining = MAX_CHARS - code.length
  const isNearLimit = remaining < 100

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Tab') {
      e.preventDefault()
      const target = e.target as HTMLTextAreaElement
      const start = target.selectionStart
      const end = target.selectionEnd

      const newCode = code.substring(0, start) + '  ' + code.substring(end)
      onCodeChange(newCode)

      // Move cursor right after the inserted spaces
      setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.selectionStart = textareaRef.current.selectionEnd = start + 2
        }
      }, 0)
    }
  }

  const handleRemove = () => {
    onCodeChange('')
    onLanguageChange('auto')
    setIsExpanded(false)
  }

  return (
    <div className="flex flex-col gap-2">
      {!isExpanded ? (
        <button
          type="button"
          onClick={() => setIsExpanded(true)}
          disabled={disabled}
          className="self-start text-sm font-medium text-slate-400 hover:text-indigo-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        >
          <span>🔗</span> Attach Code Snippet (Optional)
        </button>
      ) : (
        <div className="flex flex-col gap-3 rounded-lg border border-slate-700 bg-slate-900/50 p-4 animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <label htmlFor="code-language" className="text-sm font-medium text-slate-300">
                Code Snippet
              </label>
              <select
                id="code-language"
                value={language}
                onChange={(e) => onLanguageChange(e.target.value)}
                disabled={disabled}
                className="rounded-md border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-slate-300 focus:border-indigo-500 focus:outline-none disabled:opacity-50"
              >
                {LANGUAGES.map((lang) => (
                  <option key={lang.value} value={lang.value}>
                    {lang.label}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              onClick={handleRemove}
              disabled={disabled}
              className="text-xs font-medium text-slate-500 hover:text-rose-400 disabled:opacity-50 transition-colors flex items-center gap-1"
            >
              <span>✕</span> Remove
            </button>
          </div>

          <div className="relative">
            <textarea
              ref={textareaRef}
              id="code-snippet-input"
              value={code}
              onChange={(e) => onCodeChange(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={disabled}
              maxLength={MAX_CHARS}
              rows={8}
              placeholder="Paste your code here..."
              className="w-full rounded-md border border-slate-700 bg-slate-800 p-3 font-mono text-sm text-slate-200 placeholder-slate-500 resize-y focus:border-indigo-500 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              spellCheck={false}
            />
            <div className="absolute bottom-2 right-2 px-1 bg-slate-800 rounded">
              <span className={`text-xs ${isNearLimit ? 'text-amber-400' : 'text-slate-500'}`}>
                {code.length} / {MAX_CHARS}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
