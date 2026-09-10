import { useState } from "react"
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

type CommentItem = {
  id: number
  username: string
  content: string
  createdAt: string
}

type DocumentDetail = {
  id: number
  title: string
  owner: string
  department: string
  visibility: Visibility
  fileName: string
  fileSize: string
  createdAt: string
  updatedAt: string
}

const document: DocumentDetail = {
  id: 1,
  title: "2026 보안 운영 가이드",
  owner: "이주원",
  department: "정보보안팀",
  visibility: "team",
  fileName: "security-operation-guide-2026.pdf",
  fileSize: "2.4 MB",
  createdAt: "2026-09-08 14:20",
  updatedAt: "2026-09-10 10:32",
}

const initialComments: CommentItem[] = [
  {
    id: 1,
    username: "박수현",
    content: "네트워크 보안 부분 확인했습니다.",
    createdAt: "2026-09-10 11:20",
  },
  {
    id: 2,
    username: "admin",
    content: "최신 버전으로 업데이트된 자료입니다.",
    createdAt: "2026-09-10 13:45",
  },
]

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

  return <Badge variant="outline">{labels[visibility]}</Badge>
}

export default function DocumentDetailPage() {
  const [comment, setComment] = useState("")
  const [comments, setComments] =
    useState<CommentItem[]>(initialComments)

  const handleCommentSubmit = (
    event: React.FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault()

    const content = comment.trim()

    if (!content) {
      return
    }

    // TODO: POST /api/documents/:id/comments 연결 예정
    const newComment: CommentItem = {
      id: Date.now(),
      username: "현재 사용자",
      content,
      createdAt: new Date().toLocaleString("ko-KR"),
    }

    setComments((current) => [...current, newComment])
    setComment("")
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* 상단 제목 */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <h2 className="text-2xl font-bold text-gray-900">
              {document.title}
            </h2>

            <VisibilityBadge visibility={document.visibility} />
          </div>

          <p className="text-sm text-gray-500">
            문서 번호 #{document.id}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline">
            공유
          </Button>

          <Button type="button" variant="outline">
            수정
          </Button>

          <Button type="button" variant="outline">
            삭제
          </Button>
        </div>
      </div>

      {/* 문서 기본 정보 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">
            문서 정보
          </CardTitle>

          <CardDescription>
            등록된 문서의 기본 정보입니다.
          </CardDescription>
        </CardHeader>

        <CardContent>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <p className="text-xs font-medium text-gray-500">
                소유자
              </p>
              <p className="mt-1 text-sm font-medium text-gray-900">
                {document.owner}
              </p>
            </div>

            <div>
              <p className="text-xs font-medium text-gray-500">
                부서
              </p>
              <p className="mt-1 text-sm font-medium text-gray-900">
                {document.department}
              </p>
            </div>

            <div>
              <p className="text-xs font-medium text-gray-500">
                등록일
              </p>
              <p className="mt-1 text-sm font-medium text-gray-900">
                {document.createdAt}
              </p>
            </div>

            <div>
              <p className="text-xs font-medium text-gray-500">
                수정일
              </p>
              <p className="mt-1 text-sm font-medium text-gray-900">
                {document.updatedAt}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 파일 */}
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
                {document.fileName}
              </p>

              <p className="mt-1 text-xs text-gray-500">
                {document.fileSize}
              </p>
            </div>

            <Button
              type="button"
              className="bg-[#0F6E56] text-white hover:bg-[#0C5B47]"
            >
              다운로드
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 댓글 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">
            댓글
          </CardTitle>

          <CardDescription>
            문서에 대한 의견을 남길 수 있습니다.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          <div className="space-y-4">
            {comments.length > 0 ? (
              comments.map((item, index) => (
                <div key={item.id}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-gray-900">
                        {item.username}
                      </p>

                      <p className="mt-2 whitespace-pre-wrap break-words text-sm text-gray-700">
                        {item.content}
                      </p>
                    </div>

                    <span className="shrink-0 text-xs text-gray-400">
                      {item.createdAt}
                    </span>
                  </div>

                  {index !== comments.length - 1 && (
                    <Separator className="mt-4" />
                  )}
                </div>
              ))
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
            onSubmit={handleCommentSubmit}
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
                setComment(event.target.value)
              }
              rows={4}
              placeholder="댓글을 입력하세요"
              className="w-full resize-none rounded-md border border-gray-200 bg-white px-3 py-2 text-sm outline-none transition placeholder:text-gray-400 focus:border-[#0F6E56] focus:ring-2 focus:ring-[#0F6E56]/10"
            />

            <div className="flex justify-end">
              <Button
                type="submit"
                disabled={!comment.trim()}
                className="bg-[#0F6E56] text-white hover:bg-[#0C5B47]"
              >
                댓글 등록
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}