import { useState } from "react"

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

/**
 * 팀 자료  ·  /documents/team  ·  Department
 *
 * 같은 부서 구성원이 공유하는 자료 목록.
 * - 부서 탭 전환 → 목록 필터링
 * - 주의: 다른 부서 데이터가 탭 전환만으로 노출되면 안 됨.
 *         서버 측에서 부서 소속 검증 필수(URL 파라미터 조작 방어).
 */

type TeamDoc = {
  id: number
  title: string
  owner: string
  updatedAt: string
}

type Department = {
  id: string
  name: string
  documents: TeamDoc[]
}

// TODO: API 연동 시 GET /api/departments, GET /api/documents/team?department= 로 교체
const MOCK_DEPARTMENTS: Department[] = [
  {
    id: "dev",
    name: "개발팀",
    documents: [
      { id: 201, title: "서비스 아키텍처 개요.pdf", owner: "김주원", updatedAt: "2026-09-07" },
      { id: 202, title: "배포 절차 문서.md", owner: "이수현", updatedAt: "2026-09-06" },
      { id: 203, title: "API 명세서 v2.yaml", owner: "박서준", updatedAt: "2026-09-02" },
    ],
  },
  {
    id: "hr",
    name: "인사팀",
    documents: [
      { id: 211, title: "복지제도 안내.pptx", owner: "최민지", updatedAt: "2026-09-05" },
      { id: 212, title: "채용 프로세스.docx", owner: "최민지", updatedAt: "2026-08-28" },
    ],
  },
  {
    id: "sales",
    name: "영업팀",
    documents: [
      { id: 221, title: "3분기 파이프라인.xlsx", owner: "정하윤", updatedAt: "2026-09-08" },
    ],
  },
]

export default function TeamDocumentsPage() {
  const [activeDept, setActiveDept] = useState(MOCK_DEPARTMENTS[0].id)

  return (
    <div>
      <header className="mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-gray-900">팀 자료</h1>
          <code className="rounded border border-gray-200 bg-gray-50 px-2 py-0.5 font-mono text-xs text-gray-500">
            /documents/team
          </code>
        </div>
        <p className="mt-1.5 max-w-xl text-sm text-gray-500">
          내가 소속된 부서에서 공유되는 자료입니다. 부서 탭을 눌러 목록을 전환합니다.
        </p>
      </header>

      <Tabs value={activeDept} onValueChange={(v) => setActiveDept(v as string)}>
        <TabsList>
          {MOCK_DEPARTMENTS.map((dept) => (
            <TabsTrigger key={dept.id} value={dept.id}>
              {dept.name}
            </TabsTrigger>
          ))}
        </TabsList>

        {MOCK_DEPARTMENTS.map((dept) => (
          <TabsContent key={dept.id} value={dept.id}>
            <div className="rounded-lg border border-gray-200 bg-white">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>제목</TableHead>
                    <TableHead className="w-32">소유자</TableHead>
                    <TableHead className="w-32">수정일</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {dept.documents.map((doc) => (
                    // TODO: 라우팅 연결 후 onClick → navigate(`/documents/${doc.id}`)
                    <TableRow key={doc.id} className="cursor-pointer">
                      <TableCell className="font-medium text-gray-900">{doc.title}</TableCell>
                      <TableCell className="text-gray-600">{doc.owner}</TableCell>
                      <TableCell className="text-gray-600">{doc.updatedAt}</TableCell>
                    </TableRow>
                  ))}
                  {dept.documents.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={3} className="py-10 text-center text-sm text-gray-500">
                        이 부서에 등록된 자료가 없습니다.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}
