import { useMemo, useState } from "react"
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

type DocumentItem = {
  id: number
  title: string
  department: string
  visibility: Visibility
  fileSize: string
  updatedAt: string
}

const documents: DocumentItem[] = [
  {
    id: 1,
    title: "2026 보안 운영 가이드",
    department: "정보보안팀",
    visibility: "team",
    fileSize: "2.4 MB",
    updatedAt: "2026-09-10",
  },
  {
    id: 2,
    title: "클라우드 취약점 진단 결과",
    department: "인프라팀",
    visibility: "private",
    fileSize: "1.8 MB",
    updatedAt: "2026-09-09",
  },
  {
    id: 3,
    title: "개인정보 처리 지침",
    department: "정보보안팀",
    visibility: "shared",
    fileSize: "860 KB",
    updatedAt: "2026-09-07",
  },
  {
    id: 4,
    title: "Wazuh 탐지 정책 정리",
    department: "SOC팀",
    visibility: "team",
    fileSize: "3.1 MB",
    updatedAt: "2026-09-05",
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

export default function MyDocumentsPage() {
  const [keyword, setKeyword] = useState("")
  const [visibility, setVisibility] = useState<"all" | Visibility>("all")

  const filteredDocuments = useMemo(() => {
    return documents.filter((document) => {
      const matchesKeyword = document.title
        .toLowerCase()
        .includes(keyword.toLowerCase())

      const matchesVisibility =
        visibility === "all" || document.visibility === visibility

      return matchesKeyword && matchesVisibility
    })
  }, [keyword, visibility])

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
                onChange={(event) => setKeyword(event.target.value)}
                placeholder="자료명을 검색하세요"
              />
            </div>

            <select
              value={visibility}
              onChange={(event) =>
                setVisibility(
                  event.target.value as "all" | Visibility,
                )
              }
              className="h-9 rounded-md border border-gray-200 bg-white px-3 text-sm outline-none focus:border-[#0F6E56] focus:ring-2 focus:ring-[#0F6E56]/10"
            >
              <option value="all">전체 공개 범위</option>
              <option value="private">비공개</option>
              <option value="team">팀 공개</option>
              <option value="shared">공유</option>
            </select>
          </div>
        </CardContent>
      </Card>

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
                <TableHead>부서</TableHead>
                <TableHead>공개 범위</TableHead>
                <TableHead>파일 크기</TableHead>
                <TableHead>수정일</TableHead>
                <TableHead className="text-right">관리</TableHead>
              </TableRow>
            </TableHeader>

            <TableBody>
              {filteredDocuments.length > 0 ? (
                filteredDocuments.map((document) => (
                  <TableRow key={document.id}>
                    <TableCell className="font-medium">
                      {document.title}
                    </TableCell>

                    <TableCell>
                      {document.department}
                    </TableCell>

                    <TableCell>
                      <VisibilityBadge
                        visibility={document.visibility}
                      />
                    </TableCell>

                    <TableCell>
                      {document.fileSize}
                    </TableCell>

                    <TableCell>
                      {document.updatedAt}
                    </TableCell>

                    <TableCell className="text-right">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                      >
                        상세보기
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={6}
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