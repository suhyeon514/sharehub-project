import { useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

type Visibility = "private" | "team" | "shared"

type Department = {
  id: number
  name: string
}

type DocumentItem = {
  id: number
  title: string
  department: Department | null
  visibility: Visibility
  original_filename: string
  file_size: number | null
  created_at: string | null
  updated_at: string | null
}

type DocumentsResponse = {
  data: DocumentItem[]
  pagination?: {
    page: number
    page_size: number
    total: number
    total_pages: number
  }
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

function formatFileSize(size: number | null) {
  if (size === null || size === undefined) {
    return "-"
  }

  if (size < 1024) {
    return `${size} B`
  }

  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`
  }

  return `${(size / 1024 / 1024).toFixed(2)} MB`
}

function formatDate(date: string | null) {
  if (!date) {
    return "-"
  }

  const parsedDate = new Date(date)

  if (Number.isNaN(parsedDate.getTime())) {
    return "-"
  }

  return parsedDate.toLocaleDateString("ko-KR")
}

export default function MyDocumentsPage() {
  const navigate = useNavigate()

  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [keyword, setKeyword] = useState("")
  const [visibility, setVisibility] =
    useState<"all" | Visibility>("all")

  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState("")

  useEffect(() => {
    const fetchDocuments = async () => {
      const token = localStorage.getItem("sharehub_token")

      if (!token) {
        navigate("/login")
        return
      }

      try {
        setIsLoading(true)
        setErrorMessage("")

        const response = await fetch(
          "/api/documents/mine?page=1&page_size=100",
          {
            method: "GET",
            headers: {
              Authorization: `Bearer ${token}`,
            },
          },
        )

        const data: DocumentsResponse | null =
          await response.json().catch(() => null)

        if (response.status === 401) {
          localStorage.removeItem("sharehub_token")
          localStorage.removeItem("sharehub_user")
          localStorage.removeItem("sharehub_expires_at")

          navigate("/login")
          return
        }

        if (!response.ok) {
          setErrorMessage(
            "내 자료 목록을 불러오지 못했습니다.",
          )
          return
        }

        setDocuments(data?.data ?? [])
      } catch (error) {
        console.error("failed to load documents:", error)

        setErrorMessage(
          "서버와 통신할 수 없습니다. 잠시 후 다시 시도해주세요.",
        )
      } finally {
        setIsLoading(false)
      }
    }

    fetchDocuments()
  }, [navigate])

  const filteredDocuments = useMemo(() => {
    return documents.filter((document) => {
      const matchesKeyword = document.title
        .toLowerCase()
        .includes(keyword.toLowerCase())

      const matchesVisibility =
        visibility === "all" ||
        document.visibility === visibility

      return matchesKeyword && matchesVisibility
    })
  }, [documents, keyword, visibility])

  return (
    <div className="space-y-6">
      {/* 페이지 제목 */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">
            내 자료
          </h2>

          <p className="mt-1 text-sm text-gray-500">
            내가 등록한 자료를 확인하고 관리할 수 있습니다.
          </p>
        </div>

        <Button
          type="button"
          onClick={() => navigate("/documents/upload")}
          className="bg-[#0F6E56] text-white hover:bg-[#0C5B47]"
        >
          자료 업로드
        </Button>
      </div>

      {/* 검색 / 필터 */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col gap-3 md:flex-row">
            <div className="flex-1">
              <Input
                type="search"
                value={keyword}
                onChange={(event) =>
                  setKeyword(event.target.value)
                }
                placeholder="자료명을 검색하세요"
              />
            </div>

            <select
              value={visibility}
              onChange={(event) =>
                setVisibility(
                  event.target.value as
                    | "all"
                    | Visibility,
                )
              }
              className="h-9 rounded-md border border-gray-200 bg-white px-3 text-sm outline-none focus:border-[#0F6E56] focus:ring-2 focus:ring-[#0F6E56]/10"
            >
              <option value="all">
                전체 공개 범위
              </option>

              <option value="private">
                비공개
              </option>

              <option value="team">
                팀 공개
              </option>

              <option value="shared">
                공유
              </option>
            </select>
          </div>
        </CardContent>
      </Card>

      {/* 에러 */}
      {errorMessage && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm text-red-700">
            {errorMessage}
          </p>
        </div>
      )}

      {/* 자료 목록 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">
            자료 목록

            <span className="ml-2 text-sm font-normal text-gray-500">
              {filteredDocuments.length}건
            </span>
          </CardTitle>
        </CardHeader>

        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>자료명</TableHead>
                <TableHead>파일명</TableHead>
                <TableHead>부서</TableHead>
                <TableHead>공개 범위</TableHead>
                <TableHead>파일 크기</TableHead>
                <TableHead>수정일</TableHead>
                <TableHead className="text-right">
                  관리
                </TableHead>
              </TableRow>
            </TableHeader>

            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="h-32 text-center text-gray-500"
                  >
                    자료를 불러오는 중입니다.
                  </TableCell>
                </TableRow>
              ) : filteredDocuments.length > 0 ? (
                filteredDocuments.map((document) => (
                  <TableRow key={document.id}>
                    <TableCell className="font-medium">
                      {document.title}
                    </TableCell>

                    <TableCell className="max-w-[220px] truncate text-gray-600">
                      {document.original_filename}
                    </TableCell>

                    <TableCell>
                      {document.department?.name ?? "-"}
                    </TableCell>

                    <TableCell>
                      <VisibilityBadge
                        visibility={
                          document.visibility
                        }
                      />
                    </TableCell>

                    <TableCell>
                      {formatFileSize(
                        document.file_size,
                      )}
                    </TableCell>

                    <TableCell>
                      {formatDate(
                        document.updated_at ??
                          document.created_at,
                      )}
                    </TableCell>

                    <TableCell className="text-right">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          navigate(
                            `/documents/${document.id}`,
                          )
                        }
                      >
                        상세보기
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="h-32 text-center text-gray-500"
                  >
                    조건에 맞는 자료가 없습니다.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}