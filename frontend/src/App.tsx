import { Routes, Route } from 'react-router-dom'
import UploadPage from './pages/UploadPage'
import ProgressPage from './pages/ProgressPage'
import FeedbackPage from './pages/FeedbackPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<UploadPage />} />
      <Route path="/progress/:sessionId" element={<ProgressPage />} />
      <Route path="/feedback/:sessionId" element={<FeedbackPage />} />
    </Routes>
  )
}

export default App
