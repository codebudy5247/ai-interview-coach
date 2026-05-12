# 🎙️ In-Browser Recording — Implementation Plan

> **Goal:** Let users record their interview answer directly in the browser using their microphone, in addition to the existing MP3 file upload. Both input methods feed into the same pipeline.

---

## Current State

- Users can **only upload a pre-recorded MP3 file** via the `AudioUploader` component (drag & drop / click to browse).
- The backend accepts MP3 files via `POST /api/analyze` (`audio: UploadFile`).
- Whisper transcription uses FFmpeg under the hood, which supports **any audio format** (MP3, WAV, WebM, OGG, etc.) — not just MP3.
- The `AudioUploader` component validates for `.mp3` / `audio/mpeg` MIME types.

---

## Key Design Decision

> **Record as WebM → send as WebM → Whisper handles it natively.**
>
> The browser's `MediaRecorder` API records as **WebM/Opus** (Chrome/Edge/Firefox) or **MP4/AAC** (Safari) by default. Since Whisper accepts any FFmpeg-supported format, there's **no need to transcode to MP3 in the browser**. This avoids:
> - Heavy WebAssembly MP3 encoding libraries (~500KB+)
> - Encoding delays after recording
> - Web Worker complexity
>
> We simply send the raw recording blob to the backend as-is.

---

## User Review Required

> [!IMPORTANT]
> **No MP3 transcoding in browser**
> The recording will be sent as WebM (or MP4 on Safari) directly to the backend. Whisper handles both formats perfectly. This keeps the frontend lightweight. The backend's file validation will be loosened to accept `audio/*` MIME types instead of MP3-only. Please confirm this approach is acceptable.

> [!IMPORTANT]
> **UI approach: Tabs within AudioUploader**
> The plan replaces the current upload-only drop zone with a **tabbed component** — "Upload MP3" tab (existing flow) and "Record" tab (new mic recording flow). Both tabs produce a `File` object and feed into the same `onFileChange` prop. This keeps changes contained to one component.

---

## Open Questions

1. **Max recording duration**: Should we cap recording at a time limit (e.g., 10 minutes)? Long recordings = large files + slow transcription. Plan assumes a 10-minute soft limit with a visible timer. No, let users record as long as they want. 
2. **Playback before submit**: Should users be able to listen to their recording before submitting? (Plan assumes yes — a small audio player appears after recording.) Yes 
3. **Re-record**: Allow users to discard and re-record? (Plan assumes yes.) No - this is not needed. 

---

## Proposed Changes

### Frontend — AudioUploader Refactor

#### [MODIFY] [AudioUploader.tsx](file:///Users/ujjwal/Desktop/code/interview-coach/frontend/src/components/AudioUploader.tsx)

This is the **main change**. Refactor the component into a tabbed UI with two modes:

**Tab 1 — "Upload" (existing behavior)**
- Same drag & drop / click to browse flow
- Accepts `.mp3` files (unchanged)

**Tab 2 — "Record" (new)**
- "Start Recording" button → requests mic permission → starts `MediaRecorder`
- Live recording indicator: pulsing red dot + elapsed timer (`00:00`, `00:01`, ...)
- "Stop Recording" button → stops `MediaRecorder` → creates a `File` from the blob
- After stopping: shows playback player + "Re-record" and "Use this recording" actions
- Auto-stops at 10-minute limit

**Implementation details:**

