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

const recentDocuments = [
  {
    id: 1,
    title: "2026 보안 운영 가이드",
    owner: "이주원",
    department: "정보보안팀",
    visibility: "team",
    updatedAt: "2026-09-10",
  },
  {
    id: 2,
    title: "사내 개인정보 처리 지침",
    owner: "박수현",
    department: "정보보안팀",
    visibility: "shared",
    updatedAt: "2026-09-09",
  },
  {
    id: 3,
    title: "클라우드 취약점 진단 결과",
    owner: "이주원",
    department: "인프라팀",
    visibility: "private",
    updatedAt: "2026-09-08",
  },
]

function VisibilityBadge({
  visibility,
}: {
  visibility: "private" | "team" | "shared"
}) {
  const label = {
    private: "비공개",
    team: "팀 공개",
    shared: "공유",
  }

  return <Badge variant="outline">{label[visibility]}</Badge>
}

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">대시보드</h2>
        <p className="mt-1 text-sm text-gray-500">
          ShareHub의 자료 현황을 확인할 수 있습니다.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              내 자료
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-gray-900">12</p>
            <p className="mt-1 text-xs text-gray-500">
              내가 등록한 자료
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              공유받은 자료
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-gray-900">8</p>
            <p className="mt-1 text-xs text-gray-500">
              다른 사용자가 공유한 자료
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              팀 자료
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-gray-900">24</p>
            <p className="mt-1 text-xs text-gray-500">
              소속 부서에서 공유 중인 자료
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">최근 자료</CardTitle>
        </CardHeader>

        <CardContent>
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
              {recentDocuments.map((document) => (
                <TableRow key={document.id}>
                  <TableCell className="font-medium">
                    {document.title}
                  </TableCell>
                  <TableCell>{document.owner}</TableCell>
                  <TableCell>{document.department}</TableCell>
                  <TableCell>
                    <VisibilityBadge
                      visibility={
                        document.visibility as
                          | "private"
                          | "team"
                          | "shared"
                      }
                    />
                  </TableCell>
                  <TableCell>{document.updatedAt}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}