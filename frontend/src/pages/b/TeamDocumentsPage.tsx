import { useEffect, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ApiError, apiGet } from "@/lib/api"

type Result = {
  department: { id: number; name: string } | null
  items: { id: number; title: string; owner: { id: number; username: string }; updated_at: string | null }[]
  pagination: { page: number; per_page: number; total: number; pages: number }
}

export default function TeamDocumentsPage() {
  const [params] = useSearchParams()
  const [attempt, setAttempt] = useState(0)
  return <TeamContent key={`${params.toString()}:${attempt}`} onReload={() => setAttempt((value) => value + 1)} />
}

function TeamContent({ onReload }: { onReload: () => void }) {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const [query, setQuery] = useState(params.get("q") ?? "")
  const [result, setResult] = useState<Result | null>(null)
  const [error, setError] = useState("")
  const search = params.toString()

  useEffect(() => {
    const controller = new AbortController()
    apiGet<Result>(`/api/documents/team?${search}`, controller.signal)
      .then((data) => { if (!controller.signal.aborted) setResult(data) })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return
        if (reason instanceof ApiError && reason.status === 401) {
          navigate("/login", { replace: true, state: { from: `/documents/team?${search}` } })
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
        <h1 className="text-xl font-semibold text-gray-900">팀 자료</h1>
        <p className="mt-1.5 text-sm text-gray-500">내 부서의 팀 공개 자료입니다. 다른 부서에서 개별 공유받은 자료는 공유받은 자료에서 확인하세요.</p>
      </header>
      <form className="mb-4 flex flex-wrap items-center gap-2" onSubmit={(event) => {
        event.preventDefault()
        const next = new URLSearchParams()
        if (query.trim()) next.set("q", query.trim())
        next.set("page", "1")
        setParams(next)
        onReload()
      }}>
        <Input aria-label="제목 검색" placeholder="제목 검색" maxLength={255} value={query} onChange={(event) => setQuery(event.target.value)} className="w-full max-w-xs" />
        <Button type="submit" variant="outline">검색</Button>
        <Button type="button" variant="ghost" onClick={() => { setParams({}); onReload() }}>초기화</Button>
        <Button type="button" variant="outline" onClick={onReload}>새로고침</Button>
      </form>
      <div aria-live="polite" aria-busy={!result && !error}>
        {error ? <div role="alert" className="space-y-3 rounded-lg border p-5">
          <p className="text-red-600">{error}</p><Button variant="outline" onClick={onReload}>다시 시도</Button>
        </div> : !result ? <p className="py-10 text-center text-gray-500">팀 자료를 불러오는 중입니다.</p> : <>
          <p className="mb-3 text-sm text-gray-600">{result.department ? `${result.department.name} · 검색 결과 ${result.pagination.total}건` : "소속 부서가 지정되지 않았습니다. 부서 배정은 관리자에게 문의해주세요."}</p>
          <div className="rounded-lg border border-gray-200 bg-white">
            <Table>
              <TableHeader><TableRow><TableHead>제목</TableHead><TableHead>소유자</TableHead><TableHead>수정일</TableHead></TableRow></TableHeader>
              <TableBody>
                {result.items.map((item) => <TableRow key={item.id}>
                  <TableCell><Link className="font-medium text-emerald-800 underline-offset-4 hover:underline focus-visible:underline" to={`/documents/${item.id}`}>{item.title}</Link></TableCell>
                  <TableCell>{item.owner.username}</TableCell>
                  <TableCell>{item.updated_at?.slice(0, 10) ?? "—"}</TableCell>
                </TableRow>)}
                {result.items.length === 0 && <TableRow><TableCell colSpan={3} className="py-10 text-center text-gray-500">{result.department ? "조건에 맞는 팀 자료가 없습니다." : "부서 배정 후 팀 자료를 확인할 수 있습니다."}</TableCell></TableRow>}
              </TableBody>
            </Table>
          </div>
          <nav aria-label="팀 자료 페이지" className="mt-4 flex items-center justify-end gap-3">
            <Button variant="outline" disabled={result.pagination.page <= 1} onClick={() => changePage(result.pagination.page - 1)}>이전</Button>
            <span className="text-sm">{result.pagination.page} / {Math.max(1, result.pagination.pages)} 페이지</span>
            <Button variant="outline" disabled={result.pagination.page >= result.pagination.pages} onClick={() => changePage(result.pagination.page + 1)}>다음</Button>
          </nav>
        </>}
      </div>
    </div>
  )
}