```typescript
// Core recording hook logic (inside AudioUploader or extracted to useAudioRecorder)
const [mode, setMode] = useState<'upload' | 'record'>('upload')
const [recording, setRecording] = useState(false)
const [audioBlob, setAudioBlob] = useState<Blob | null>(null)
const [duration, setDuration] = useState(0)       // seconds elapsed
const mediaRecorderRef = useRef<MediaRecorder | null>(null)
const chunksRef = useRef<Blob[]>([])
const timerRef = useRef<number | null>(null)

async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true })

  // Prefer webm/opus, fall back to whatever the browser supports
  const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
    ? 'audio/webm;codecs=opus'
    : MediaRecorder.isTypeSupported('audio/mp4')
    ? 'audio/mp4'
    : ''  // browser default

  const recorder = new MediaRecorder(stream, { mimeType: mimeType || undefined })
  chunksRef.current = []

  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunksRef.current.push(e.data)
  }

  recorder.onstop = () => {
    const blob = new Blob(chunksRef.current, { type: recorder.mimeType })
    setAudioBlob(blob)
    // Convert blob to File object so it works with the existing onFileChange prop
    const ext = blob.type.includes('mp4') ? 'mp4' : 'webm'
    const file = new File([blob], `recording.${ext}`, { type: blob.type })
    onFileChange(file)
    // Stop all mic tracks
    stream.getTracks().forEach(t => t.stop())
  }

  recorder.start(1000)  // collect chunks every 1s
  mediaRecorderRef.current = recorder
  setRecording(true)
  setDuration(0)
  // Start timer
  timerRef.current = window.setInterval(() => {
    setDuration(d => {
      if (d >= 600) { stopRecording(); return d }  // 10 min limit
      return d + 1
    })
  }, 1000)
}

function stopRecording() {
  mediaRecorderRef.current?.stop()
  setRecording(false)
  if (timerRef.current) clearInterval(timerRef.current)
}
```

**UI wireframe for "Record" tab:**

```
┌──────────────────────────────────────────┐
│  Your Answer                             │
│  ┌─────────────┬─────────────┐           │
│  │  📁 Upload  │  🎙️ Record  │  ← tabs   │
│  └─────────────┴─────────────┘           │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │                                    │  │
│  │     🎙️  Ready to record            │  │
│  │                                    │  │
│  │     [ 🔴 Start Recording ]         │  │
│  │                                    │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘

── Recording state ──
┌────────────────────────────────────────┐
│  🔴 Recording...  02:34 / 10:00       │
│                                        │
│  ██████████░░░░░░░░░░  (progress bar)  │
│                                        │
│  [ ⏹️ Stop Recording ]                 │
└────────────────────────────────────────┘

── After recording ──
┌────────────────────────────────────────┐
│  ✅ Recording complete — 2:34          │
│                                        │
│  ▶ ━━━━━━━━━━━━━━━━━━━━ 2:34          │
│    (native <audio> player)             │
│                                        │
│  [ 🔄 Re-record ]  [ ✅ Use this ]     │
└────────────────────────────────────────┘
```

---

#### [NEW] [useAudioRecorder.ts](file:///Users/ujjwal/Desktop/code/interview-coach/frontend/src/hooks/useAudioRecorder.ts)

Custom React hook that encapsulates all `MediaRecorder` logic:

```typescript
interface UseAudioRecorderReturn {
  // State
  recording: boolean
  duration: number           // seconds elapsed
  audioBlob: Blob | null
  audioUrl: string | null    // object URL for <audio> playback
  error: string | null
  permissionDenied: boolean

  // Actions
  startRecording: () => Promise<void>
  stopRecording: () => void
  resetRecording: () => void  // discard and allow re-record
}

export function useAudioRecorder(maxDurationSec = 600): UseAudioRecorderReturn
```

Benefits of extracting to a hook:
- Keeps `AudioUploader` clean and focused on UI
- Handles cleanup (stop tracks, revoke object URLs) in hook's `useEffect` return
- Testable in isolation
- Handles mic permission errors gracefully

---

### Backend — Accept Multiple Audio Formats

#### [MODIFY] [file_handler.py](file:///Users/ujjwal/Desktop/code/interview-coach/backend/utils/file_handler.py)

Loosen the file validation to accept any audio format that FFmpeg/Whisper supports:

