import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ApiError, apiGet } from "@/lib/api"
import DocumentBlockForm from "@/components/admin/DocumentBlockForm"
import AdminReviewsPage from "@/pages/b/AdminReviewsPage"

type Resource = "users" | "documents" | "activity-logs"
type RequestStatus = "pending" | "approved" | "rejected" | "cancelled"
const requestLabels: Record<RequestStatus, string> = { pending: "검토 대기", approved: "승인", rejected: "거절", cancelled: "요청 취소" }
type AdminItem = Record<string, unknown> & { active_block?: { id: number; status: "blocked"; blocked_at: string; latest_request_status: RequestStatus | null } | null }
type Result = { items: AdminItem[]; pagination: { page: number; pages: number; total: number } }
const columns: Record<Resource, [string, string][]> = {
  users: [["username", "계정명"], ["role", "역할"], ["department", "부서"], ["created_at", "가입일"]],
  documents: [["title", "제목"], ["owner", "소유자"], ["department", "부서"], ["visibility", "공개 범위"], ["updated_at", "수정일"]],
  "activity-logs": [["username", "작업자"], ["action_type", "이벤트"], ["created_at", "기록 시각"], ["detail", "상세"]],
}
function display(value: unknown, key: string, actionType: unknown) {
  if (key === "action_type" && value === "DOCUMENT_UPDATE") return "문서 수정"
  if (value === null || value === undefined) return "—"
  if (key === "detail") {
    const detail = value as Record<string, unknown>
    if (actionType === "DOCUMENT_UPDATE") {
      const fields = Array.isArray(detail.changed_fields) ? detail.changed_fields : []
      const labels = [["title", "제목"], ["description", "설명"]]
        .filter(([field]) => fields.includes(field)).map(([, label]) => label)
      return ["문서 수정", detail.document_id != null ? `문서 #${detail.document_id}` : "",
        labels.length ? `변경 항목: ${labels.join(", ")}` : ""].filter(Boolean).join(" · ")
    }
    if (detail.operation === "review") return [detail.decision === "approved" ? "소명 승인" : "소명 거절", `문서 #${detail.document_id}`, `요청 #${detail.request_id}`, detail.review_comment].filter(Boolean).join(" · ")
    if (detail.operation === "block") return ["문서 차단", `문서 #${detail.document_id}`, `차단 #${detail.block_id}`, detail.block_reason].filter(Boolean).join(" · ")
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
  const [notice, setNotice] = useState("")
  if (params.get("tab") === "unblock-requests") return <AdminReviewsPage />
  return <AdminContent key={`${params.toString()}:${attempt}`} notice={notice}
    onBlocked={(message) => { setNotice(message); setAttempt((value) => value + 1) }}
    reload={() => { setNotice(""); setAttempt((value) => value + 1) }} />
}
function AdminContent({ reload, notice, onBlocked }: { reload: () => void; notice: string; onBlocked: (message: string) => void }) {
  const [params, setParams] = useSearchParams()
  const tab = params.get("tab") ?? "users"
  const resource: Resource = tab === "documents" || tab === "activity-logs" ? tab : "users"
  const [query, setQuery] = useState(params.get("q") ?? "")
  const [data, setData] = useState<Result | null>(null)
  const [error, setError] = useState("")
  const [forbidden, setForbidden] = useState(false)
  const [selected, setSelected] = useState<{ id: number; title: string } | null>(null)
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
      {notice && resource === "documents" && <p role="status" className="mb-4 text-sm text-gray-700">{notice}</p>}
      {selected && <DocumentBlockForm key={selected.id} document={selected} onDone={onBlocked} onCancel={() => setSelected(null)}
        onAuthError={(reason) => {
          if (reason.status === 401) navigate("/login", { replace: true, state: { from: `/admin?${search}` } })
          else { setSelected(null); setData(null); setForbidden(true); setError(reason.message) }
        }} />}
      <form className="mb-4 flex flex-wrap gap-2" onSubmit={(event) => { event.preventDefault(); const next = new URLSearchParams(params); next.set("tab", resource); next.set("q", query.trim()); next.set("page", "1"); setParams(next); reload() }}>
        <Input className="max-w-sm" aria-label="목록 검색" maxLength={255} placeholder={resource === "users" ? "계정명 검색" : resource === "documents" ? "문서 제목 검색" : "이벤트 검색 (예: DOCUMENT_SHARE)"} value={query} onChange={(event) => setQuery(event.target.value)} />
        {resource === "documents" && <select aria-label="문서 상태" value={params.get("status") ?? ""}
          className="h-9 rounded-md border border-gray-300 bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600"
          onChange={(event) => { const next = new URLSearchParams(params); next.set("tab", "documents"); next.set("page", "1"); next.set("q", query.trim()); if (event.target.value) next.set("status", event.target.value); else next.delete("status"); setParams(next) }}>
          <option value="">문서 상태</option>
          <option value="normal">정상</option>
          <option value="blocked">차단</option>
          <option value="pending">검토 대기</option>
          <option value="rejected">거절</option>
          <option value="cancelled">요청 취소</option>
        </select>}
        <Button type="submit" variant="outline">검색</Button><Button type="button" variant="ghost" onClick={() => { setParams({ tab: resource }); reload() }}>초기화</Button><Button type="button" variant="outline" onClick={reload}>새로고침</Button>
      </form>
      {error ? <div role="alert"><p className="text-red-600">{error}</p><Button variant="outline" onClick={reload}>다시 시도</Button></div> : !data ? <p role="status">조회 중입니다.</p> : <>
        <p className="mb-3 text-sm">총 {data.pagination.total}건</p>
        <div className="rounded-lg border bg-white"><Table><TableHeader><TableRow>{columns[resource].map(([key, title]) => <TableHead key={key}>{title}</TableHead>)}{resource === "documents" && <><TableHead>문서 상태</TableHead><TableHead>소명 상태</TableHead><TableHead>관리</TableHead></>}</TableRow></TableHeader><TableBody>
          {data.items.map((item) => <TableRow key={String(item.id)}>{columns[resource].map(([key]) => <TableCell key={key} className="whitespace-normal break-words">{display(item[key], key, item.action_type)}</TableCell>)}
            {resource === "documents" && <>
              <TableCell><span className={item.active_block ? "font-medium text-red-700" : "text-gray-600"}>{item.active_block ? "차단" : "정상"}</span></TableCell>
              <TableCell>{item.active_block ? (item.active_block.latest_request_status ? requestLabels[item.active_block.latest_request_status] : "요청 없음") : "—"}</TableCell>
              <TableCell><Button size="sm" variant="outline" disabled={Boolean(item.active_block) || selected !== null}
                aria-label={`${String(item.title)} 차단`} onClick={() => setSelected({ id: Number(item.id), title: String(item.title) })}>{item.active_block ? "차단됨" : "차단"}</Button></TableCell>
            </>}
          </TableRow>)}
          {!data.items.length && <TableRow><TableCell colSpan={columns[resource].length + (resource === "documents" ? 3 : 0)} className="py-10 text-center">조건에 맞는 기록이 없습니다.</TableCell></TableRow>}
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
