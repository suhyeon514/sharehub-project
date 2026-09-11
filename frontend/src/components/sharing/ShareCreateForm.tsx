import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ApiError, apiGet, apiPost } from "@/lib/api"

type User = { id: number; username: string }
type Permission = "view" | "download" | "edit"
type Share = { id: number; shared_with: User; permission: Permission }
const labels: Record<Permission, string> = { view: "조회", download: "다운로드", edit: "편집" }

export default function ShareCreateForm({ documentId, shares, onCreated }: {
  documentId: string
  shares: Share[]
  onCreated: (share: Share) => void
}) {
  const navigate = useNavigate()
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<User[] | null>(null)
  const [selected, setSelected] = useState<User | null>(null)
  const [permission, setPermission] = useState<Permission>("view")
  const [searching, setSearching] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const searchController = useRef<AbortController | null>(null)
  const submitting = useRef(false)
  let currentUserId: number | undefined
  try { currentUserId = JSON.parse(localStorage.getItem("sharehub_user") ?? "null")?.id } catch { /* 서버가 최종 검사한다. */ }

  useEffect(() => () => searchController.current?.abort(), [])

  const handleError = (reason: unknown) => {
    if (reason instanceof ApiError && reason.status === 401) {
      navigate("/login", { replace: true, state: { from: `/documents/${documentId}/share` } })
      return
    }
    setError(reason instanceof ApiError ? reason.message : "서버 연결을 확인해주세요. 공유 요청 후 오류가 났다면 목록을 새로고침해 저장 여부를 확인하세요.")
  }

  const search = async () => {
    searchController.current?.abort()
    const controller = new AbortController()
    searchController.current = controller
    setSearching(true)
    setResults(null)
    setError("")
    setMessage("")
    setSelected(null)
    try {
      const data = await apiGet<{ users: User[] }>(`/api/users?q=${encodeURIComponent(query.trim())}`, controller.signal)
      if (!controller.signal.aborted) setResults(data.users)
    } catch (reason) {
      if (!controller.signal.aborted) handleError(reason)
    } finally {
      if (!controller.signal.aborted) setSearching(false)
    }
  }

  const create = async () => {
    if (!selected || submitting.current) return
    submitting.current = true
    setSaving(true)
    setError("")
    setMessage("")
    try {
      const data = await apiPost<{ share: Share }>(`/api/documents/${documentId}/shares`, {
        shared_with_id: selected.id, permission,
      })
      onCreated(data.share)
      setSelected(null)
      setQuery("")
      setResults(null)
      setPermission("view")
      setMessage(`${data.share.shared_with.username}님에게 공유했습니다.`)
    } catch (reason) {
      handleError(reason)
    } finally {
      submitting.current = false
      setSaving(false)
    }
  }

  return (
    <div className="mt-4">
      <form onSubmit={(event) => { event.preventDefault(); if (query.trim() && !saving) void search() }}>
        <label htmlFor="share-user-search" className="mb-1 block text-xs font-medium text-gray-500">사용자 검색</label>
        <div className="flex gap-2">
          <Input id="share-user-search" placeholder="아이디" maxLength={50} value={query} disabled={saving}
            onChange={(event) => {
              searchController.current?.abort()
              setSearching(false)
              setQuery(event.target.value)
              setSelected(null)
              setResults(null)
              setError("")
              setMessage("")
            }} />
          <Button type="submit" variant="outline" disabled={!query.trim() || searching || saving}>검색</Button>
        </div>
      </form>
      <div aria-live="polite" className="mt-2 text-sm">
        {searching && <p>검색 중입니다.</p>}
        {results?.length === 0 && <p>검색 결과가 없습니다.</p>}
        {results && results.length > 0 && (
          <div>
            <ul className="max-h-40 space-y-1 overflow-y-auto">
              {results.map((user) => {
                const shared = shares.some((share) => share.shared_with.id === user.id)
                const self = user.id === currentUserId
                return <li key={user.id}>
                  <Button type="button" variant={selected?.id === user.id ? "default" : "outline"}
                    className="h-auto w-full justify-start whitespace-normal break-all text-left" disabled={self || shared || saving}
                    onClick={() => { setSelected(user); setMessage(""); setError("") }}>
                    {user.username}{self ? " (본인)" : shared ? " (공유 중)" : ""}
                  </Button>
                </li>
              })}
            </ul>
            <p className="mt-1 text-xs text-gray-500">최대 20명 표시됩니다. 원하는 계정이 없으면 검색어를 구체적으로 입력하세요.</p>
          </div>
        )}
        {selected && <p className="mt-2">선택한 사용자: {selected.username}</p>}
      </div>
      <p className="mb-1 mt-3 text-xs font-medium text-gray-500">권한</p>
      <div className="flex gap-1.5">
        {(Object.keys(labels) as Permission[]).map((value) => (
          <Button key={value} type="button" size="sm" aria-pressed={permission === value}
            variant={permission === value ? "default" : "outline"} disabled={saving}
            onClick={() => setPermission(value)}>{labels[value]}</Button>
        ))}
      </div>
      <p className="mt-2 text-xs text-gray-500">다운로드는 조회를, 편집은 조회·다운로드를 포함합니다. 기존 공유는 아래 목록에서 변경하거나 제거할 수 있습니다.</p>
      {error && <p role="alert" className="mt-2 text-sm text-red-600">{error}</p>}
      {message && <p role="status" className="mt-2 text-sm text-green-700">{message}</p>}
      <div className="mt-3 flex justify-end">
        <Button type="button" size="sm" disabled={!selected || saving || shares.some((share) => share.shared_with.id === selected.id)} onClick={() => void create()}>
          {saving ? "공유 중…" : "공유"}
        </Button>
      </div>
    </div>
  )
}
