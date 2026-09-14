import { useEffect, useRef, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import AdminModal from "@/components/admin/AdminModal"
import { ApiError, apiGet, apiPost } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

type Status = "pending" | "approved" | "rejected" | "cancelled"
type Reason = "SELF_REVIEW_NOT_ALLOWED" | "UNBLOCK_REQUEST_NOT_PENDING" | "DOCUMENT_BLOCK_NOT_ACTIVE" | null
type Person = { id: number; username: string }
type Item = { id: number; document_id: number; title: string; block_id: number; block_status: string; requester: Person; status: Status; requested_at: string; can_review: boolean; review_unavailable_reason: Reason }
type List = { items: Item[]; pagination: { page: number; pages: number; total: number } }
type Detail = { document: { id: number; title: string }; block: { id: number; status: string; block_reason: string; block_basis: string; blocked_at: string; is_current_block: boolean }; unblock_request: { id: number; status: Status; request_reason: string; requested_at: string; requester: Person; review_comment: string | null; reviewed_by: Person | null; reviewed_at: string | null; cancelled_at: string | null }; can_review: boolean; review_unavailable_reason: Reason }
const labels: Record<Status, string> = { pending: "검토 대기", approved: "승인", rejected: "거절", cancelled: "요청 취소" }
const reasons = { SELF_REVIEW_NOT_ALLOWED: "본인 문서 또는 본인 요청은 심사할 수 없습니다.", UNBLOCK_REQUEST_NOT_PENDING: "이미 처리되었거나 취소된 요청입니다.", DOCUMENT_BLOCK_NOT_ACTIVE: "현재 활성 차단에 대한 요청이 아닙니다." }
const time = (value: string | null) => value ? new Date(value).toLocaleString("ko-KR") : "—"

export default function AdminReviewsPage() {
  const [params] = useSearchParams()
  return <Reviews key={params.toString()} />
}

function Reviews() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const [query, setQuery] = useState(params.get("q") ?? "")
  const [list, setList] = useState<List | null>(null)
  const [selected, setSelected] = useState(params.get("request_id") ?? "")
  const [detail, setDetail] = useState<Detail | null>(null)
  const [error, setError] = useState("")
  const [detailError, setDetailError] = useState("")
  const [notice, setNotice] = useState("")
  const [forbidden, setForbidden] = useState(false)
  const [revision, setRevision] = useState(0)
  const [busy, setBusy] = useState(false)
  const [comment, setComment] = useState("")
  const submitting = useRef(false)
  const alive = useRef(true)
  const search = params.toString()
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])

  function handleAuth(cause: unknown) {
    if (!(cause instanceof ApiError)) return false
    if (cause.status === 401) {
      navigate("/login", { replace: true, state: { from: `/admin?${search}` } })
      return true
    }
    if (cause.status === 403 && cause.code !== "SELF_REVIEW_NOT_ALLOWED") {
      setForbidden(true); setList(null); setDetail(null); setError(cause.message)
      return true
    }
    return false
  }

  useEffect(() => {
    const controller = new AbortController()
    apiGet<List>(`/api/admin/unblock-requests?${search}`, controller.signal).then((data) => {
      if (!controller.signal.aborted) setList(data)
    }).catch((cause: unknown) => {
      if (controller.signal.aborted) return
      if (cause instanceof ApiError && cause.status === 401) navigate("/login", { replace: true, state: { from: `/admin?${search}` } })
      else { setForbidden(cause instanceof ApiError && cause.status === 403); setError(cause instanceof Error ? cause.message : "목록을 조회하지 못했습니다.") }
    })
    return () => controller.abort()
  }, [search, revision, navigate])

  useEffect(() => {
    if (!selected || forbidden) return
    const controller = new AbortController()
    apiGet<Detail>(`/api/admin/unblock-requests/${selected}`, controller.signal).then((data) => {
      if (!controller.signal.aborted) setDetail(data)
    }).catch((cause: unknown) => {
      if (controller.signal.aborted) return
      if (cause instanceof ApiError && cause.status === 401) navigate("/login", { replace: true, state: { from: `/admin?${search}` } })
      else if (cause instanceof ApiError && cause.status === 403) { setForbidden(true); setError(cause.message) }
      else setDetailError(cause instanceof Error ? cause.message : "상세를 조회하지 못했습니다.")
    })
    return () => controller.abort()
  }, [selected, revision, search, forbidden, navigate])

  function refresh() { setList(null); setDetail(null); setError(""); setDetailError(""); setRevision((value) => value + 1) }
  function change(values: Record<string, string>) {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(values)) { if (value) next.set(key, value); else next.delete(key) }
    next.set("tab", "unblock-requests"); next.delete("request_id"); setParams(next)
  }
  async function review(decision: "approved" | "rejected") {
    if (!detail?.can_review || submitting.current) return
    submitting.current = true; setBusy(true); setDetailError(""); setNotice("")
    try {
      await apiPost<Detail>(`/api/admin/unblock-requests/${detail.unblock_request.id}/review`, { decision, review_comment: comment.trim() })
      if (!alive.current) return
      setComment(""); setNotice(`${labels[decision]} 처리가 완료되었습니다.`); refresh()
    } catch (cause) {
      if (!alive.current || handleAuth(cause)) return
      if (cause instanceof ApiError && (cause.status === 409 || cause.code === "SELF_REVIEW_NOT_ALLOWED")) {
        setNotice(cause.message); refresh()
      } else setDetailError(cause instanceof ApiError ? cause.message : "서버 연결을 확인해주세요. 처리되었을 수 있으니 새로고침하여 결과를 확인하세요.")
    } finally { submitting.current = false; if (alive.current) setBusy(false) }
  }
  const length = Array.from(comment.trim()).length
  return <div>
    <h1 className="mb-2 text-xl font-semibold">소명 관리</h1>
    <p className="mb-5 text-sm text-gray-500">차단된 문서의 소명을 검토하고 승인 또는 거절합니다.</p>
    {forbidden ? <p role="alert">{error}</p> : <>
      <form className="mb-4 flex flex-wrap gap-2" onSubmit={(event) => { event.preventDefault(); change({ q: query.trim(), page: "1" }) }}>
        <Input aria-label="문서 제목 검색" placeholder="문서 제목 검색" maxLength={255} value={query} disabled={busy} className="max-w-sm" onChange={(event) => setQuery(event.target.value)} />
        <select aria-label="소명 상태" disabled={busy} className="rounded-md border bg-white px-3 text-sm" value={params.get("status") ?? ""} onChange={(event) => change({ status: event.target.value, page: "1", q: query.trim() })}>
          <option value="">전체 요청</option>{Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <Button variant="outline" disabled={busy}>검색</Button>
        <Button type="button" variant="ghost" disabled={busy} onClick={() => setParams({ tab: "unblock-requests" })}>초기화</Button>
        <Button type="button" variant="outline" disabled={busy} onClick={refresh}>새로고침</Button>
      </form>
      {params.get("block_id") && <p className="mb-3 text-sm">차단 #{params.get("block_id")}의 요청 이력</p>}
      {notice && !selected && <p role="status" className="mb-3 text-sm text-emerald-700">{notice}</p>}
      {error ? <p role="alert" className="text-red-600">{error}</p> : !list ? <p role="status">조회 중입니다.</p> : <>
        <p className="mb-3 text-sm">총 {list.pagination.total}건</p>
        <ul className="space-y-2">{list.items.map((item) => <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-white p-4">
          <div><p className="font-medium">{item.title}</p><p className="text-sm text-gray-500">요청 #{item.id} · {item.requester.username} · {labels[item.status]} · {time(item.requested_at)}</p></div>
          <Button variant="outline" disabled={busy} onClick={() => { setDetail(null); setDetailError(""); setComment(""); setSelected(String(item.id)); if (selected === String(item.id)) setRevision((value) => value + 1) }}>상세 보기</Button>
        </li>)}</ul>
        {!list.items.length && <p className="py-6 text-gray-500">조건에 맞는 소명 요청이 없습니다.</p>}
        <nav aria-label="소명 목록 페이지" className="my-4 flex justify-end gap-3">
          <Button variant="outline" disabled={busy || list.pagination.page <= 1} onClick={() => change({ page: String(list.pagination.page - 1) })}>이전</Button>
          <span>{list.pagination.page} / {Math.max(1, list.pagination.pages)}</span>
          <Button variant="outline" disabled={busy || list.pagination.page >= list.pagination.pages} onClick={() => change({ page: String(list.pagination.page + 1) })}>다음</Button>
        </nav>
      </>}
      {selected && <AdminModal title="소명 상세·심사" busy={busy} onClose={() => { setSelected(""); setDetail(null); setDetailError(""); setComment("") }}>
        {notice && <p role="status" className="text-sm text-emerald-700">{notice}</p>}
        {detailError && <p role="alert" className="text-red-600">{detailError}</p>}
        {!detail ? !detailError && <p role="status">상세 조회 중입니다.</p> : <>
          <p className="font-medium">{detail.document.title} · 차단 #{detail.block.id}</p>
          <p className="text-sm">{detail.block.status === "blocked" ? "차단" : "해제"} · {labels[detail.unblock_request.status]} · 요청자 {detail.unblock_request.requester.username}</p>
          {[["차단 사유 (소유자 공개)", detail.block.block_reason], ["내부 근거 (관리자 전용)", detail.block.block_basis], ["소명 내용", detail.unblock_request.request_reason], ["심사 의견 (소유자 공개)", detail.unblock_request.review_comment ?? "—"]].map(([label, value]) => <div key={label}><h3 className="text-sm font-semibold">{label}</h3><p className="mt-1 whitespace-pre-wrap break-words text-sm text-gray-700">{value}</p></div>)}
          <p className="text-sm text-gray-500">요청: {time(detail.unblock_request.requested_at)} · 심사: {time(detail.unblock_request.reviewed_at)} · 심사자: {detail.unblock_request.reviewed_by?.username ?? "—"}</p>
          {!detail.can_review ? <p role="status" className="rounded-lg bg-gray-100 p-3 text-sm">{detail.review_unavailable_reason ? reasons[detail.review_unavailable_reason] : "현재 심사할 수 없습니다."}</p> : <div>
            <label htmlFor="review-comment" className="block text-sm font-medium">심사 의견</label>
            <p className="my-1 text-sm text-gray-500">소유자에게 공개됩니다. 앞뒤 공백 제외 1~1,000자. 승인하면 해당 차단이 해제되고, 거절하면 차단이 유지됩니다.</p>
            <textarea id="review-comment" rows={4} disabled={busy} className="w-full rounded-md border p-2" value={comment} onChange={(event) => setComment(event.target.value)} />
            <p className={`text-sm ${length > 1000 ? "text-red-600" : "text-gray-500"}`}>{length} / 1,000자</p>
            <div className="mt-3 flex gap-2"><Button disabled={busy || length < 1 || length > 1000} onClick={() => void review("approved")}>승인</Button><Button variant="destructive" disabled={busy || length < 1 || length > 1000} onClick={() => void review("rejected")}>거절</Button>{busy && <span role="status">처리 중…</span>}</div>
          </div>}
        </>}
      </AdminModal>}
    </>}
  </div>
}
