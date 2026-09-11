import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

type Visibility = "private" | "team" | "shared"

type DocumentItem = {
  id: number
  title: string

  owner: {
    id: number
    username: string
  }

  department: {
    id: number
    name: string
  } | null

  visibility: Visibility
  original_filename: string
  file_size: number | null
  created_at: string | null
  updated_at: string | null
}

type DashboardData = {
  my_documents: number
  shared_documents: number
  team_documents: number
  recent_documents: DocumentItem[]
}

type DashboardResponse = {
  data: DashboardData
}

function VisibilityBadge({
  visibility,
}: {
  visibility: Visibility
}) {
  const labels: Record<Visibility, string> = {
    private: "비공개",
    team: "팀 공개",
    shared: "공유",
  }

  return (
    <Badge variant="outline">
      {labels[visibility] ?? visibility}
    </Badge>
  )
}

function formatDate(date: string | null) {
  if (!date) {
    return "-"
  }

  const parsed = new Date(date)

  if (Number.isNaN(parsed.getTime())) {
    return "-"
  }

  return parsed.toLocaleDateString("ko-KR")
}

function clearAuth() {
  localStorage.removeItem("sharehub_token")
  localStorage.removeItem("sharehub_user")
  localStorage.removeItem("sharehub_expires_at")
}

export default function DashboardPage() {
  const navigate = useNavigate()

  const [dashboard, setDashboard] =
    useState<DashboardData | null>(null)

  const [isLoading, setIsLoading] =
    useState(true)

  const [errorMessage, setErrorMessage] =
    useState("")

  useEffect(() => {
    const token =
      localStorage.getItem("sharehub_token")

    if (!token) {
      navigate("/login")
      return
    }

    const loadDashboard = async () => {
      try {
        const response = await fetch(
          "/api/dashboard",
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          },
        )

        if (response.status === 401) {
          clearAuth()
          navigate("/login")
          return
        }

        if (!response.ok) {
          setErrorMessage(
            "대시보드 정보를 불러오지 못했습니다.",
          )
          return
        }

        const data: DashboardResponse =
          await response.json()

        setDashboard(data.data)
      } catch (error) {
        console.error(
          "failed to load dashboard:",
          error,
        )

        setErrorMessage(
          "서버와 통신할 수 없습니다. 잠시 후 다시 시도해주세요.",
        )
      } finally {
        setIsLoading(false)
      }
    }

    loadDashboard()
  }, [navigate])

  if (isLoading) {
    return (
      <div className="py-20 text-center text-sm text-gray-500">
        대시보드 정보를 불러오는 중입니다.
      </div>
    )
  }

  if (errorMessage) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3">
        <p className="text-sm text-red-700">
          {errorMessage}
        </p>
      </div>
    )
  }

  if (!dashboard) {
    return null
  }

  return (
    <div className="space-y-6">
      {/* 제목 */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">
          대시보드
        </h2>

        <p className="mt-1 text-sm text-gray-500">
          ShareHub의 자료 현황을 확인할 수 있습니다.
        </p>
      </div>

      {/* 통계 카드 */}
      <div className="grid gap-4 md:grid-cols-3">
        {/* 내 자료 */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              내 자료
            </CardTitle>
          </CardHeader>

          <CardContent>
            <p className="text-3xl font-bold text-gray-900">
              {dashboard.my_documents}
            </p>

            <p className="mt-1 text-xs text-gray-500">
              내가 등록한 자료
            </p>
          </CardContent>
        </Card>

        {/* 공유받은 자료 */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              공유받은 자료
            </CardTitle>
          </CardHeader>

          <CardContent>
            <p className="text-3xl font-bold text-gray-900">
              {dashboard.shared_documents}
            </p>

            <p className="mt-1 text-xs text-gray-500">
              다른 사용자가 공유한 자료
            </p>
          </CardContent>
        </Card>

        {/* 팀 자료 */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              팀 자료
            </CardTitle>
          </CardHeader>

          <CardContent>
            <p className="text-3xl font-bold text-gray-900">
              {dashboard.team_documents}
            </p>

            <p className="mt-1 text-xs text-gray-500">
              소속 부서에서 공유 중인 자료
            </p>
          </CardContent>
        </Card>
      </div>

      {/* 최근 자료 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">
            최근 자료
          </CardTitle>
        </CardHeader>

        <CardContent>
          {dashboard.recent_documents.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>자료명</TableHead>
                  <TableHead>소유자</TableHead>
                  <TableHead>부서</TableHead>
                  <TableHead>공개 범위</TableHead>
                  <TableHead>수정일</TableHead>
                </TableRow>
              </TableHeader>

              <TableBody>
                {dashboard.recent_documents.map(
                  (document) => (
                    <TableRow
                      key={document.id}
                      className="cursor-pointer"
                      onClick={() =>
                        navigate(
                          `/documents/${document.id}`,
                        )
                      }
                    >
                      <TableCell className="font-medium">
                        {document.title}
                      </TableCell>

                      <TableCell>
                        {document.owner.username}
                      </TableCell>

                      <TableCell>
                        {document.department?.name ??
                          "-"}
                      </TableCell>

                      <TableCell>
                        <VisibilityBadge
                          visibility={
                            document.visibility
                          }
                        />
                      </TableCell>

                      <TableCell>
                        {formatDate(
                          document.updated_at,
                        )}
                      </TableCell>
                    </TableRow>
                  ),
                )}
              </TableBody>
            </Table>
          ) : (
            <div className="py-10 text-center">
              <p className="text-sm text-gray-500">
                최근 자료가 없습니다.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}