import { useRef, useState } from "react";

interface AudioUploaderProps {
  file: File | null;
  onFileChange: (file: File | null) => void;
  disabled?: boolean;
}

const MAX_SIZE_MB = 100;
const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function AudioUploader({
  file,
  onFileChange,
  disabled = false,
}: AudioUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function validate(f: File): string | null {
    if (
      !f.name.toLowerCase().endsWith(".mp3") &&
      f.type !== "audio/mpeg" &&
      f.type !== "audio/mp3"
    ) {
      return "Only MP3 files are accepted.";
    }
    if (f.size > MAX_SIZE_BYTES) {
      return `File is too large (${formatSize(f.size)}). Max size is ${MAX_SIZE_MB} MB.`;
    }
    return null;
  }

  function handleFile(f: File) {
    const err = validate(f);
    if (err) {
      setError(err);
      onFileChange(null);
    } else {
      setError(null);
      onFileChange(f);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    if (disabled) return;
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFile(dropped);
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0];
    if (picked) handleFile(picked);
    // reset so re-selecting same file triggers onChange
    e.target.value = "";
  }

  function handleRemove() {
    setError(null);
    onFileChange(null);
  }

  return (
    <div className="flex flex-col gap-2">
      <label className="text-sm font-medium text-slate-300">
        Your Answer (MP3)
      </label>

      {/* Drop zone */}
      <div
        id="audio-drop-zone"
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label="Upload MP3 file"
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) =>
          e.key === "Enter" && !disabled && inputRef.current?.click()
        }
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`
          relative flex flex-col items-center justify-center gap-3
          rounded-lg border-2 border-dashed px-6 py-8 cursor-pointer
          transition-colors duration-150
          ${dragOver ? "border-indigo-400 bg-indigo-950/30" : "border-slate-700 bg-slate-800/50 hover:border-slate-500"}
          ${disabled ? "opacity-50 cursor-not-allowed" : ""}
        `}
      >
        {file ? (
          /* File selected state */
          <div className="flex items-center gap-4 w-full">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-indigo-500/20 shrink-0">
              <span className="text-xl">🎵</span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-slate-100 truncate">
                {file.name}
              </p>
              <p className="text-xs text-slate-400">{formatSize(file.size)}</p>
            </div>
            <button
              id="audio-remove-btn"
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleRemove();
              }}
              className="text-xs text-slate-500 hover:text-rose-400 px-2 py-1 rounded transition-colors"
              aria-label="Remove file"
            >
              Remove
            </button>
          </div>
        ) : (
          /* Empty state */
          <>
            <span className="text-3xl">🎤</span>
            <div className="text-center">
              <p className="text-sm text-slate-300">
                Drop your MP3 here or{" "}
                <span className="text-indigo-400 font-medium">
                  click to browse
                </span>
              </p>
              <p className="text-xs text-slate-500 mt-1">
                MP3 only · Max {MAX_SIZE_MB} MB
              </p>
            </div>
          </>
        )}
      </div>

      {/* Validation error */}
      {error && (
        <p id="audio-error" role="alert" className="text-xs text-rose-400">
          ⚠ {error}
        </p>
      )}

      {/* Hidden file input */}
      <input
        ref={inputRef}
        type="file"
        accept=".mp3,audio/mpeg,audio/mp3"
        onChange={handleInputChange}
        disabled={disabled}
        className="hidden"
        aria-hidden="true"
      />
    </div>
  );
}
