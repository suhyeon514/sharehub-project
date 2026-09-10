import { useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

/**
 * 공유받은 자료  ·  /documents/shared  ·  DocumentShare
 *
 * 다른 사용자가 나에게 공유한 문서 목록.
 * - 행 클릭 → 자료 상세 (권한 범위 내에서만 열람)
 * - 주의: 권한이 "조회"인데 다운로드 버튼이 활성화되면 Authorization 결함.
 *         프론트가 백엔드 응답의 permission 필드를 그대로 신뢰하는지 확인 필요.
 */

type Permission = "view" | "download" | "edit"

type SharedDoc = {
  id: number
  title: string
  sharedBy: string
  permission: Permission
  sharedAt: string
}

// TODO: API 연동 시 GET /api/documents/shared 응답으로 교체
const MOCK_SHARED: SharedDoc[] = [
  { id: 101, title: "2026 상반기 사업계획서.pdf", sharedBy: "김주원", permission: "view", sharedAt: "2026-09-01" },
  { id: 102, title: "디자인 시스템 가이드.fig", sharedBy: "이수현", permission: "edit", sharedAt: "2026-09-03" },
  { id: 103, title: "월간 지표 리포트.xlsx", sharedBy: "박서준", permission: "download", sharedAt: "2026-09-05" },
  { id: 104, title: "온보딩 체크리스트.docx", sharedBy: "김주원", permission: "view", sharedAt: "2026-09-08" },
]

const PERMISSION_LABEL: Record<Permission, string> = {
  view: "조회",
  download: "다운로드",
  edit: "편집",
}

function PermissionBadge({ permission }: { permission: Permission }) {
  const variant =
    permission === "edit"
      ? "default"
      : permission === "download"
        ? "secondary"
        : "outline"
  return <Badge variant={variant}>{PERMISSION_LABEL[permission]}</Badge>
}

export default function SharedDocumentsPage() {
  const [keyword, setKeyword] = useState("")
  const [sharerFilter, setSharerFilter] = useState("")
  const [permissionFilter, setPermissionFilter] = useState<"" | Permission>("")

  const rows = MOCK_SHARED.filter((doc) => {
    if (keyword && !doc.title.includes(keyword)) return false
    if (sharerFilter && !doc.sharedBy.includes(sharerFilter)) return false
    if (permissionFilter && doc.permission !== permissionFilter) return false
    return true
  })

  return (
    <div>
      <header className="mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-gray-900">공유받은 자료</h1>
          <code className="rounded border border-gray-200 bg-gray-50 px-2 py-0.5 font-mono text-xs text-gray-500">
            /documents/shared
          </code>
        </div>
        <p className="mt-1.5 max-w-xl text-sm text-gray-500">
          다른 사용자가 나에게 공유한 문서 목록입니다. 부여받은 권한 범위 안에서만 열람할 수 있습니다.
        </p>
      </header>

      {/* 검색 · 필터 */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Input
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="제목 검색"
          className="h-9 w-full max-w-xs"
        />
        <Input
          value={sharerFilter}
          onChange={(e) => setSharerFilter(e.target.value)}
          placeholder="공유자"
          className="h-9 w-40"
        />
        <select
          value={permissionFilter}
          onChange={(e) => setPermissionFilter(e.target.value as "" | Permission)}
          className="h-9 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <option value="">권한 전체</option>
          <option value="view">조회</option>
          <option value="download">다운로드</option>
          <option value="edit">편집</option>
        </select>
      </div>

      {/* 목록 */}
      <div className="rounded-lg border border-gray-200 bg-white">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>제목</TableHead>
              <TableHead className="w-32">공유자</TableHead>
              <TableHead className="w-28">권한</TableHead>
              <TableHead className="w-32">공유일</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((doc) => (
              // TODO: 라우팅 연결 후 onClick → navigate(`/documents/${doc.id}`)
              <TableRow key={doc.id} className="cursor-pointer">
                <TableCell className="font-medium text-gray-900">{doc.title}</TableCell>
                <TableCell className="text-gray-600">{doc.sharedBy}</TableCell>
                <TableCell>
                  <PermissionBadge permission={doc.permission} />
                </TableCell>
                <TableCell className="text-gray-600">{doc.sharedAt}</TableCell>
              </TableRow>
            ))}
            {rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="py-10 text-center text-sm text-gray-500">
                  조건에 맞는 공유 자료가 없습니다.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="mt-4 flex justify-end">
        <Button variant="outline" size="sm" disabled>
          더 보기
        </Button>
      </div>
    </div>
  )
}
