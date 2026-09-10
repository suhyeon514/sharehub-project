import { BrowserRouter, Route, Routes } from "react-router-dom"

import ProtectedRoute from "@/components/auth/ProtectedRoute"
import AppLayout from "@/components/layout/AppLayout"

import DashboardPage from "@/pages/a/DashboardPage"
import DocumentDetailPage from "@/pages/a/DocumentDetailPage"
import LoginPage from "@/pages/a/LoginPage"
import MyDocumentsPage from "@/pages/a/MyDocumentsPage"
import UploadPage from "@/pages/a/UploadPage"

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 로그인 페이지 */}
        <Route
          path="/login"
          element={<LoginPage />}
        />

        {/* 로그인 필요 */}
        <Route
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route
            path="/"
            element={<DashboardPage />}
          />

          <Route
            path="/documents/mine"
            element={<MyDocumentsPage />}
          />

          <Route
            path="/documents/upload"
            element={<UploadPage />}
          />

          <Route
            path="/documents/:id"
            element={<DocumentDetailPage />}
          />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App