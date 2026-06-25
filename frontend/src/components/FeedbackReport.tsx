import { useState } from "react";
import {
  CheckCircle2,
  Pin,
  Lightbulb,
  FileText,
  Code2,
  Trophy,
  Download,
  RotateCcw,
  ChevronDown,
  type LucideIcon,
} from "lucide-react";
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
  icon: Icon,
  iconClass = "text-slate-400",
  title,
  children,
  defaultOpen = false,
}: {
  id: string;
  icon: LucideIcon;
  iconClass?: string;
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="rounded-lg ring-1 ring-white/[0.06] overflow-hidden">
      <button
        id={id}
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 bg-surface-2 hover:bg-white/[0.06] text-left transition-colors"
        aria-expanded={open}
      >
        <span className="flex items-center gap-2 text-sm font-medium text-slate-200">
          <Icon className={`h-4 w-4 ${iconClass}`} />
          {title}
        </span>
        <ChevronDown
          className={`h-4 w-4 text-slate-500 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && <div className="px-4 py-3 bg-surface/40">{children}</div>}
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
      <div className="flex flex-col items-center gap-2 py-6 rounded-lg ring-1 ring-white/[0.06] bg-surface/40">
        <ScoreRing score={feedback.overall_score} size={120} />
        <p className="text-sm text-slate-400 mt-1">Overall Score</p>
      </div>

      {/* ── 4 Dimension Score Cards ── */}
      <div className="grid grid-cols-2 gap-3">
        {Object.entries(feedback.scores).map(([dim, val]) => (
          <div
            key={dim}
            className="flex flex-col gap-2 rounded-lg ring-1 ring-white/[0.06] bg-surface/40 p-4"
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
            <div className="h-1 w-full rounded-full bg-surface-2">
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
          icon={CheckCircle2}
          iconClass="text-emerald-400"
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

        <Section id="section-missed" icon={Pin} iconClass="text-amber-400" title="What You Missed">
          <ul className="flex flex-col gap-1.5">
            {feedback.what_was_missed.map((item, i) => (
              <li key={i} className="flex gap-2 text-sm text-slate-300">
                <span className="text-amber-400 shrink-0">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </Section>

        <Section id="section-improvements" icon={Lightbulb} iconClass="text-indigo-400" title="How to Improve">
          <ul className="flex flex-col gap-1.5">
            {feedback.improvements.map((item, i) => (
              <li key={i} className="flex gap-2 text-sm text-slate-300">
                <span className="text-indigo-400 shrink-0">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </Section>

        <Section id="section-transcript" icon={FileText} title="Your Transcript">
          {feedback.audio_url && (
            <audio controls src={feedback.audio_url} className="w-full" />
          )}
          <p className="text-sm text-slate-400 leading-relaxed italic mb-3 mt-5">
            "{feedback.transcript}"
          </p>
        </Section>

        {feedback.code_snippet && (
          <Section id="section-code" icon={Code2} title="Code Snippet">
            {feedback.code_language && feedback.code_language !== 'auto' && (
              <span className="text-xs text-slate-500 mb-2 block uppercase tracking-wider">
                {feedback.code_language}
              </span>
            )}
            <pre className="text-sm text-slate-300 bg-surface-2 rounded-lg p-4 overflow-x-auto font-mono">
              <code>{feedback.code_snippet}</code>
            </pre>
          </Section>
        )}

        <Section id="section-ideal" icon={Trophy} iconClass="text-amber-400" title="Ideal Answer">
          <p className="text-sm text-slate-300 leading-relaxed mb-3">
            {feedback.ideal_answer}
          </p>
          {feedback.ideal_code && (
            <pre className="text-sm text-slate-300 bg-surface-2 rounded-lg p-4 overflow-x-auto font-mono mt-3 ring-1 ring-white/[0.06]">
              <code>{feedback.ideal_code}</code>
            </pre>
          )}
        </Section>
      </div>

      {/* ── Action Buttons ── */}
      <div className="flex gap-3 pt-2">
        <button
          id="btn-download-report"
          type="button"
          onClick={onDownload}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-surface-2 ring-1 ring-white/[0.06] px-4 py-2.5 text-sm font-medium text-slate-200 hover:bg-white/[0.08] transition-colors"
        >
          <Download className="h-4 w-4" />
          Download Report
        </button>
        <button
          id="btn-analyze-another"
          type="button"
          onClick={onRestart}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
        >
          <RotateCcw className="h-4 w-4" />
          Analyze Another
        </button>
      </div>
    </div>
  );
}
