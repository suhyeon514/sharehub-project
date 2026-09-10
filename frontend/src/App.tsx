import { BrowserRouter, Route, Routes } from "react-router-dom"

import ProtectedRoute from "@/components/auth/ProtectedRoute"
import AppLayout from "@/components/layout/AppLayout"

import DashboardPage from "@/pages/a/DashboardPage"
import DocumentDetailPage from "@/pages/a/DocumentDetailPage"
import LoginPage from "@/pages/a/LoginPage"
import MyDocumentsPage from "@/pages/a/MyDocumentsPage"
import UploadPage from "@/pages/a/UploadPage"
import AdminPage from "@/pages/b/AdminPage"
import SearchPage from "@/pages/b/SearchPage"
import SharedDocumentsPage from "@/pages/b/SharedDocumentsPage"
import SharePage from "@/pages/b/SharePage"
import TeamDocumentsPage from "@/pages/b/TeamDocumentsPage"

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

          <Route
            path="/documents/shared"
            element={<SharedDocumentsPage />}
          />

          <Route
            path="/documents/team"
            element={<TeamDocumentsPage />}
          />

          <Route
            path="/documents/:id/share"
            element={<SharePage />}
          />

          <Route
            path="/search"
            element={<SearchPage />}
          />

          <Route
            path="/admin"
            element={<AdminPage />}
          />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
