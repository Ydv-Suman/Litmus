import { Navigate, Route, Routes } from 'react-router-dom'

import ApplyPage from './pages/ApplyPage'
import HomePage from './pages/HomePage'
import HrLoginPage from './pages/HrLoginPage'
import HrSignupPage from './pages/HrSignupPage'
import HrDashboardPage from './pages/HrDashboardPage'
import ApplicantDetailPage from './pages/ApplicantDetailPage'
import AssessmentPage from './pages/AssessmentPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/apply" element={<ApplyPage />} />
      <Route path="/assessment/:token" element={<AssessmentPage />} />
      <Route path="/hr" element={<Navigate to="/hr/login" replace />} />
      <Route path="/hr/login" element={<HrLoginPage />} />
      <Route path="/hr/signup" element={<HrSignupPage />} />
      <Route path="/hr/dashboard" element={<HrDashboardPage />} />
      <Route path="/hr/:userId/applicants/:applicationId" element={<ApplicantDetailPage />} />
    </Routes>
  )
}

export default App
