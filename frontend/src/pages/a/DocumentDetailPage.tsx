import { useEffect, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"

type Visibility = "private" | "team" | "shared"
type Permission = "view" | "download" | "edit"

type DocumentDetail = {
  id: number
  title: string
  description: string | null

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
  content_type: string | null
  created_at: string | null
  updated_at: string | null

  access: {
    source: "owner" | "team" | "share"
    permission: Permission
  }
}

type DocumentResponse = {
  data: DocumentDetail
}

type CommentItem = {
  id: number
  content: string

  user: {
    id: number
    username: string
  }

  created_at: string | null
}

type CommentsResponse = {
  data: CommentItem[]
}

/* =========================
   공개 범위 Badge
========================= */

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

/* =========================
   파일 크기 표시
========================= */

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

/* =========================
   날짜 표시
========================= */

function formatDate(date: string | null) {
  if (!date) {
    return "-"
  }

  const parsed = new Date(date)

  if (Number.isNaN(parsed.getTime())) {
    return "-"
  }

  return parsed.toLocaleString("ko-KR")
}

/* =========================
   로그인 정보 제거
========================= */

function clearAuth() {
  localStorage.removeItem("sharehub_token")
  localStorage.removeItem("sharehub_user")
  localStorage.removeItem("sharehub_expires_at")
}

/* =========================
   Document Detail Page
========================= */

export default function DocumentDetailPage() {
  const navigate = useNavigate()
  const { id } = useParams()

  const documentId = Number(id)

  const hasValidId =
    Boolean(id) &&
    Number.isInteger(documentId) &&
    documentId > 0

  const [document, setDocument] =
    useState<DocumentDetail | null>(null)

  const [comments, setComments] =
    useState<CommentItem[]>([])

  const [comment, setComment] = useState("")

  const [isLoading, setIsLoading] = useState(true)

  const [
    isCommentSubmitting,
    setIsCommentSubmitting,
  ] = useState(false)

  const [isDownloading, setIsDownloading] =
    useState(false)

  const [errorMessage, setErrorMessage] =
    useState("")

  const [commentError, setCommentError] =
    useState("")

  /* =========================
     문서 상세 + 댓글 조회
  ========================= */

  useEffect(() => {
    if (!hasValidId) {
      return
    }

    const token =
      localStorage.getItem("sharehub_token")

    if (!token) {
      navigate("/login")
      return
    }

    const loadDocument = async () => {
      try {
        const [
          documentResponse,
          commentsResponse,
        ] = await Promise.all([
          fetch(
            `/api/documents/${documentId}`,
            {
              headers: {
                Authorization: `Bearer ${token}`,
              },
            },
          ),

          fetch(
            `/api/documents/${documentId}/comments`,
            {
              headers: {
                Authorization: `Bearer ${token}`,
              },
            },
          ),
        ])

        /* 인증 만료 */
        if (
          documentResponse.status === 401 ||
          commentsResponse.status === 401
        ) {
          clearAuth()
          navigate("/login")
          return
        }

        /* 문서 없음 */
        if (documentResponse.status === 404) {
          setErrorMessage(
            "문서를 찾을 수 없습니다.",
          )
          return
        }

        /* 문서 접근 권한 없음 */
        if (documentResponse.status === 403) {
          const errorData = await documentResponse
            .json()
            .catch(() => null)

          if (
            errorData?.error?.code ===
            "DOCUMENT_BLOCKED"
          ) {
            setErrorMessage(
              "관리자에 의해 이용이 제한된 문서입니다. 내 자료에서 소명 신청 상태를 확인할 수 있습니다.",
            )
            return
          }

          setErrorMessage(
            "이 문서를 조회할 권한이 없습니다.",
          )
          return
        }

        /* 기타 오류 */
        if (!documentResponse.ok) {
          setErrorMessage(
            "문서 정보를 불러오지 못했습니다.",
          )
          return
        }

        const documentData: DocumentResponse =
          await documentResponse.json()

        setDocument(documentData.data)

        /* 댓글은 문서와 별도로 처리 */
        if (commentsResponse.ok) {
          const commentsData: CommentsResponse =
            await commentsResponse.json()

          setComments(
            commentsData.data ?? [],
          )
        }
      } catch (error) {
        console.error(
          "failed to load document:",
          error,
        )

        setErrorMessage(
          "서버와 통신할 수 없습니다. 잠시 후 다시 시도해주세요.",
        )
      } finally {
        setIsLoading(false)
      }
    }

    loadDocument()
  }, [documentId, hasValidId, navigate])

  /* =========================
     파일 다운로드
  ========================= */

  const handleDownload = async () => {
    if (!document || !hasValidId) {
      return
    }

    const token =
      localStorage.getItem("sharehub_token")

    if (!token) {
      navigate("/login")
      return
    }

    try {
      setIsDownloading(true)
      setErrorMessage("")

      const response = await fetch(
        `/api/documents/${documentId}/download`,
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

      if (response.status === 403) {
        setErrorMessage(
          "이 파일을 다운로드할 권한이 없습니다.",
        )
        return
      }

      if (!response.ok) {
        const data = await response
          .json()
          .catch(() => null)

        setErrorMessage(
          data?.message ??
            "파일 다운로드에 실패했습니다.",
        )

        return
      }

      const blob = await response.blob()

      const url =
        URL.createObjectURL(blob)

      const anchor =
        window.document.createElement("a")

      anchor.href = url
      anchor.download =
        document.original_filename

      window.document.body.appendChild(
        anchor,
      )

      anchor.click()
      anchor.remove()

      URL.revokeObjectURL(url)
    } catch (error) {
      console.error(
        "download failed:",
        error,
      )

      setErrorMessage(
        "파일 다운로드 중 오류가 발생했습니다.",
      )
    } finally {
      setIsDownloading(false)
    }
  }

  /* =========================
     댓글 등록
  ========================= */

  const handleCommentSubmit = async (
    event: React.FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault()

    const content = comment.trim()

    if (!content || !hasValidId) {
      return
    }

    const token =
      localStorage.getItem("sharehub_token")

    if (!token) {
      navigate("/login")
      return
    }

    try {
      setIsCommentSubmitting(true)
      setCommentError("")

      const response = await fetch(
        `/api/documents/${documentId}/comments`,
        {
          method: "POST",

          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type":
              "application/json",
          },

          body: JSON.stringify({
            content,
          }),
        },
      )

      const data = await response
        .json()
        .catch(() => null)

      if (response.status === 401) {
        clearAuth()
        navigate("/login")
        return
      }

      if (response.status === 403) {
        setCommentError(
          "댓글을 작성할 권한이 없습니다.",
        )
        return
      }

      if (!response.ok) {
        setCommentError(
          data?.message ??
            "댓글 등록에 실패했습니다.",
        )
        return
      }

      /*
       * 서버에서 반환된 댓글을
       * 현재 댓글 목록 마지막에 추가
       */
      setComments((current) => [
        ...current,
        data.data,
      ])

      setComment("")
    } catch (error) {
      console.error(
        "comment creation failed:",
        error,
      )

      setCommentError(
        "댓글 등록 중 오류가 발생했습니다.",
      )
    } finally {
      setIsCommentSubmitting(false)
    }
  }

  /* =========================
     잘못된 문서 ID
  ========================= */

  if (!hasValidId) {
    return (
      <div className="mx-auto max-w-5xl space-y-4">
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm text-red-700">
            문서 번호가 올바르지 않습니다.
          </p>
        </div>

        <Button
          type="button"
          variant="outline"
          onClick={() =>
            navigate("/documents/mine")
          }
        >
          내 자료로 돌아가기
        </Button>
      </div>
    )
  }

  /* =========================
     로딩
  ========================= */

  if (isLoading) {
    return (
      <div className="py-20 text-center text-sm text-gray-500">
        문서 정보를 불러오는 중입니다.
      </div>
    )
  }

  /* =========================
     상세 조회 실패
  ========================= */

  if (errorMessage && !document) {
    return (
      <div className="mx-auto max-w-5xl space-y-4">
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm text-red-700">
            {errorMessage}
          </p>
        </div>

        <Button
          type="button"
          variant="outline"
          onClick={() =>
            navigate("/documents/mine")
          }
        >
          내 자료로 돌아가기
        </Button>
      </div>
    )
  }

  if (!document) {
    return null
  }

  /* =========================
     다운로드 권한
  ========================= */

  const canDownload =
    document.access.permission ===
      "download" ||
    document.access.permission === "edit"

  /* =========================
     화면
  ========================= */

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* 상단 제목 */}

      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <h2 className="text-2xl font-bold text-gray-900">
              {document.title}
            </h2>

            <VisibilityBadge
              visibility={
                document.visibility
              }
            />
          </div>

          <p className="text-sm text-gray-500">
            문서 번호 #{document.id}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {/* 공유 페이지는 팀원 담당 */}

          <Button
            type="button"
            variant="outline"
            onClick={() =>
              navigate(
                `/documents/${document.id}/share`,
              )
            }
          >
            공유
          </Button>

          {/* 수정 API는 아직 연결 전 */}

          <Button
            type="button"
            variant="outline"
            disabled={
              document.access.permission !==
              "edit"
            }
          >
            수정
          </Button>

          {/* 삭제 API는 아직 연결 전 */}

          <Button
            type="button"
            variant="outline"
            disabled={
              document.access.source !==
              "owner"
            }
          >
            삭제
          </Button>
        </div>
      </div>

      {/* 일반 오류 */}

      {errorMessage && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm text-red-700">
            {errorMessage}
          </p>
        </div>
      )}

      {/* 문서 정보 */}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">
            문서 정보
          </CardTitle>

          <CardDescription>
            등록된 문서의 기본 정보입니다.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {/* 소유자 */}

            <div>
              <p className="text-xs font-medium text-gray-500">
                소유자
              </p>

              <p className="mt-1 text-sm font-medium text-gray-900">
                {document.owner.username}
              </p>
            </div>

            {/* 부서 */}

            <div>
              <p className="text-xs font-medium text-gray-500">
                부서
              </p>

              <p className="mt-1 text-sm font-medium text-gray-900">
                {document.department?.name ??
                  "-"}
              </p>
            </div>

            {/* 등록일 */}

            <div>
              <p className="text-xs font-medium text-gray-500">
                등록일
              </p>

              <p className="mt-1 text-sm font-medium text-gray-900">
                {formatDate(
                  document.created_at,
                )}
              </p>
            </div>

            {/* 수정일 */}

            <div>
              <p className="text-xs font-medium text-gray-500">
                수정일
              </p>

              <p className="mt-1 text-sm font-medium text-gray-900">
                {formatDate(
                  document.updated_at,
                )}
              </p>
            </div>
          </div>

          {/* 설명 */}

          {document.description && (
            <>
              <Separator />

              <div>
                <p className="text-xs font-medium text-gray-500">
                  설명
                </p>

                <p className="mt-2 whitespace-pre-wrap text-sm text-gray-700">
                  {document.description}
                </p>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* 첨부 파일 */}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">
            첨부 파일
          </CardTitle>
        </CardHeader>

        <CardContent>
          <div className="flex flex-col gap-4 rounded-lg border bg-gray-50 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-gray-900">
                {document.original_filename}
              </p>

              <p className="mt-1 text-xs text-gray-500">
                {formatFileSize(
                  document.file_size,
                )}
              </p>
            </div>

            <Button
              type="button"
              disabled={
                !canDownload ||
                isDownloading
              }
              onClick={handleDownload}
              className="bg-[#0F6E56] text-white hover:bg-[#0C5B47]"
            >
              {isDownloading
                ? "다운로드 중..."
                : "다운로드"}
            </Button>
          </div>

          {!canDownload && (
            <p className="mt-2 text-xs text-gray-500">
              현재 권한에서는 파일을
              다운로드할 수 없습니다.
            </p>
          )}
        </CardContent>
      </Card>

      {/* 댓글 */}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">
            댓글

            <span className="ml-2 text-sm font-normal text-gray-500">
              {comments.length}건
            </span>
          </CardTitle>

          <CardDescription>
            문서에 대한 의견을 남길 수
            있습니다.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* 댓글 목록 */}

          <div className="space-y-4">
            {comments.length > 0 ? (
              comments.map(
                (item, index) => (
                  <div key={item.id}>
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-gray-900">
                          {
                            item.user
                              .username
                          }
                        </p>

                        <p className="mt-2 whitespace-pre-wrap break-words text-sm text-gray-700">
                          {item.content}
                        </p>
                      </div>

                      <span className="shrink-0 text-xs text-gray-400">
                        {formatDate(
                          item.created_at,
                        )}
                      </span>
                    </div>

                    {index !==
                      comments.length -
                        1 && (
                      <Separator className="mt-4" />
                    )}
                  </div>
                ),
              )
            ) : (
              <p className="py-6 text-center text-sm text-gray-500">
                등록된 댓글이 없습니다.
              </p>
            )}
          </div>

          <Separator />

          {/* 댓글 작성 */}

          <form
            className="space-y-3"
            onSubmit={
              handleCommentSubmit
            }
          >
            <label
              htmlFor="comment"
              className="text-sm font-medium text-gray-700"
            >
              댓글 작성
            </label>

            <textarea
              id="comment"
              value={comment}
              onChange={(event) =>
                setComment(
                  event.target.value,
                )
              }
              rows={4}
              maxLength={2000}
              disabled={
                isCommentSubmitting
              }
              placeholder="댓글을 입력하세요"
              className="w-full resize-none rounded-md border border-gray-200 bg-white px-3 py-2 text-sm outline-none transition placeholder:text-gray-400 focus:border-[#0F6E56] focus:ring-2 focus:ring-[#0F6E56]/10 disabled:cursor-not-allowed disabled:opacity-60"
            />

            {commentError && (
              <p className="text-sm text-red-600">
                {commentError}
              </p>
            )}

            <div className="flex justify-end">
              <Button
                type="submit"
                disabled={
                  !comment.trim() ||
                  isCommentSubmitting
                }
                className="bg-[#0F6E56] text-white hover:bg-[#0C5B47]"
              >
                {isCommentSubmitting
                  ? "등록 중..."
                  : "댓글 등록"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}