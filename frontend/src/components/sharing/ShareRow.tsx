import { useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { ApiError, apiDelete, apiPatch } from "@/lib/api"

type Permission = "view" | "download" | "edit"
type Share = { id: number; shared_with: { id: number; username: string }; permission: Permission }

export default function ShareRow({ documentId, share, onUpdated, onDeleted, onBlocked }: {
  documentId: string
  share: Share
  onUpdated: (share: Share) => void
  onDeleted: (id: number) => void
  onBlocked: (message: string) => void
}) {
  const navigate = useNavigate()
  const [permission, setPermission] = useState(share.permission)
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const submitting = useRef(false)

  const submit = async (remove: boolean) => {
    if (submitting.current) return
    submitting.current = true
    setBusy(true)
    setError("")
    const path = `/api/documents/${documentId}/shares/${share.id}`
    try {
      if (remove) {
        const result = await apiDelete<{ deleted_share_id: number }>(path)
        onDeleted(result.deleted_share_id)
      } else {
        const result = await apiPatch<{ share: Share }>(path, { permission })
        onUpdated(result.share)
      }
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) {
        navigate("/login", { replace: true, state: { from: `/documents/${documentId}/share` } })
      } else if (reason instanceof ApiError && reason.code === "DOCUMENT_BLOCKED") {
        onBlocked(reason.message)
      } else {
        setError(reason instanceof ApiError
          ? `${reason.message}${reason.status === 404 ? " 목록을 새로고침해주세요." : ""}`
          : "서버 연결을 확인해주세요. 새로고침하여 처리 결과를 확인할 수 있습니다.")
      }
    } finally {
      submitting.current = false
      setBusy(false)
    }
  }

  return (
    <li className="space-y-3 rounded-xl border border-gray-100 bg-gray-50 px-4 py-4" aria-busy={busy}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <span className="min-w-0 flex-1 break-all text-sm font-medium text-gray-900">{share.shared_with.username}</span>
        <div className="flex shrink-0 flex-wrap items-center gap-2 sm:gap-3">
          <select aria-label={`${share.shared_with.username} 공유 권한`} value={permission}
            disabled={busy || confirming} onChange={(event) => setPermission(event.target.value as Permission)}
            className="h-9 w-28 rounded-md border border-gray-300 bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600 disabled:opacity-50">
            <option value="view">조회</option>
            <option value="download">다운로드</option>
            <option value="edit">편집</option>
          </select>
          <Button size="sm" variant="outline" className="h-9 rounded-lg px-3" disabled={busy || confirming || permission === share.permission}
            onClick={() => void submit(false)}>저장</Button>
          <Button size="sm" variant="ghost" className="h-9 px-3 text-red-600 hover:bg-red-50 hover:text-red-700" disabled={busy || confirming}
            onClick={() => { setConfirming(true); setError("") }}>제거</Button>
          {busy && <span role="status" className="text-xs">처리 중…</span>}
        </div>
      </div>
      {confirming && (
        <div className="space-y-2 text-sm">
          <p>{share.shared_with.username}님의 개별 공유를 해제할까요? 팀 조회 권한은 별도로 유지될 수 있습니다.</p>
          <div className="flex gap-2">
            <Button size="xs" variant="destructive" disabled={busy} onClick={() => void submit(true)}>공유 해제</Button>
            <Button size="xs" variant="outline" disabled={busy} onClick={() => setConfirming(false)}>취소</Button>
          </div>
        </div>
      )}
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
    </li>
  )
}
