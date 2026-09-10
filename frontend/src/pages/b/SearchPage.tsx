import { useState } from "react"
import { SearchIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

/**
 * 검색 결과  ·  /search  ·  Document
 *
 * 전역 검색어에 대한 결과를 필터와 함께 보여주는 화면.
 * - 결과 클릭 → 자료 상세
 * - 주의: 검색어가 SQL로 직접 조립되면 SQLi 지점.
 *         검색 결과 자체도 권한 범위 밖 문서를 노출하면 안 됨.
 */

type SearchResult = {
  id: number
  title: string
  snippet: string
  department: string
  owner: string
  updatedAt: string
}

// TODO: API 연동 시 GET /api/search?q=&department=&type=&owner=&from=&to= 로 교체
const MOCK_RESULTS: SearchResult[] = [
  {
    id: 301,
    title: "보안 점검 체크리스트 2026",
    snippet: "…분기별 보안 점검 항목과 담당자, 조치 기한을 정리한 문서입니다…",
    department: "개발팀",
    owner: "김주원",
    updatedAt: "2026-09-04",
  },
  {
    id: 302,
    title: "사내 자료공유 정책 개정안",
    snippet: "…자료 공개범위(개인/팀/전체) 기준과 공유 승인 절차를 개정…",
    department: "인사팀",
    owner: "최민지",
    updatedAt: "2026-08-30",
  },
  {
    id: 303,
    title: "분기 실적 보안 브리핑",
    snippet: "…접근 로그 분석 결과와 이상 징후 대응 내역을 포함…",
    department: "영업팀",
    owner: "정하윤",
    updatedAt: "2026-09-01",
  },
]

/** 검색어와 일치하는 부분을 강조 */
function Highlight({ text, term }: { text: string; term: string }) {
  if (!term) return <>{text}</>
  const idx = text.indexOf(term)
  if (idx === -1) return <>{text}</>
  return (
    <>
      {text.slice(0, idx)}
      <mark className="rounded bg-[#E1F5EE] px-0.5 text-[#085041]">
        {text.slice(idx, idx + term.length)}
      </mark>
      {text.slice(idx + term.length)}
    </>
  )
}

export default function SearchPage() {
  const [query, setQuery] = useState("보안")
  const [department, setDepartment] = useState("")
  const [fileType, setFileType] = useState("")
  const [owner, setOwner] = useState("")

  const results = MOCK_RESULTS.filter(
    (r) => !query || r.title.includes(query) || r.snippet.includes(query),
  )

  const selectClass =
    "h-9 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"

  return (
    <div>
      <header className="mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-gray-900">검색 결과</h1>
          <code className="rounded border border-gray-200 bg-gray-50 px-2 py-0.5 font-mono text-xs text-gray-500">
            /search
          </code>
        </div>
        <p className="mt-1.5 max-w-xl text-sm text-gray-500">
          자료 제목과 본문에서 검색합니다. 결과는 내가 접근 가능한 문서로 제한됩니다.
        </p>
      </header>

      {/* 검색어 입력 */}
      <div className="relative mb-5 max-w-2xl">
        <SearchIcon className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gray-400" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="검색어를 입력하세요"
          className="h-10 pl-9"
        />
      </div>

      <div className="grid gap-6 md:grid-cols-[180px_1fr]">
        {/* 필터 */}
        <aside className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">부서</label>
            <select
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              className={selectClass}
            >
              <option value="">전체</option>
              <option value="dev">개발팀</option>
              <option value="hr">인사팀</option>
              <option value="sales">영업팀</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">파일 유형</label>
            <select
              value={fileType}
              onChange={(e) => setFileType(e.target.value)}
              className={selectClass}
            >
              <option value="">전체</option>
              <option value="pdf">PDF</option>
              <option value="doc">문서</option>
              <option value="sheet">스프레드시트</option>
              <option value="image">이미지</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">날짜 범위</label>
            <div className="flex flex-col gap-1.5">
              <input type="date" className={selectClass} />
              <input type="date" className={selectClass} />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">소유자</label>
            <Input
              value={owner}
              onChange={(e) => setOwner(e.target.value)}
              placeholder="이름"
              className="h-9"
            />
          </div>
        </aside>

        {/* 결과 리스트 */}
        <section>
          {results.length === 0 ? (
            <div className="rounded-lg border border-dashed border-gray-300 bg-white py-16 text-center">
              <p className="text-sm font-medium text-gray-700">검색 결과가 없습니다</p>
              <p className="mt-1 text-xs text-gray-500">
                다른 검색어를 입력하거나 필터를 조정해 보세요.
              </p>
            </div>
          ) : (
            <ul className="space-y-3">
              {results.map((r) => (
                // TODO: 라우팅 연결 후 onClick → navigate(`/documents/${r.id}`)
                <li
                  key={r.id}
                  className="cursor-pointer rounded-lg border border-gray-200 bg-white p-4 hover:border-gray-300"
                >
                  <h3 className="text-sm font-semibold text-gray-900">
                    <Highlight text={r.title} term={query} />
                  </h3>
                  <p className="mt-1 text-sm text-gray-600">
                    <Highlight text={r.snippet} term={query} />
                  </p>
                  <p className="mt-2 text-xs text-gray-400">
                    {r.department} · {r.owner} · {r.updatedAt}
                  </p>
                </li>
              ))}
            </ul>
          )}

          <div className="mt-4 flex justify-center">
            <Button variant="outline" size="sm" disabled>
              다음 페이지
            </Button>
          </div>
        </section>
      </div>
    </div>
  )
}
