import { useEffect, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ApiError, apiGet } from "@/lib/api"

type Result = {
  filters: { departments: { id: number; name: string }[]; owners: { id: number; username: string }[] }
  items: { id: number; title: string; owner: { id: number; username: string }; department: { id: number; name: string } | null; updated_at: string | null }[]
  pagination: { page: number; per_page: number; total: number; pages: number }
}

export default function SearchPage() {
  const [params] = useSearchParams()
  const [attempt, setAttempt] = useState(0)
  return <SearchContent key={`${params.toString()}:${attempt}`} onReload={() => setAttempt((value) => value + 1)} />
}

function SearchContent({ onReload }: { onReload: () => void }) {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const [query, setQuery] = useState(params.get("q") ?? "")
  const [department, setDepartment] = useState(params.get("department_id") ?? "")
  const [owner, setOwner] = useState(params.get("owner_id") ?? "")
  const [sort, setSort] = useState(params.get("sort") ?? "updated_desc")
  const [result, setResult] = useState<Result | null>(null)
  const [error, setError] = useState("")
  const search = params.toString()

  useEffect(() => {
    const controller = new AbortController()
    apiGet<Result>(`/api/search?${search}`, controller.signal)
      .then((data) => { if (!controller.signal.aborted) setResult(data) })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return
        if (reason instanceof ApiError && reason.status === 401) {
          navigate("/login", { replace: true, state: { from: `/search?${search}` } })
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
        <h1 className="text-xl font-semibold text-gray-900">검색 결과</h1>
        <p className="mt-1.5 text-sm text-gray-500">접근 가능한 문서를 제목으로 검색합니다. 검색어를 비우면 전체 접근 가능한 문서를 표시합니다.</p>
      </header>
      <form className="mb-4 flex flex-wrap items-center gap-2" onSubmit={(event) => {
        event.preventDefault()
        const next = new URLSearchParams()
        if (query.trim()) next.set("q", query.trim())
        if (department) next.set("department_id", department)
        if (owner) next.set("owner_id", owner)
        next.set("sort", sort)
        next.set("page", "1")
        setParams(next)
        onReload()
      }}>
        <Input aria-label="제목 검색" placeholder="제목 검색" maxLength={255} value={query} onChange={(event) => setQuery(event.target.value)} className="w-full max-w-xs" />
        <select aria-label="부서 필터" className="h-9 rounded-md border px-2 text-sm" value={department} onChange={(event) => setDepartment(event.target.value)}>
          <option value="">부서 전체</option>
          {department && !result?.filters.departments.some((item) => String(item.id) === department) && <option value={department}>선택한 부서</option>}
          {result?.filters.departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
        <select aria-label="소유자 필터" className="h-9 rounded-md border px-2 text-sm" value={owner} onChange={(event) => setOwner(event.target.value)}>
          <option value="">소유자 전체</option>
          {owner && !result?.filters.owners.some((item) => String(item.id) === owner) && <option value={owner}>선택한 소유자</option>}
          {result?.filters.owners.map((item) => <option key={item.id} value={item.id}>{item.username}</option>)}
        </select>
        <select aria-label="검색 정렬" className="h-9 rounded-md border px-2 text-sm" value={sort} onChange={(event) => setSort(event.target.value)}>
          <option value="updated_desc">최근 수정순</option><option value="updated_asc">오래된 수정순</option><option value="title_asc">제목순</option>
        </select>
        <Button type="submit" variant="outline">검색</Button>
        <Button type="button" variant="ghost" onClick={() => { setParams({}); onReload() }}>초기화</Button>
        <Button type="button" variant="outline" onClick={onReload}>새로고침</Button>
      </form>
      <div aria-live="polite" aria-busy={!result && !error}>
        {error ? <div role="alert" className="space-y-3 rounded-lg border p-5">
          <p className="text-red-600">{error}</p><Button variant="outline" onClick={onReload}>다시 시도</Button>
        </div> : !result ? <p className="py-10 text-center text-gray-500">검색 결과를 불러오는 중입니다.</p> : <>
          <p className="mb-3 text-sm text-gray-600">검색 결과 {result.pagination.total}건</p>
          <div className="rounded-lg border border-gray-200 bg-white">
            <Table>
              <TableHeader><TableRow><TableHead>제목</TableHead><TableHead>소유자</TableHead><TableHead>부서</TableHead><TableHead>수정일</TableHead></TableRow></TableHeader>
              <TableBody>
                {result.items.map((item) => <TableRow key={item.id}>
                  <TableCell><Link className="font-medium text-emerald-800 underline-offset-4 hover:underline focus-visible:underline" to={`/documents/${item.id}`}>{item.title}</Link></TableCell>
                  <TableCell>{item.owner.username}</TableCell><TableCell>{item.department?.name ?? "부서 없음"}</TableCell>
                  <TableCell>{item.updated_at?.slice(0, 10) ?? "—"}</TableCell>
                </TableRow>)}
                {result.items.length === 0 && <TableRow><TableCell colSpan={4} className="py-10 text-center text-gray-500">조건에 맞는 문서가 없습니다.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </div>
          <nav aria-label="검색 결과 페이지" className="mt-4 flex items-center justify-end gap-3">
            <Button variant="outline" disabled={result.pagination.page <= 1} onClick={() => changePage(result.pagination.page - 1)}>이전</Button>
            <span className="text-sm">{result.pagination.page} / {Math.max(1, result.pagination.pages)} 페이지</span>
            <Button variant="outline" disabled={result.pagination.page >= result.pagination.pages} onClick={() => changePage(result.pagination.page + 1)}>다음</Button>
          </nav>
        </>}
      </div>
    </div>
  )
}