```diff
-async def save_upload(file: UploadFile, session_id: str) -> Path:
+async def save_upload(file: UploadFile, session_id: str) -> Path:
     filename = file.filename or ""
     content_type = file.content_type or ""
+
+    # Accepted audio formats (anything FFmpeg/Whisper can handle)
+    ACCEPTED_EXTENSIONS = {".mp3", ".wav", ".webm", ".ogg", ".mp4", ".m4a", ".flac"}
+    ACCEPTED_MIMES = {"audio/mpeg", "audio/mp3", "audio/wav", "audio/webm",
+                      "audio/ogg", "audio/mp4", "audio/x-m4a", "audio/flac"}
+
+    ext = os.path.splitext(filename)[1].lower()
+    is_valid = ext in ACCEPTED_EXTENSIONS or content_type in ACCEPTED_MIMES
-    if not (
-        filename.lower().endswith(".mp3")
-        or "audio/mpeg" in content_type
-        or "audio/mp3" in content_type
-    ):
+    if not is_valid:
         raise HTTPException(
             status_code=400,
-            detail="Only MP3 audio files are accepted.",
+            detail=f"Unsupported audio format. Accepted: MP3, WAV, WebM, OGG, MP4, M4A, FLAC.",
         )

-    dest = TEMP_DIR / f"{session_id}.mp3"
+    # Preserve original extension so FFmpeg can detect the container format
+    save_ext = ext if ext in ACCEPTED_EXTENSIONS else ".webm"
+    dest = TEMP_DIR / f"{session_id}{save_ext}"
     with dest.open("wb") as out:
         shutil.copyfileobj(file.file, out)
     return dest
```

---

#### [MODIFY] [file_handler.py](file:///Users/ujjwal/Desktop/code/interview-coach/backend/utils/file_handler.py) — `delete_temp()`

Update to handle any extension (not just `.mp3`):

```diff
 def delete_temp(session_id: str) -> None:
-    path = TEMP_DIR / f"{session_id}.mp3"
-    try:
-        path.unlink(missing_ok=True)
-    except Exception:
-        pass
+    """Remove the temporary audio file for a session (any extension)."""
+    import glob
+    for path in TEMP_DIR.glob(f"{session_id}.*"):
+        try:
+            path.unlink(missing_ok=True)
+        except Exception:
+            pass
```

---

#### [MODIFY] [whisper_service.py](file:///Users/ujjwal/Desktop/code/interview-coach/backend/services/whisper_service.py)

Rename the parameter and docstring to reflect that it's no longer MP3-only:

```diff
-def transcribe(mp3_path: str) -> str:
+def transcribe(audio_path: str) -> str:
     """
-    Transcribe the audio file at `mp3_path` and return the transcript string.
+    Transcribe the audio file at `audio_path` and return the transcript string.
+    Supports any format FFmpeg can decode (MP3, WAV, WebM, OGG, MP4, etc.).
     """
```

---

#### [MODIFY] [analyze.py](file:///Users/ujjwal/Desktop/code/interview-coach/backend/routers/analyze.py)

Update the session dict key name and reference:

```diff
-    _sessions[session_id] = {
-        "mp3_path": str(mp3_path),
+    _sessions[session_id] = {
+        "audio_path": str(mp3_path),  # now supports any audio format
```

And in `_run_pipeline()`:

```diff
-    mp3_path = session["mp3_path"]
+    audio_path = session["audio_path"]
     ...
-    transcript = transcribe(mp3_path)
+    transcript = transcribe(audio_path)
```

---

### Frontend — Minor Adjustments

#### [MODIFY] [AudioUploader.tsx](file:///Users/ujjwal/Desktop/code/interview-coach/frontend/src/components/AudioUploader.tsx) — Validation

