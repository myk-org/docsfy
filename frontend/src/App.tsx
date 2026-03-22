import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'sonner'
import LoginPage from '@/pages/LoginPage'
import DashboardPage from '@/pages/DashboardPage'
import ModalProvider from '@/components/shared/ModalProvider'

function App() {
  return (
    <BrowserRouter>
      <ModalProvider>
        <Toaster position="top-right" closeButton />
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<DashboardPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </ModalProvider>
    </BrowserRouter>
  )
}

export default App
