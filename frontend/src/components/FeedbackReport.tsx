import { useState } from "react";
import type { FeedbackResponse } from "../types/api";
import ScoreRing from "./ScoreRing";

interface FeedbackReportProps {
  feedback: FeedbackResponse;
  onDownload: () => void;
  onRestart: () => void;
}

const SCORE_LABELS: Record<string, string> = {
  correctness: "Correctness",
  clarity: "Clarity",
  structure: "Structure",
  relevance: "Relevance",
};

function getScoreColor(score: number): string {
  if (score >= 8) return "text-emerald-400";
  if (score >= 5) return "text-amber-400";
  return "text-rose-400";
}

function getBarColor(score: number): string {
  if (score >= 8) return "bg-emerald-500";
  if (score >= 5) return "bg-amber-500";
  return "bg-rose-500";
}

// Collapsible section
function Section({
  id,
  emoji,
  title,
  children,
  defaultOpen = false,
}: {
  id: string;
  emoji: string;
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="rounded-lg border border-slate-800 overflow-hidden">
      <button
        id={id}
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 bg-slate-800/60 hover:bg-slate-800 text-left transition-colors"
        aria-expanded={open}
      >
        <span className="text-sm font-medium text-slate-200">
          {emoji} {title}
        </span>
        <span className="text-slate-500 text-xs">{open ? "▲" : "▼"}</span>
      </button>
      {open && <div className="px-4 py-3 bg-slate-900/40">{children}</div>}
    </div>
  );
}

export default function FeedbackReport({
  feedback,
  onDownload,
  onRestart,
}: FeedbackReportProps) {
  return (
    <div className="flex flex-col gap-6">
      {/* ── Overall Score ── */}
      <div className="flex flex-col items-center gap-2 py-6 rounded-lg border border-slate-800 bg-slate-900/40">
        <ScoreRing score={feedback.overall_score} size={120} />
        <p className="text-sm text-slate-400 mt-1">Overall Score</p>
      </div>

      {/* ── 4 Dimension Score Cards ── */}
      <div className="grid grid-cols-2 gap-3">
        {Object.entries(feedback.scores).map(([dim, val]) => (
          <div
            key={dim}
            className="flex flex-col gap-2 rounded-lg border border-slate-800 bg-slate-900/40 p-4"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                {SCORE_LABELS[dim] ?? dim}
              </span>
              <span className={`text-sm font-bold ${getScoreColor(val.score)}`}>
                {val.score}/10
              </span>
            </div>
            {/* mini bar */}
            <div className="h-1 w-full rounded-full bg-slate-700">
              <div
                className={`h-1 rounded-full ${getBarColor(val.score)}`}
                style={{ width: `${(val.score / 10) * 100}%` }}
              />
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              {val.feedback}
            </p>
          </div>
        ))}
      </div>

      {/* ── Collapsible Sections ── */}
      <div className="flex flex-col gap-2">
        <Section
          id="section-went-well"
          emoji="✅"
          title="What You Did Well"
          defaultOpen
        >
          <ul className="flex flex-col gap-1.5">
            {feedback.what_went_well.map((item, i) => (
              <li key={i} className="flex gap-2 text-sm text-slate-300">
                <span className="text-emerald-400 shrink-0">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </Section>

        <Section id="section-missed" emoji="📌" title="What You Missed">
          <ul className="flex flex-col gap-1.5">
            {feedback.what_was_missed.map((item, i) => (
              <li key={i} className="flex gap-2 text-sm text-slate-300">
                <span className="text-amber-400 shrink-0">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </Section>

        <Section id="section-improvements" emoji="💡" title="How to Improve">
          <ul className="flex flex-col gap-1.5">
            {feedback.improvements.map((item, i) => (
              <li key={i} className="flex gap-2 text-sm text-slate-300">
                <span className="text-indigo-400 shrink-0">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </Section>

        <Section id="section-transcript" emoji="📝" title="Your Transcript" defaultOpen>
          <p className="text-sm text-slate-400 leading-relaxed italic mb-3">
            "{feedback.transcript}"
          </p>
          {feedback.audio_url && (
            <audio controls src={feedback.audio_url} className="w-full" />
          )}
        </Section>

        <Section id="section-ideal" emoji="🏆" title="Ideal Answer">
          <p className="text-sm text-slate-300 leading-relaxed">
            {feedback.ideal_answer}
          </p>
        </Section>
      </div>

      {/* ── Action Buttons ── */}
      <div className="flex gap-3 pt-2">
        <button
          id="btn-download-report"
          type="button"
          onClick={onDownload}
          className="flex-1 rounded-lg border border-slate-700 bg-slate-800 px-4 py-2.5 text-sm font-medium text-slate-200 hover:bg-slate-700 transition-colors"
        >
          📄 Download Report
        </button>
        <button
          id="btn-analyze-another"
          type="button"
          onClick={onRestart}
          className="flex-1 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
        >
          🔁 Analyze Another
        </button>
      </div>
    </div>
  );
}