When in "Upload" mode, keep MP3-only validation. The recording tab produces WebM/MP4 which bypasses file validation entirely (it's created programmatically, not uploaded by the user).

```diff
-    if (
-      !f.name.toLowerCase().endsWith(".mp3") &&
-      f.type !== "audio/mpeg" &&
-      f.type !== "audio/mp3"
-    ) {
-      return "Only MP3 files are accepted.";
-    }
+    // In upload mode, accept common audio formats
+    const validExts = ['.mp3', '.wav', '.m4a', '.ogg', '.webm', '.flac']
+    const validMimes = ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/webm', 'audio/ogg', 'audio/mp4', 'audio/x-m4a', 'audio/flac']
+    const ext = f.name.toLowerCase().slice(f.name.lastIndexOf('.'))
+    if (!validExts.includes(ext) && !validMimes.includes(f.type)) {
+      return "Unsupported format. Accepted: MP3, WAV, M4A, OGG, WebM, FLAC."
+    }
```

#### [MODIFY] [UploadPage.tsx](file:///Users/ujjwal/Desktop/code/interview-coach/frontend/src/pages/UploadPage.tsx)

Update the label from "Your Answer (MP3)" to "Your Answer (Audio)" since we now accept multiple formats.

---

## File Summary

| Action   | File                                       | Description                                         |
|----------|--------------------------------------------|-----------------------------------------------------|
| **NEW**  | `frontend/src/hooks/useAudioRecorder.ts`   | Custom hook: MediaRecorder + timer + cleanup         |
| MODIFY   | `frontend/src/components/AudioUploader.tsx` | Add tabbed UI (Upload / Record), integrate hook      |
| MODIFY   | `backend/utils/file_handler.py`            | Accept `audio/*` formats, dynamic file extension     |
| MODIFY   | `backend/services/whisper_service.py`      | Rename param `mp3_path` → `audio_path`               |
| MODIFY   | `backend/routers/analyze.py`               | Update session key `mp3_path` → `audio_path`         |
| MODIFY   | `frontend/src/pages/UploadPage.tsx`        | Update label to "Your Answer (Audio)"                |

---

## Build Phases

### Phase 1 — Backend: Multi-Format Support
- [x] Update `file_handler.py` — accept `audio/*` formats, preserve file extension
- [x] Update `delete_temp()` — glob-based cleanup for any extension
- [x] Update `whisper_service.py` — rename `mp3_path` → `audio_path`
- [x] Update `analyze.py` — rename session key to `audio_path`
- [x] Test: upload a `.webm` file via curl → verify Whisper transcribes it correctly

### Phase 2 — Frontend: useAudioRecorder Hook
- [ ] Create `frontend/src/hooks/useAudioRecorder.ts`
- [ ] Implement `startRecording()`, `stopRecording()`, `resetRecording()`
- [ ] Handle mic permission denied error
- [ ] Auto-stop at max duration (10 min)
- [ ] Cleanup: stop tracks + revoke object URLs on unmount

### Phase 3 — Frontend: AudioUploader Refactor
- [ ] Add tab UI (Upload / Record) to `AudioUploader.tsx`
- [ ] "Upload" tab: existing drag & drop (loosen to accept all audio formats)
- [ ] "Record" tab: integrate `useAudioRecorder` hook
- [ ] Recording states: idle → recording (red dot + timer) → done (playback + re-record)
- [ ] Both tabs produce a `File` object via the same `onFileChange` prop
- [ ] Update `UploadPage.tsx` label

### Phase 4 — Polish & Edge Cases
- [ ] Mic permission denied → clear error message + instructions
- [ ] Browser compatibility: test Chrome, Firefox, Safari
- [ ] Recording too short (< 1s) → show warning
- [ ] Responsive layout for the tabbed UI
- [ ] Smooth transitions between recording states

---

## Verification Plan

### Automated Tests
- Backend: `curl -F "audio=@test.webm" -F "question=test" /api/analyze` → verify pipeline works with WebM
- Backend: repeat with `.ogg`, `.wav` files to confirm multi-format support
- Backend: upload a non-audio file → verify 400 rejection

### Browser Tests
- Open app → switch to "Record" tab → click "Start Recording" → speak → click "Stop"
- Verify playback works in the mini player
- Click "Re-record" → verify previous recording is discarded
- Click "Use this recording" → submit → verify pipeline processes it
- Test mic permission denied flow (block mic in browser settings)

### Manual Verification
- Test on Chrome, Firefox, Safari
- Verify no audio glitches or gaps in recording
- Verify timer accuracy
- Verify 10-minute auto-stop works
