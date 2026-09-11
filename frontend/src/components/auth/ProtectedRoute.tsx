import { useEffect, useSyncExternalStore } from "react"
import type { ReactNode } from "react"
import { Navigate, useLocation } from "react-router-dom"

type ProtectedRouteProps = { children: ReactNode }

// 외부 상태인 저장된 세션과 시각을 React의 구독 방식으로 확인한다.
function hasValidSession() {
  const token = localStorage.getItem("sharehub_token")
  const expiresAt = localStorage.getItem("sharehub_expires_at")
  const expiresTime = expiresAt ? new Date(expiresAt).getTime() : NaN
  return Boolean(token) && Number.isFinite(expiresTime) && Date.now() < expiresTime
}

function subscribeSession(onChange: () => void) {
  const timer = window.setInterval(onChange, 1000)
  window.addEventListener("storage", onChange)
  window.addEventListener("focus", onChange)
  return () => {
    window.clearInterval(timer)
    window.removeEventListener("storage", onChange)
    window.removeEventListener("focus", onChange)
  }
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const location = useLocation()
  const valid = useSyncExternalStore(subscribeSession, hasValidSession, () => false)

  useEffect(() => {
    if (!valid && !hasValidSession()) {
      localStorage.removeItem("sharehub_token")
      localStorage.removeItem("sharehub_user")
      localStorage.removeItem("sharehub_expires_at")
    }
  }, [valid])

  if (!valid) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  return <>{children}</>
}
