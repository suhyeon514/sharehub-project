import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
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
 * 관리자  ·  /admin  ·  User · Document · ActivityLog
 *
 * 운영자가 사용자·문서·로그를 관리하는 화면.
 * - 역할 변경 / 문서 강제 삭제 / 로그 상세 조회
 * - 주의: 관리자 권한 남용·에스컬레이션 취약점의 핵심 화면.
 *         모든 액션은 ActivityLog(action_type=ADMIN_ACTION)에 반드시 기록.
 */

type ManagedUser = {
  id: number
  name: string
  department: string
  role: "user" | "admin"
  active: boolean
}

type ManagedDoc = {
  id: number
  filename: string
  owner: string
  visibility: "private" | "team" | "shared"
}

type LogEntry = {
  id: number
  at: string
  user: string
  action: string
  target: string
  ip: string
}

// TODO: API 연동 시 GET /api/admin/users · /documents · /activity-logs 로 교체
const MOCK_USERS: ManagedUser[] = [
  { id: 1, name: "김주원", department: "개발팀", role: "admin", active: true },
  { id: 2, name: "이수현", department: "개발팀", role: "user", active: true },
  { id: 3, name: "최민지", department: "인사팀", role: "user", active: true },
  { id: 4, name: "정하윤", department: "영업팀", role: "user", active: false },
]

const MOCK_DOCS: ManagedDoc[] = [
  { id: 201, filename: "서비스 아키텍처 개요.pdf", owner: "김주원", visibility: "team" },
  { id: 302, filename: "사내 자료공유 정책 개정안.docx", owner: "최민지", visibility: "shared" },
  { id: 104, filename: "온보딩 체크리스트.docx", owner: "김주원", visibility: "private" },
]

const MOCK_LOGS: LogEntry[] = [
  { id: 1, at: "2026-09-10 09:12:04", user: "이수현", action: "LOGIN_SUCCESS", target: "-", ip: "10.0.4.21" },
  { id: 2, at: "2026-09-10 09:15:33", user: "이수현", action: "DOCUMENT_DOWNLOAD", target: "doc#201", ip: "10.0.4.21" },
  { id: 3, at: "2026-09-10 09:20:10", user: "정하윤", action: "AUTHORIZATION_DENIED", target: "doc#104", ip: "10.0.7.8" },
  { id: 4, at: "2026-09-10 09:24:41", user: "김주원", action: "ADMIN_ACTION", target: "user#4 role→user", ip: "10.0.1.2" },
]

const VISIBILITY_LABEL: Record<ManagedDoc["visibility"], string> = {
  private: "개인",
  team: "팀",
  shared: "공유",
}

export default function AdminPage() {
  return (
    <div>
      <header className="mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-gray-900">관리자</h1>
          <code className="rounded border border-gray-200 bg-gray-50 px-2 py-0.5 font-mono text-xs text-gray-500">
            /admin
          </code>
        </div>
        <p className="mt-1.5 max-w-xl text-sm text-gray-500">
          사용자, 문서, 활동 로그를 관리합니다. admin 역할만 접근할 수 있으며 모든 조치는 감사 로그에 기록됩니다.
        </p>
      </header>

      <Tabs defaultValue="users">
        <TabsList>
          <TabsTrigger value="users">사용자</TabsTrigger>
          <TabsTrigger value="documents">문서</TabsTrigger>
          <TabsTrigger value="logs">활동 로그</TabsTrigger>
        </TabsList>

        {/* 사용자 */}
        <TabsContent value="users">
          <div className="rounded-lg border border-gray-200 bg-white">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>이름</TableHead>
                  <TableHead className="w-28">부서</TableHead>
                  <TableHead className="w-24">역할</TableHead>
                  <TableHead className="w-24">상태</TableHead>
                  <TableHead className="w-32 text-right">액션</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {MOCK_USERS.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell className="font-medium text-gray-900">{u.name}</TableCell>
                    <TableCell className="text-gray-600">{u.department}</TableCell>
                    <TableCell>
                      <Badge variant={u.role === "admin" ? "default" : "outline"}>
                        {u.role}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={u.active ? "secondary" : "destructive"}>
                        {u.active ? "활성" : "비활성"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="outline" size="xs" disabled>
                        역할 변경
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        {/* 문서 */}
        <TabsContent value="documents">
          <div className="rounded-lg border border-gray-200 bg-white">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>파일명</TableHead>
                  <TableHead className="w-28">소유자</TableHead>
                  <TableHead className="w-24">공개범위</TableHead>
                  <TableHead className="w-32 text-right">액션</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {MOCK_DOCS.map((d) => (
                  <TableRow key={d.id}>
                    <TableCell className="font-medium text-gray-900">{d.filename}</TableCell>
                    <TableCell className="text-gray-600">{d.owner}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{VISIBILITY_LABEL[d.visibility]}</Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="xs" className="text-red-600" disabled>
                        강제 삭제
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        {/* 활동 로그 */}
        <TabsContent value="logs">
          <div className="rounded-lg border border-gray-200 bg-white">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-44">시각</TableHead>
                  <TableHead className="w-24">사용자</TableHead>
                  <TableHead className="w-48">액션</TableHead>
                  <TableHead>대상</TableHead>
                  <TableHead className="w-32">IP</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {MOCK_LOGS.map((log) => (
                  // TODO: 행 클릭 → 로그 상세(detail, request_id) 조회
                  <TableRow key={log.id} className="cursor-pointer">
                    <TableCell className="font-mono text-xs text-gray-600">{log.at}</TableCell>
                    <TableCell className="text-gray-600">{log.user}</TableCell>
                    <TableCell>
                      <span className="font-mono text-xs text-gray-700">{log.action}</span>
                    </TableCell>
                    <TableCell className="text-gray-600">{log.target}</TableCell>
                    <TableCell className="font-mono text-xs text-gray-500">{log.ip}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
