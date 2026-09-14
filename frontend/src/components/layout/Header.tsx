import { useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"

type StoredUser = {
  id: number
  username: string
  role: string
  department_id: number | null
}

export default function Header() {
  const navigate = useNavigate()

  const rawUser = localStorage.getItem("sharehub_user")

  let user: StoredUser | null = null

  if (rawUser) {
    try {
      user = JSON.parse(rawUser) as StoredUser
    } catch {
      user = null
    }
  }

  const handleLogout = async () => {
    const token = localStorage.getItem("sharehub_token")

    try {
      if (token) {
        await fetch("/api/auth/logout", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        })
      }
    } catch (error) {
      console.error("Logout error:", error)
    } finally {
      localStorage.removeItem("sharehub_token")
      localStorage.removeItem("sharehub_user")
      localStorage.removeItem("sharehub_expires_at")

      navigate("/login", { replace: true })
    }
  }

  const displayName = user?.username ?? "사용자"

  const displayRole =
    user?.role === "admin"
      ? "관리자"
      : user?.role === "user"
        ? "일반 사용자"
        : user?.role ?? ""

  const avatarText =
    displayName.charAt(0).toUpperCase()

  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-gray-200 bg-white px-6">
      {/* 검색 영역 */}
      <div className="w-full max-w-md">
        <div className="relative">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400"
            aria-hidden="true"
          >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>

          <input
            type="search"
            placeholder="자료 또는 사용자 검색"
            className="h-10 w-full rounded-lg border border-gray-200 bg-gray-50 pl-10 pr-4 text-sm outline-none transition focus:border-[#0F6E56] focus:bg-white focus:ring-2 focus:ring-[#0F6E56]/10"
          />
        </div>
      </div>

      {/* 사용자 영역 */}
      <div className="ml-6 flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#0F6E56] text-sm font-semibold text-white">
          {avatarText}
        </div>

        <div className="hidden sm:block">
          <p className="text-sm font-medium text-gray-800">
            {displayName}
          </p>

          <p className="text-xs text-gray-500">
            {displayRole}
          </p>
        </div>

        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleLogout}
          className="ml-2"
        >
          로그아웃
        </Button>
      </div>
    </header>
  )
}