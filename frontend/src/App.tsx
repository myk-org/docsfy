import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'sonner'
import LoginPage from '@/pages/LoginPage'
import DashboardPage from '@/pages/DashboardPage'
import ModalProvider from '@/components/shared/ModalProvider'
import { useTheme } from '@/lib/useTheme'

function App() {
  const { theme } = useTheme()

  return (
    <BrowserRouter>
      <ModalProvider>
        <Toaster position="top-right" closeButton theme={theme} />
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
