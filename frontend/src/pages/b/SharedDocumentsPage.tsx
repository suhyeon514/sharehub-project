import { useEffect, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ApiError, apiGet } from "@/lib/api"

type Result = {
  items: {
    share_id: number
    document: { id: number; title: string }
    shared_by: { id: number; username: string }
    permission: "view" | "download" | "edit"
    shared_at: string | null
  }[]
  pagination: { page: number; per_page: number; total: number; pages: number }
}
const labels = { view: "조회", download: "다운로드", edit: "편집" }

export default function SharedDocumentsPage() {
  const [params] = useSearchParams()
  const [attempt, setAttempt] = useState(0)
  return <SharedContent key={`${params.toString()}:${attempt}`} onReload={() => setAttempt((value) => value + 1)} />
}

function SharedContent({ onReload }: { onReload: () => void }) {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const [query, setQuery] = useState(params.get("q") ?? "")
  const [sharer, setSharer] = useState(params.get("sharer") ?? "")
  const [permission, setPermission] = useState(params.get("permission") ?? "")
  const [result, setResult] = useState<Result | null>(null)
  const [error, setError] = useState("")
  const search = params.toString()

  useEffect(() => {
    const controller = new AbortController()
    apiGet<Result>(`/api/documents/shared?${search}`, controller.signal)
      .then((data) => { if (!controller.signal.aborted) setResult(data) })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return
        if (reason instanceof ApiError && reason.status === 401) {
          navigate("/login", { replace: true, state: { from: `/documents/shared?${search}` } })
        } else {
          setError(reason instanceof ApiError ? reason.message : "서버에 연결할 수 없습니다. 다시 시도해주세요.")
        }
      })
    return () => controller.abort()
  }, [search, navigate])

  const changePage = (page: number) => {
    const next = new URLSearchParams(params)
    next.set("page", String(page))
    setParams(next)
  }

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900">공유받은 자료</h1>
        <p className="mt-1.5 text-sm text-gray-500">나에게 개별 공유된 자료와 부여받은 공유 권한을 확인하세요.</p>
      </header>
      <form className="mb-4 flex flex-wrap items-center gap-2" onSubmit={(event) => {
        event.preventDefault()
        const next = new URLSearchParams()
        if (query.trim()) next.set("q", query.trim())
        if (sharer.trim()) next.set("sharer", sharer.trim())
        if (permission) next.set("permission", permission)
        next.set("page", "1")
        setParams(next)
        onReload()
      }}>
        <Input aria-label="제목 검색" placeholder="제목 검색" maxLength={255} value={query} onChange={(event) => setQuery(event.target.value)} className="w-full max-w-xs" />
        <Input aria-label="공유자 계정명" placeholder="공유자 계정명" maxLength={50} value={sharer} onChange={(event) => setSharer(event.target.value)} className="w-44" />
        <select aria-label="공유 권한 필터" value={permission} onChange={(event) => setPermission(event.target.value)} className="h-9 rounded-md border border-gray-300 px-2 text-sm">
          <option value="">권한 전체</option><option value="view">조회</option><option value="download">다운로드</option><option value="edit">편집</option>
        </select>
        <Button type="submit" variant="outline">검색</Button>
        <Button type="button" variant="ghost" onClick={() => { setParams({}); onReload() }}>초기화</Button>
        <Button type="button" variant="outline" onClick={onReload}>새로고침</Button>
      </form>
      <div aria-live="polite" aria-busy={!result && !error}>
        {error ? <div role="alert" className="space-y-3 rounded-lg border p-5">
          <p className="text-red-600">{error}</p><Button variant="outline" onClick={onReload}>다시 시도</Button>
        </div> : !result ? <p className="py-10 text-center text-gray-500">공유받은 자료를 불러오는 중입니다.</p> : <>
          <p className="mb-3 text-sm text-gray-600">검색 결과 {result.pagination.total}건</p>
          <div className="rounded-lg border border-gray-200 bg-white">
            <Table>
              <TableHeader><TableRow><TableHead>제목</TableHead><TableHead>공유자</TableHead><TableHead>공유 권한</TableHead><TableHead>공유일</TableHead></TableRow></TableHeader>
              <TableBody>
                {result.items.map((item) => <TableRow key={item.share_id}>
                  <TableCell><Link className="font-medium text-emerald-800 underline-offset-4 hover:underline focus-visible:underline" to={`/documents/${item.document.id}`}>{item.document.title}</Link></TableCell>
                  <TableCell>{item.shared_by.username}</TableCell>
                  <TableCell><Badge variant="outline">{labels[item.permission]}</Badge></TableCell>
                  <TableCell>{item.shared_at?.slice(0, 10) ?? "—"}</TableCell>
                </TableRow>)}
                {result.items.length === 0 && <TableRow><TableCell colSpan={4} className="py-10 text-center text-gray-500">조건에 맞는 공유 자료가 없습니다.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </div>
          <nav aria-label="공유받은 자료 페이지" className="mt-4 flex items-center justify-end gap-3">
            <Button variant="outline" disabled={result.pagination.page <= 1} onClick={() => changePage(result.pagination.page - 1)}>이전</Button>
            <span className="text-sm">{result.pagination.page} / {Math.max(1, result.pagination.pages)} 페이지</span>
            <Button variant="outline" disabled={result.pagination.page >= result.pagination.pages} onClick={() => changePage(result.pagination.page + 1)}>다음</Button>
          </nav>
        </>}
      </div>
    </div>
  )
}
