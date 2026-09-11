import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ApiError, apiGet } from "@/lib/api"

type Resource = "users" | "documents" | "activity-logs"
type Result = { items: Record<string, unknown>[]; pagination: { page: number; pages: number; total: number } }
const columns: Record<Resource, [string, string][]> = {
  users: [["username", "계정명"], ["role", "역할"], ["department", "부서"], ["created_at", "가입일"]],
  documents: [["title", "제목"], ["owner", "소유자"], ["department", "부서"], ["visibility", "공개 범위"], ["updated_at", "수정일"]],
  "activity-logs": [["username", "작업자"], ["action_type", "이벤트"], ["created_at", "기록 시각"], ["detail", "상세"]],
}
function display(value: unknown, key: string) {
  if (value === null || value === undefined) return "—"
  if (key === "detail") {
    const detail = value as Record<string, unknown>
    const operations: Record<string, string> = { create: "공유 생성", update: "권한 변경", delete: "공유 해제" }
    return [operations[String(detail.operation)], detail.document_id != null ? `문서 #${detail.document_id}` : "",
      detail.shared_with_id != null ? `수신자 #${detail.shared_with_id}` : "",
      detail.operation ? `${detail.before_permission ?? "없음"} → ${detail.after_permission ?? "없음"}` : ""].filter(Boolean).join(" · ") || "—"
  }
  return String(value).replace("T", " ")
}

export default function AdminPage() {
  const [params] = useSearchParams()
  const [attempt, setAttempt] = useState(0)
  return <AdminContent key={`${params.toString()}:${attempt}`} reload={() => setAttempt((value) => value + 1)} />
}
function AdminContent({ reload }: { reload: () => void }) {
  const [params, setParams] = useSearchParams()
  const tab = params.get("tab") ?? "users"
  const resource: Resource = tab === "documents" || tab === "activity-logs" ? tab : "users"
  const [query, setQuery] = useState(params.get("q") ?? "")
  const [data, setData] = useState<Result | null>(null)
  const [error, setError] = useState("")
  const [forbidden, setForbidden] = useState(false)
  const navigate = useNavigate()
  const search = params.toString()
  useEffect(() => {
    const controller = new AbortController()
    // 렌더 전에 서버의 현재 역할 확인. 목록 API도 별도로 관리자 권한 검사.
    async function load() {
      const me = await apiGet<{ user: { role: string } }>("/api/auth/me", controller.signal)
      if (me.user.role !== "admin") throw new ApiError(403, "관리자만 접근할 수 있습니다.")
      return apiGet<Result>(`/api/admin/${resource}?${search}`, controller.signal)
    }
    load().then((result) => { if (!controller.signal.aborted) setData(result) }).catch((reason: unknown) => {
      if (controller.signal.aborted) return
      if (reason instanceof ApiError && reason.status === 401) {
        navigate("/login", { replace: true, state: { from: `/admin?${search}` } })
      } else {
        setForbidden(reason instanceof ApiError && reason.status === 403)
        setError(reason instanceof ApiError ? reason.message : "서버에 연결할 수 없습니다.")
      }
    })
    return () => controller.abort()
  }, [resource, search, navigate])
  return <div>
    <h1 className="mb-2 text-xl font-semibold">관리자</h1>
    <p className="mb-6 text-sm text-gray-500">사용자, 문서 정보와 기록된 활동을 조회합니다.</p>
    {forbidden ? <div role="alert"><p>{error}</p><Button className="mt-3" variant="outline" onClick={() => navigate("/")}>대시보드로 이동</Button></div> : <>
      <form className="mb-4 flex flex-wrap gap-2" onSubmit={(event) => { event.preventDefault(); setParams({ tab: resource, q: query.trim(), page: "1" }); reload() }}>
        <Input className="max-w-sm" aria-label="목록 검색" maxLength={255} placeholder={resource === "users" ? "계정명 검색" : resource === "documents" ? "문서 제목 검색" : "이벤트 검색 (예: DOCUMENT_SHARE)"} value={query} onChange={(event) => setQuery(event.target.value)} />
        <Button type="submit" variant="outline">검색</Button><Button type="button" variant="ghost" onClick={() => { setParams({ tab: resource }); reload() }}>초기화</Button><Button type="button" variant="outline" onClick={reload}>새로고침</Button>
      </form>
      {error ? <div role="alert"><p className="text-red-600">{error}</p><Button variant="outline" onClick={reload}>다시 시도</Button></div> : !data ? <p role="status">조회 중입니다.</p> : <>
        <p className="mb-3 text-sm">총 {data.pagination.total}건</p>
        <div className="rounded-lg border bg-white"><Table><TableHeader><TableRow>{columns[resource].map(([key, title]) => <TableHead key={key}>{title}</TableHead>)}</TableRow></TableHeader><TableBody>
          {data.items.map((item) => <TableRow key={String(item.id)}>{columns[resource].map(([key]) => <TableCell key={key} className="whitespace-normal break-words">{display(item[key], key)}</TableCell>)}</TableRow>)}
          {!data.items.length && <TableRow><TableCell colSpan={columns[resource].length} className="py-10 text-center">조건에 맞는 기록이 없습니다.</TableCell></TableRow>}
        </TableBody></Table></div>
        <nav aria-label="관리자 목록 페이지" className="mt-4 flex items-center justify-end gap-3">
          <Button variant="outline" disabled={data.pagination.page <= 1} onClick={() => { const next = new URLSearchParams(params); next.set("page", String(data.pagination.page - 1)); setParams(next) }}>이전</Button>
          <span>{data.pagination.page} / {Math.max(1, data.pagination.pages)} 페이지</span>
          <Button variant="outline" disabled={data.pagination.page >= data.pagination.pages} onClick={() => { const next = new URLSearchParams(params); next.set("page", String(data.pagination.page + 1)); setParams(next) }}>다음</Button>
        </nav>
      </>}
    </>}
  </div>
}
