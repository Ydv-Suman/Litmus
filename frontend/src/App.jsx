import { Route, Routes } from 'react-router-dom'

import ApplyPage from './pages/ApplyPage'
import HomePage from './pages/HomePage'
import HrPage from './pages/HrPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/apply" element={<ApplyPage />} />
      <Route path="/hr" element={<HrPage />} />
    </Routes>
  )
}

export default App
