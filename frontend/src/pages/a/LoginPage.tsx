import { useState } from "react"
import type { FormEvent } from "react"
import {
  useLocation,
  useNavigate,
} from "react-router-dom"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"

type LoginResponse = {
  message: string
  token: string
  expires_at: string
  user: {
    id: number
    username: string
    role: string
    department_id: number | null
  }
}

type ErrorResponse = {
  message?: string
}

export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()

  const from =
    (location.state as { from?: string } | null)?.from ?? "/"

  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    setError("")

    if (!username.trim() || !password) {
      setError("아이디와 비밀번호를 입력해주세요.")
      return
    }

    try {
      setIsLoading(true)

      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: username.trim(),
          password,
        }),
      })

      const data = (await response.json()) as LoginResponse | ErrorResponse

      if (!response.ok) {
        setError(data.message ?? "로그인에 실패했습니다.")
        return
      }

      const loginData = data as LoginResponse

      localStorage.setItem("sharehub_token", loginData.token)
      localStorage.setItem(
        "sharehub_user",
        JSON.stringify(loginData.user),
      )
      localStorage.setItem(
        "sharehub_expires_at",
        loginData.expires_at,
      )

      navigate(from, { replace: true })
    } catch (error) {
      console.error("Login error:", error)
      setError(
        "서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.",
      )
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <Card className="w-full max-w-md shadow-sm">
        <CardHeader className="space-y-2 text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-xl bg-[#0F6E56] text-xl font-bold text-white">
            S
          </div>

          <CardTitle className="text-2xl font-bold text-gray-900">
            ShareHub
          </CardTitle>

          <CardDescription>
            사내 자료공유 서비스에 로그인하세요.
          </CardDescription>
        </CardHeader>

        <CardContent>
          <form
            className="space-y-4"
            onSubmit={handleSubmit}
          >
            <div className="space-y-2">
              <label
                htmlFor="username"
                className="text-sm font-medium text-gray-700"
              >
                아이디
              </label>

              <Input
                id="username"
                type="text"
                placeholder="아이디를 입력하세요"
                autoComplete="username"
                value={username}
                onChange={(event) =>
                  setUsername(event.target.value)
                }
                disabled={isLoading}
              />
            </div>

            <div className="space-y-2">
              <label
                htmlFor="password"
                className="text-sm font-medium text-gray-700"
              >
                비밀번호
              </label>

              <Input
                id="password"
                type="password"
                placeholder="비밀번호를 입력하세요"
                autoComplete="current-password"
                value={password}
                onChange={(event) =>
                  setPassword(event.target.value)
                }
                disabled={isLoading}
              />
            </div>

            {error && (
              <div
                className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
                role="alert"
              >
                {error}
              </div>
            )}

            <Button
              type="submit"
              disabled={isLoading}
              className="w-full bg-[#0F6E56] text-white hover:bg-[#0C5B47]"
            >
              {isLoading ? "로그인 중..." : "로그인"}
            </Button>
          </form>

          <p className="mt-6 text-center text-xs text-gray-500">
            사내 계정으로 로그인해 주세요.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}