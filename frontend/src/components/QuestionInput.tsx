interface QuestionInputProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

const MAX_CHARS = 1000;

export default function QuestionInput({
  value,
  onChange,
  disabled = false,
}: QuestionInputProps) {
  const remaining = MAX_CHARS - value.length;
  const isNearLimit = remaining < 100;

  return (
    <div className="flex flex-col gap-2">
      <label
        htmlFor="question-input"
        className="text-sm font-medium text-slate-300"
      >
        Interview Question
      </label>

      <textarea
        id="question-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        maxLength={MAX_CHARS}
        rows={4}
        placeholder='e.g. "Explain how closures work and give a real world example."'
        className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-sm text-slate-100 placeholder-slate-500 resize-none focus:outline-none focus:border-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
      />

      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500">
          💡 Paste the exact question for best results
        </p>
        <span
          className={`text-xs ${isNearLimit ? "text-amber-400" : "text-slate-500"}`}
        >
          {value.length} / {MAX_CHARS}
        </span>
      </div>
    </div>
  );
}
