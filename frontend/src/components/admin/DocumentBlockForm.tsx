import { useRef, useState } from "react"
import AdminModal from "@/components/admin/AdminModal"
import { Button } from "@/components/ui/button"
import { ApiError, apiPost } from "@/lib/api"

export default function DocumentBlockForm({ document, onDone, onCancel, onAuthError }: {
  document: { id: number; title: string }
  onDone: (message: string) => void
  onCancel: () => void
  onAuthError: (error: ApiError) => void
}) {
  const [reason, setReason] = useState("")
  const [basis, setBasis] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const submitting = useRef(false)
  // Python len과 같이 유니코드 코드 포인트로 계산한다.
  const reasonLength = Array.from(reason.trim()).length
  const basisLength = Array.from(basis.trim()).length
  const valid = reasonLength >= 1 && reasonLength <= 1000 && basisLength >= 1 && basisLength <= 5000

  async function submit() {
    if (!valid || submitting.current) return
    submitting.current = true
    setBusy(true)
    setError("")
    try {
      await apiPost(`/api/admin/documents/${document.id}/blocks`, {
        block_reason: reason.trim(), block_basis: basis.trim(),
      })
      onDone("문서를 차단했습니다.")
    } catch (cause) {
      if (cause instanceof ApiError && (cause.status === 401 || cause.status === 403)) {
        onAuthError(cause)
      } else if (cause instanceof ApiError && cause.code === "DOCUMENT_ALREADY_BLOCKED") {
        onDone("이미 차단된 문서입니다. 목록을 갱신했습니다.")
      } else {
        setError(cause instanceof ApiError ? cause.message : "서버에 연결할 수 없습니다. 요청이 처리되었을 수 있으니 목록에서 상태를 확인해주세요.")
      }
    } finally {
      submitting.current = false
      setBusy(false)
    }
  }

  return <AdminModal title="문서 차단" busy={busy} onClose={onCancel}>
    <h2 id="block-form-title" className="font-semibold">문서 차단: {document.title} (#{document.id})</h2>
    <p className="mt-2 text-sm text-gray-700">차단하면 소유자를 포함한 모든 사용자의 일반 문서 이용과 공유 관리가 중지됩니다. 원본과 기존 기록은 보존됩니다.</p>
    <form className="mt-4 space-y-4" aria-busy={busy} onSubmit={(event) => { event.preventDefault(); void submit() }}>
      <div>
        <label htmlFor="block-reason" className="block text-sm font-medium">차단 사유</label>
        <p id="block-reason-help" className="my-1 text-sm text-gray-600">소유자에게 공개됩니다. 앞뒤 공백 제외 1~1,000자.</p>
        <textarea id="block-reason" aria-describedby="block-reason-help" required disabled={busy} rows={3}
          className="w-full rounded-md border bg-white p-2 disabled:opacity-50" value={reason} onChange={(event) => setReason(event.target.value)} />
        <p className={reasonLength > 1000 ? "text-sm text-red-600" : "text-sm text-gray-500"}>{reasonLength.toLocaleString()} / 1,000자</p>
      </div>
      <div>
        <label htmlFor="block-basis" className="block text-sm font-medium">내부 근거</label>
        <p id="block-basis-help" className="my-1 text-sm text-gray-600">관리자 전용 정보입니다. 앞뒤 공백 제외 1~5,000자.</p>
        <textarea id="block-basis" aria-describedby="block-basis-help" required disabled={busy} rows={4}
          className="w-full rounded-md border bg-white p-2 disabled:opacity-50" value={basis} onChange={(event) => setBasis(event.target.value)} />
        <p className={basisLength > 5000 ? "text-sm text-red-600" : "text-sm text-gray-500"}>{basisLength.toLocaleString()} / 5,000자</p>
      </div>
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" variant="destructive" disabled={!valid || busy}>{busy ? "차단 중…" : "차단 실행"}</Button>
        <Button type="button" variant="outline" disabled={busy} onClick={onCancel}>취소</Button>
      </div>
    </form>
  </AdminModal>
}
