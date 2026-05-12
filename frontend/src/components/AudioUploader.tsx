import { useRef, useState, useEffect } from "react";
import { useAudioRecorder } from "../hooks/useAudioRecorder";

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

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default function AudioUploader({
  file,
  onFileChange,
  disabled = false,
}: AudioUploaderProps) {
  const [activeTab, setActiveTab] = useState<'upload' | 'record'>('upload');
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const {
    recording,
    duration,
    audioBlob,
    audioUrl,
    error: recorderError,
    permissionDenied,
    startRecording,
    stopRecording,
    resetRecording,
  } = useAudioRecorder(600); // 10 minutes max

  function validate(f: File): string | null {
    if (!f.type.startsWith("audio/") && !f.name.match(/\.(mp3|wav|m4a|webm|ogg|flac)$/i)) {
      return "Only audio files are accepted.";
    }
    if (f.size > MAX_SIZE_BYTES) {
      return `File is too large (${formatSize(f.size)}). Max size is ${MAX_SIZE_MB} MB.`;
    }
    return null;
  }

  function handleFile(f: File) {
    const err = validate(f);
    if (err) {
      setUploadError(err);
      onFileChange(null);
    } else {
      setUploadError(null);
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
    e.target.value = "";
  }

  function handleRemove() {
    setUploadError(null);
    onFileChange(null);
  }

  function handleUseRecording() {
    if (audioBlob) {
      const mimeType = audioBlob.type || 'audio/webm';
      const ext = mimeType.includes('mp4') ? 'm4a' : mimeType.includes('mpeg') ? 'mp3' : 'webm';
      const f = new File([audioBlob], `recording.${ext}`, { type: mimeType });
      handleFile(f);
    }
  }

  // Clear file when switching tabs
  function switchTab(tab: 'upload' | 'record') {
    if (disabled) return;
    setActiveTab(tab);
    if (file) handleRemove();
    if (tab === 'upload') {
      resetRecording();
    }
  }

  const combinedError = uploadError || recorderError;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-slate-300">
          Your Answer (Audio)
        </label>
        
        {/* Tabs */}
        <div className="flex bg-slate-800/50 p-1 rounded-lg">
          <button
            type="button"
            onClick={() => switchTab('upload')}
            disabled={disabled}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              activeTab === 'upload' 
                ? 'bg-slate-700 text-white shadow-sm' 
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            📁 Upload
          </button>
          <button
            type="button"
            onClick={() => switchTab('record')}
            disabled={disabled}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              activeTab === 'record' 
                ? 'bg-slate-700 text-white shadow-sm' 
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            🎙️ Record
          </button>
        </div>
      </div>

      {/* TABS CONTENT */}
      {activeTab === 'upload' ? (
        <div
          id="audio-drop-zone"
          role="button"
          tabIndex={disabled ? -1 : 0}
          aria-label="Upload Audio file"
          onClick={() => !disabled && inputRef.current?.click()}
          onKeyDown={(e) => e.key === "Enter" && !disabled && inputRef.current?.click()}
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
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  handleRemove();
                }}
                className="text-xs text-slate-500 hover:text-rose-400 px-2 py-1 rounded transition-colors"
              >
                Remove
              </button>
            </div>
          ) : (
            <>
              <span className="text-3xl">🎤</span>
              <div className="text-center">
                <p className="text-sm text-slate-300">
                  Drop your audio here or{" "}
                  <span className="text-indigo-400 font-medium">click to browse</span>
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  MP3, WAV, WebM · Max {MAX_SIZE_MB} MB
                </p>
              </div>
            </>
          )}
        </div>
      ) : (
        <div className={`
          relative flex flex-col items-center justify-center gap-4
          rounded-lg border-2 border-slate-700 bg-slate-800/50 px-6 py-8
          ${disabled ? "opacity-50" : ""}
        `}>
          {file ? (
            // State 4: Recording is approved and selected as a File
            <div className="flex flex-col items-center gap-3 w-full">
               <div className="flex items-center gap-2 text-emerald-400 text-sm font-medium">
                 <span>✅</span> Recording ready
               </div>
               {audioUrl && (
                 <audio src={audioUrl} controls className="w-full max-w-sm h-10" />
               )}
               <button
                 type="button"
                 onClick={() => {
                   handleRemove();
                   resetRecording();
                 }}
                 disabled={disabled}
                 className="text-xs text-slate-400 hover:text-slate-200"
               >
                 Discard & Re-record
               </button>
            </div>
          ) : audioUrl ? (
            // State 3: Done recording, playback and confirm
            <div className="flex flex-col items-center gap-4 w-full">
              <div className="text-sm text-slate-300 font-medium">
                Recording complete — {formatTime(duration)}
              </div>
              <audio src={audioUrl} controls className="w-full max-w-sm h-10" />
              <div className="flex gap-3 mt-2">
                <button
                  type="button"
                  onClick={resetRecording}
                  disabled={disabled}
                  className="px-4 py-2 text-sm font-medium text-slate-300 bg-slate-700 hover:bg-slate-600 rounded-md transition-colors"
                >
                  🔄 Re-record
                </button>
                <button
                  type="button"
                  onClick={handleUseRecording}
                  disabled={disabled}
                  className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-500 rounded-md transition-colors"
                >
                  ✅ Use this
                </button>
              </div>
            </div>
          ) : recording ? (
            // State 2: Recording in progress
            <div className="flex flex-col items-center gap-4">
              <div className="flex items-center gap-3">
                <span className="relative flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-rose-500"></span>
                </span>
                <span className="text-rose-400 font-medium text-sm tabular-nums">
                  Recording... {formatTime(duration)} / 10:00
                </span>
              </div>
              <button
                type="button"
                onClick={() => {
                  if (duration < 1) {
                    setUploadError("Recording is too short (less than 1 second). Please try again.");
                    resetRecording();
                  } else {
                    setUploadError(null);
                    stopRecording();
                  }
                }}
                className="px-6 py-2 text-sm font-medium text-white bg-rose-600 hover:bg-rose-500 rounded-md transition-colors"
              >
                ⏹️ Stop Recording
              </button>
            </div>
          ) : (
            // State 1: Idle
            <div className="flex flex-col items-center gap-3">
              <span className="text-3xl">🎙️</span>
              <p className="text-sm text-slate-300 font-medium">Ready to record</p>
              {permissionDenied && (
                <p className="text-xs text-rose-400 text-center max-w-xs mt-1">
                  Microphone access denied. Please enable it in your browser settings.
                </p>
              )}
              <button
                type="button"
                onClick={startRecording}
                disabled={disabled || permissionDenied}
                className="mt-2 px-6 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-500 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                🔴 Start Recording
              </button>
            </div>
          )}
        </div>
      )}

      {/* Validation / Error messages */}
      {combinedError && (
        <p id="audio-error" role="alert" className="text-xs text-rose-400">
          ⚠ {combinedError}
        </p>
      )}

      {/* Hidden file input for Upload Tab */}
      <input
        ref={inputRef}
        type="file"
        accept="audio/*,.mp3,.wav,.m4a"
        onChange={handleInputChange}
        disabled={disabled}
        className="hidden"
        aria-hidden="true"
      />
    </div>
  );
}
