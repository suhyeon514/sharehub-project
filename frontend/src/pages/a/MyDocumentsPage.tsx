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

type UnblockRequestStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "cancelled"

type UnblockRequest = {
  id: number
  status: UnblockRequestStatus
  requested_at: string | null
  review_comment: string | null
}

type BlockedDocumentItem = {
  document_id: number
  block_id: number
  title: string
  status: "blocked" | "unblocked"
  block_reason: string
  blocked_at: string | null
  unblock_request: UnblockRequest | null
}

type BlockedDocumentsResponse = {
  data: BlockedDocumentItem[]
}

type ApiErrorResponse = {
  error?: {
    code?: string
    message?: string
  }
}

function clearAuth() {
  localStorage.removeItem("sharehub_token")
  localStorage.removeItem("sharehub_user")
  localStorage.removeItem("sharehub_expires_at")
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

  return parsedDate.toLocaleString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export default function MyDocumentsPage() {
  const navigate = useNavigate()

  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [keyword, setKeyword] = useState("")
  const [visibility, setVisibility] =
    useState<"all" | Visibility>("all")

  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState("")

  const [blockedDocuments, setBlockedDocuments] =
    useState<BlockedDocumentItem[]>([])
  const [blockedLoading, setBlockedLoading] = useState(true)

  const [selectedBlock, setSelectedBlock] =
    useState<BlockedDocumentItem | null>(null)
  const [appealReason, setAppealReason] = useState("")
  const [appealSubmitting, setAppealSubmitting] =
    useState(false)
  const [appealMessage, setAppealMessage] = useState("")

  const fetchBlockedDocuments = async () => {
    const token = localStorage.getItem("sharehub_token")

    if (!token) {
      navigate("/login")
      return
    }

    try {

      const response = await fetch(
        "/api/my/blocked-documents",
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

      const data:
        | BlockedDocumentsResponse
        | ApiErrorResponse
        | null = await response.json().catch(() => null)

      if (!response.ok) {
        const errorData = data as ApiErrorResponse | null

        setAppealMessage(
          errorData?.error?.message ??
            "이용 제한 자료를 불러오지 못했습니다.",
        )
        return
      }

      setBlockedDocuments(
        (data as BlockedDocumentsResponse).data ?? [],
      )
    } catch (error) {
      console.error(
        "failed to load blocked documents:",
        error,
      )

      setAppealMessage(
        "이용 제한 자료를 불러오지 못했습니다.",
      )
    } finally {
      setBlockedLoading(false)
    }
  }

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
          clearAuth()
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
        console.error(
          "failed to load documents:",
          error,
        )

        setErrorMessage(
          "서버와 통신할 수 없습니다. 잠시 후 다시 시도해주세요.",
        )
      } finally {
        setIsLoading(false)
      }
    }

    fetchDocuments()
  }, [navigate])

  useEffect(() => {
  let cancelled = false

  const loadBlockedDocuments = async () => {
    const token =
      localStorage.getItem("sharehub_token")

    if (!token) {
      navigate("/login")
      return
    }

    try {
      const response = await fetch(
        "/api/my/blocked-documents",
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      )

      if (cancelled) {
        return
      }

      if (response.status === 401) {
        clearAuth()
        navigate("/login")
        return
      }

      const data:
        | BlockedDocumentsResponse
        | ApiErrorResponse
        | null = await response
        .json()
        .catch(() => null)

      if (cancelled) {
        return
      }

      if (!response.ok) {
        const errorData =
          data as ApiErrorResponse | null

        setAppealMessage(
          errorData?.error?.message ??
            "이용 제한 자료를 불러오지 못했습니다.",
        )
        return
      }

      setBlockedDocuments(
        (data as BlockedDocumentsResponse).data ??
          [],
      )
    } catch (error) {
      if (cancelled) {
        return
      }

      console.error(
        "failed to load blocked documents:",
        error,
      )

      setAppealMessage(
        "이용 제한 자료를 불러오지 못했습니다.",
      )
    } finally {
      if (!cancelled) {
        setBlockedLoading(false)
      }
    }
  }

  void loadBlockedDocuments()

  return () => {
    cancelled = true
  }
}, [navigate])

  const submitAppeal = async () => {
    if (!selectedBlock) {
      return
    }

    const reason = appealReason.trim()

    if (!reason) {
      setAppealMessage("소명 사유를 입력해주세요.")
      return
    }

    const token = localStorage.getItem("sharehub_token")

    if (!token) {
      navigate("/login")
      return
    }

    try {
      setAppealSubmitting(true)
      setAppealMessage("")

      const response = await fetch(
        `/api/document-blocks/${selectedBlock.block_id}/unblock-requests`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            reason,
          }),
        },
      )

      if (response.status === 401) {
        clearAuth()
        navigate("/login")
        return
      }

      const data: ApiErrorResponse | null =
        await response.json().catch(() => null)

      if (!response.ok) {
        const code = data?.error?.code

        if (code === "EMPTY_REASON") {
          setAppealMessage(
            "소명 사유를 입력해주세요.",
          )
          return
        }

        if (
          code ===
          "UNBLOCK_REQUEST_ALREADY_PENDING"
        ) {
          setAppealMessage(
            "이미 검토 대기 중인 소명 요청이 있습니다.",
          )

          setSelectedBlock(null)
          setAppealReason("")
          await fetchBlockedDocuments()
          return
        }

        setAppealMessage(
          data?.error?.message ??
            "소명 신청에 실패했습니다.",
        )
        return
      }

      setSelectedBlock(null)
      setAppealReason("")
      setAppealMessage(
        "소명 요청이 등록되었습니다.",
      )

      await fetchBlockedDocuments()
    } catch (error) {
      console.error(
        "failed to submit appeal:",
        error,
      )

      setAppealMessage(
        "소명 신청 중 오류가 발생했습니다.",
      )
    } finally {
      setAppealSubmitting(false)
    }
  }

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

      {/* 일반 자료 오류 */}
      {errorMessage && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm text-red-700">
            {errorMessage}
          </p>
        </div>
      )}

      {/* 이용 제한 자료 */}
      <Card className="overflow-hidden">
        <CardHeader className="border-b bg-gray-50/50">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-lg">
                이용 제한 자료

                {!blockedLoading &&
                  blockedDocuments.length > 0 && (
                    <span className="rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold text-red-700">
                      {blockedDocuments.length}건
                    </span>
                  )}
              </CardTitle>

              <p className="mt-1 text-sm text-gray-500">
                관리자에 의해 이용이 제한된 내 자료입니다.
              </p>
            </div>
          </div>
        </CardHeader>

        <CardContent className="pt-6">
          {appealMessage && (
            <div className="mb-4 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
              <p className="text-sm text-gray-700">
                {appealMessage}
              </p>
            </div>
          )}

          {blockedLoading ? (
            <div className="py-8 text-center text-sm text-gray-500">
              이용 제한 자료를 불러오는 중입니다.
            </div>
          ) : blockedDocuments.length === 0 ? (
            <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-6 py-10 text-center">
              <p className="text-sm text-gray-500">
                현재 이용이 제한된 자료가 없습니다.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {blockedDocuments.map((item) => {
                const request = item.unblock_request

                const canAppeal =
                  item.status === "blocked" &&
                  (!request ||
                    request.status === "rejected" ||
                    request.status === "cancelled")

                return (
                  <div
                    key={item.block_id}
                    className="overflow-hidden rounded-xl border border-red-100 bg-white"
                  >
                    <div className="border-b border-red-100 bg-red-50/50 px-5 py-4">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <div className="mb-2 flex flex-wrap items-center gap-2">
                            <Badge
                              variant="outline"
                              className="border-red-200 bg-red-100 text-red-700"
                            >
                              이용 제한
                            </Badge>

                            {request?.status ===
                              "pending" && (
                              <Badge
                                variant="outline"
                                className="border-amber-200 bg-amber-100 text-amber-700"
                              >
                                검토 대기
                              </Badge>
                            )}

                            {request?.status ===
                              "rejected" && (
                              <Badge
                                variant="outline"
                                className="border-gray-200 bg-gray-100 text-gray-700"
                              >
                                반려
                              </Badge>
                            )}

                            {request?.status ===
                              "approved" && (
                              <Badge
                                variant="outline"
                                className="border-emerald-200 bg-emerald-100 text-emerald-700"
                              >
                                승인
                              </Badge>
                            )}

                            {request?.status ===
                              "cancelled" && (
                              <Badge
                                variant="outline"
                                className="border-gray-200 bg-gray-100 text-gray-700"
                              >
                                요청 취소
                              </Badge>
                            )}
                          </div>

                          <h3 className="text-base font-semibold text-gray-900">
                            {item.title}
                          </h3>

                          <p className="mt-1 text-xs text-gray-500">
                            문서 #{item.document_id}
                          </p>
                        </div>

                        {canAppeal && (
                          <Button
                            type="button"
                            onClick={() => {
                              setSelectedBlock(item)
                              setAppealReason("")
                              setAppealMessage("")
                            }}
                            className="shrink-0 bg-[#0F6E56] text-white hover:bg-[#0C5B47]"
                          >
                            {request?.status ===
                            "rejected"
                              ? "다시 소명 신청"
                              : "소명 신청"}
                          </Button>
                        )}
                      </div>
                    </div>

                    <div className="space-y-4 px-5 py-5">
                      <div>
                        <p className="mb-1.5 text-xs font-medium text-gray-500">
                          제한 사유
                        </p>

                        <div className="rounded-lg bg-gray-50 px-4 py-3">
                          <p className="whitespace-pre-wrap text-sm leading-6 text-gray-700">
                            {item.block_reason ||
                              "차단 사유가 제공되지 않았습니다."}
                          </p>
                        </div>
                      </div>

                      <div className="text-sm">
                        <span className="text-gray-500">
                          제한 일시
                        </span>

                        <span className="ml-2 font-medium text-gray-700">
                          {formatDate(item.blocked_at)}
                        </span>
                      </div>

                      {request?.status ===
                        "pending" && (
                        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-4">
                          <p className="text-sm font-semibold text-amber-800">
                            소명 요청을 검토하고 있습니다.
                          </p>

                          <p className="mt-1 text-sm text-amber-700">
                            {formatDate(
                              request.requested_at,
                            )}
                            에 소명 요청이
                            접수되었습니다.
                          </p>

                          <p className="mt-2 text-xs text-amber-700">
                            검토가 완료되기 전에는
                            추가 소명 요청을 제출할 수
                            없습니다.
                          </p>
                        </div>
                      )}

                      {request?.status ===
                        "rejected" && (
                        <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-4">
                          <p className="text-sm font-semibold text-gray-800">
                            이전 소명 요청이
                            반려되었습니다.
                          </p>

                          {request.review_comment && (
                            <>
                              <p className="mt-3 text-xs font-medium text-gray-500">
                                관리자 검토 의견
                              </p>

                              <p className="mt-1 whitespace-pre-wrap text-sm text-gray-700">
                                {
                                  request.review_comment
                                }
                              </p>
                            </>
                          )}

                          <p className="mt-2 text-xs text-gray-500">
                            내용을 보완해 다시 소명을
                            신청할 수 있습니다.
                          </p>
                        </div>
                      )}

                      {request?.status ===
                        "cancelled" && (
                        <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-4">
                          <p className="text-sm font-semibold text-gray-800">
                            이전 소명 요청이
                            취소되었습니다.
                          </p>

                          <p className="mt-2 text-xs text-gray-500">
                            필요한 경우 다시 소명을
                            신청할 수 있습니다.
                          </p>
                        </div>
                      )}

                      {request?.status ===
                        "approved" && (
                        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-4">
                          <p className="text-sm font-semibold text-emerald-800">
                            소명 요청이 승인되었습니다.
                          </p>

                          {request.review_comment && (
                            <p className="mt-2 text-sm text-emerald-700">
                              {
                                request.review_comment
                              }
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 소명 신청 */}
      {selectedBlock && (
        <Card className="border-[#0F6E56]/20">
          <CardHeader>
            <CardTitle className="text-lg">
              소명 신청
            </CardTitle>

            <p className="text-sm text-gray-500">
              이용 제한에 대해 관리자가 검토할 수 있도록
              소명 내용을 작성해주세요.
            </p>
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="rounded-lg bg-gray-50 px-4 py-3">
              <p className="text-xs font-medium text-gray-500">
                대상 자료
              </p>

              <p className="mt-1 text-sm font-semibold text-gray-900">
                {selectedBlock.title}
              </p>

              <p className="mt-3 text-xs font-medium text-gray-500">
                제한 사유
              </p>

              <p className="mt-1 whitespace-pre-wrap text-sm text-gray-700">
                {selectedBlock.block_reason}
              </p>
            </div>

            <div>
              <label
                htmlFor="appeal-reason"
                className="mb-2 block text-sm font-medium text-gray-800"
              >
                소명 내용
              </label>

              <textarea
                id="appeal-reason"
                value={appealReason}
                onChange={(event) =>
                  setAppealReason(event.target.value)
                }
                rows={5}
                disabled={appealSubmitting}
                placeholder="이용 제한 해제가 필요한 사유를 입력해주세요."
                className="w-full resize-none rounded-lg border border-gray-200 bg-white px-3 py-3 text-sm leading-6 outline-none transition placeholder:text-gray-400 focus:border-[#0F6E56] focus:ring-2 focus:ring-[#0F6E56]/10 disabled:cursor-not-allowed disabled:bg-gray-50"
              />
            </div>

            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={appealSubmitting}
                onClick={() => {
                  setSelectedBlock(null)
                  setAppealReason("")
                  setAppealMessage("")
                }}
              >
                취소
              </Button>

              <Button
                type="button"
                disabled={
                  appealSubmitting ||
                  !appealReason.trim()
                }
                onClick={submitAppeal}
                className="bg-[#0F6E56] text-white hover:bg-[#0C5B47]"
              >
                {appealSubmitting
                  ? "제출 중..."
                  : selectedBlock.unblock_request
                        ?.status === "rejected"
                    ? "다시 소명 요청"
                    : "소명 요청 제출"}
              </Button>
            </div>
          </CardContent>
        </Card>
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
