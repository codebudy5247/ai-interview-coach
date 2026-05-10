# MP3 Audio Player on Feedback Page Plan (via ImageKit)

This plan outlines the changes needed to display an audio player alongside the user's transcript on the Feedback page, utilizing **ImageKit.io** as the cloud storage provider for the audio files.

## Proposed Changes

### Configuration & Dependencies

#### [MODIFY] `backend/requirements.txt`
- Add `imagekitio` to the list of required packages.

#### [MODIFY] `.env.example` & `.env`
- Add ImageKit environment variables:
  ```env
  IMAGEKIT_PUBLIC_KEY=your_public_key
  IMAGEKIT_PRIVATE_KEY=your_private_key
  IMAGEKIT_URL_ENDPOINT=your_url_endpoint
  ```

### Backend Modifications

#### [NEW] `backend/services/imagekit_service.py`
- Create a new service file to initialize the ImageKit client using the `.env` variables.
- Add an `upload_audio(file_path: str, file_name: str) -> str` function that uploads the local MP3 file to ImageKit and returns the generated URL.
- Add a `delete_audio(file_id: str)` function to remove the audio from ImageKit when a session is deleted.

#### [MODIFY] `backend/models/session_model.py`
- Add a new column to the `InterviewSession` model to store the ImageKit URL and file ID (or just store it inside the `feedback_json` to avoid database migrations). For this plan, we will append an `audio_url` to the `feedback_json` dictionary that gets saved in the database.

#### [MODIFY] `backend/routers/analyze.py`
- **Pipeline Update:** In the `_run_pipeline()` function, after transcribing the local temporary MP3, call `imagekit_service.upload_audio()` to upload the file to ImageKit. This will return an `audio_url` and an `imagekit_file_id`.
- **Error Handling (Rollback):** If the AI pipeline fails *after* the ImageKit upload (e.g., Gemini API failure), catch the exception in the `except` block and use the `imagekit_file_id` to immediately delete the orphaned file from ImageKit via `imagekit_service.delete_audio()`.
- Add the returned ImageKit `audio_url` into the `feedback` dictionary before saving it to the database so it's persisted in `feedback_json`.
- The `finally` block that calls `delete_temp(session_id)` will remain untouched! We still want to delete the local temporary MP3 after the pipeline finishes (whether it succeeds or fails).

#### [MODIFY] `backend/routers/sessions.py` (Cleanup)
- In the `DELETE /api/sessions/{session_id}` route, add a step to also delete the audio file from ImageKit via its API so we don't leave orphaned files on the CDN.

---

### Frontend Modifications

#### [MODIFY] `frontend/src/types/api.ts`
- Update the `FeedbackResponse` interface to include the optional `audio_url?: string` property.

#### [MODIFY] `frontend/src/components/FeedbackReport.tsx`
- **UI Update:** Within the `<Section id="section-transcript" title="Your Transcript">`, read the `audio_url` from the feedback prop and render an HTML5 `<audio>` player:
  ```tsx
  {feedback.audio_url && (
    <audio 
      controls 
      src={feedback.audio_url} 
      className="w-full mb-4" 
    />
  )}
  ```

## Implementation Phases

### Phase 1: ImageKit Integration (Backend)
- Add `imagekitio` to `requirements.txt`.
- Add credentials to `.env` and `.env.example`.
- Create `backend/services/imagekit_service.py` with the upload and delete functions.

### Phase 2: AI Pipeline & Error Handling (Backend)
- Update `_run_pipeline()` in `backend/routers/analyze.py` to upload the MP3 after transcription.
- Implement the rollback strategy in the `except` block to delete orphaned files if the AI generation fails.
- Attach `audio_url` and `imagekit_file_id` to the `feedback_json` saved in the database.

### Phase 3: Cleanup & Session Deletion (Backend)
- Update `DELETE /api/sessions/{session_id}` in `backend/routers/sessions.py` to extract `imagekit_file_id` from the stored `feedback_json` and delete the remote file.

### Phase 4: Audio Player (Frontend)
- Update `FeedbackResponse` interface in `types/api.ts`.
- Update `FeedbackReport.tsx` to conditionally render the `<audio>` element if `audio_url` is present in the feedback object.

## Verification Plan

### Manual Verification
1. **Upload & Analyze**: Set up ImageKit credentials in your `.env` file, upload a test MP3 file, and wait for the pipeline to finish.
2. **Playback**: Navigate to the feedback page and verify that the HTML5 audio player renders correctly in the Transcript section using the remote ImageKit URL. Hit "Play" and confirm the correct audio plays.
3. **Local Cleanup Check**: Verify that the local `temp/` folder is empty after the pipeline finishes (meaning the file was uploaded and successfully cleaned up locally).
4. **Cloud Cleanup**: Go to the History page, delete the session, and verify that the corresponding MP3 file is removed from your ImageKit Media Library dashboard.
