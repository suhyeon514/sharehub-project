import type { ReactNode } from "react"
import { Navigate, useLocation } from "react-router-dom"

type ProtectedRouteProps = {
  children: ReactNode
}

export default function ProtectedRoute({
  children,
}: ProtectedRouteProps) {
  const location = useLocation()

  const token = localStorage.getItem("sharehub_token")
  const expiresAt = localStorage.getItem("sharehub_expires_at")

  const isExpired = (() => {
    if (!expiresAt) {
      return true
    }

    const expiresTime = new Date(expiresAt).getTime()

    if (Number.isNaN(expiresTime)) {
      return true
    }

    return Date.now() >= expiresTime
  })()

  if (!token || isExpired) {
    localStorage.removeItem("sharehub_token")
    localStorage.removeItem("sharehub_user")
    localStorage.removeItem("sharehub_expires_at")

    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location.pathname }}
      />
    )
  }

  return <>{children}</>
}
