import { Circle, Loader2, CheckCircle2, XCircle, type LucideIcon } from "lucide-react";
import type { SSEEvent } from "../types/api";

// The fixed ordered steps shown in the UI
const STEPS = [
  { key: "uploaded", label: "Audio Uploaded" },
  { key: "transcribing", label: "Transcribing Speech" },
  { key: "analyzing", label: "AI Analyzing Your Answer" },
  { key: "saving_report", label: "Saving Feedback Report" },
  { key: "done", label: "Complete" },
];

// Derive the status of each fixed step from the flat list of SSE events
function deriveStepStates(
  events: SSEEvent[],
): Map<string, { status: string; message: string }> {
  const map = new Map<string, { status: string; message: string }>();
  for (const e of events) {
    const key = e.step === "error" ? "error" : e.step;
    // Always overwrite so last event for a step wins
    map.set(key, { status: e.status, message: e.message });
  }
  return map;
}

// Map a step status to a lucide icon + color (spin flag for active states)
function stepIcon(status: string | undefined): {
  Icon: LucideIcon;
  className: string;
  spin?: boolean;
} {
  switch (status) {
    case "done":
      return { Icon: CheckCircle2, className: "text-emerald-400" };
    case "error":
      return { Icon: XCircle, className: "text-rose-400" };
    case "in_progress":
    case "retrying":
      return { Icon: Loader2, className: "text-indigo-400", spin: true };
    default:
      return { Icon: Circle, className: "text-slate-600" };
  }
}

interface ProgressTrackerProps {
  events: SSEEvent[];
  pipelineError: string | null;
}

export default function ProgressTracker({
  events,
  pipelineError,
}: ProgressTrackerProps) {
  const states = deriveStepStates(events);

  return (
    <div className="flex flex-col gap-1">
      {STEPS.map((step, i) => {
        const state = states.get(step.key);
        const isDone = state?.status === "done";
        const isActive =
          state?.status === "in_progress" || state?.status === "retrying";
        const isError =
          pipelineError !== null &&
          !isDone &&
          i === STEPS.findIndex((s) => !states.has(s.key));

        const { Icon, className, spin } = isError
          ? stepIcon("error")
          : stepIcon(state?.status);

        return (
          <div
            key={step.key}
            className={`flex items-start gap-3 px-4 py-3 rounded-lg
              ${isDone ? "bg-emerald-500/[0.08]" : isActive ? "bg-indigo-500/[0.08]" : "bg-transparent"}
            `}
          >
            <Icon
              className={`h-[18px] w-[18px] shrink-0 mt-0.5 ${className} ${spin ? "animate-spin" : ""}`}
            />
            <div className="flex-1 min-w-0">
              <p
                className={`text-sm font-medium ${isDone ? "text-emerald-300" : isActive ? "text-indigo-300" : "text-slate-400"}`}
              >
                {step.label}
              </p>
              {/* Show the latest message for active/done steps */}
              {state && state.message && state.status !== "done" && (
                <p className="text-xs text-slate-500 mt-0.5 truncate">
                  {state.message}
                </p>
              )}
            </div>
          </div>
        );
      })}

      {/* Pipeline error message */}
      {pipelineError && (
        <div className="mt-3 rounded-lg ring-1 ring-rose-500/30 bg-rose-500/10 px-4 py-3">
          <p className="text-sm font-medium text-rose-300">Pipeline Error</p>
          <p className="text-xs text-rose-400 mt-1">{pipelineError}</p>
        </div>
      )}
    </div>
  );
}
