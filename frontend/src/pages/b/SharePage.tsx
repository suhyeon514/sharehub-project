import { useState } from "react"
import { XIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"

/**
 * 자료 공유  ·  /documents/:id/share  ·  DocumentShare
 *
 * 자료 상세 화면 위에 뜨는 모달. 특정 사용자에게 권한을 부여한다.
 * (라우팅 통합 시 <Dialog> 로 /documents/:id 위에 마운트 — 여기서는 뼈대만 구성)
 * - 공유 버튼 → DocumentShare 레코드 생성 / 제거 → 공유 취소
 * - 주의: 공유 권한을 부여할 수 있는 주체가 소유자 / Admin 으로 한정되는지가 핵심 검증 포인트.
 */

type Permission = "view" | "download" | "edit"

type Share = {
  id: number
  name: string
  permission: Permission
}

const PERMISSION_LABEL: Record<Permission, string> = {
  view: "조회",
  download: "다운로드",
  edit: "편집",
}

// TODO: API 연동 시 GET /api/documents/:id/shares 응답으로 교체
const MOCK_SHARES: Share[] = [
  { id: 1, name: "이수현", permission: "edit" },
  { id: 2, name: "박서준", permission: "view" },
]

// TODO: 사용자 검색 자동완성 결과 (GET /api/users?q=)
const MOCK_USER_SUGGESTIONS = ["김주원", "최민지", "정하윤", "한지민"]

export default function SharePage() {
  const [query, setQuery] = useState("")
  const [permission, setPermission] = useState<Permission>("view")

  const suggestions = query
    ? MOCK_USER_SUGGESTIONS.filter((name) => name.includes(query))
    : []

  return (
    <div>
      <header className="mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-gray-900">자료 공유</h1>
          <code className="rounded border border-gray-200 bg-gray-50 px-2 py-0.5 font-mono text-xs text-gray-500">
            /documents/:id/share
          </code>
        </div>
        <p className="mt-1.5 max-w-xl text-sm text-gray-500">
          자료 상세 위에 모달로 표시됩니다. 사용자를 찾아 권한을 지정해 공유하세요.
        </p>
      </header>

      {/* 모달 미리보기 — 뒤 배경은 자료 상세(흐림 처리) 자리표시자 */}
      <div className="relative overflow-hidden rounded-xl border border-gray-200">
        <div className="pointer-events-none min-h-[420px] bg-gray-50 p-6 blur-[1px]">
          <div className="h-6 w-48 rounded bg-gray-200" />
          <div className="mt-4 h-40 rounded bg-gray-200/70" />
          <div className="mt-4 h-4 w-2/3 rounded bg-gray-200" />
          <div className="mt-2 h-4 w-1/2 rounded bg-gray-200" />
        </div>
        <div className="absolute inset-0 bg-black/10" />

        <div className="absolute left-1/2 top-1/2 w-[min(360px,calc(100%-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-xl bg-white p-5 shadow-xl ring-1 ring-black/10">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-gray-900">자료 공유하기</h2>
            <Button variant="ghost" size="icon-sm" aria-label="닫기" disabled>
              <XIcon />
            </Button>
          </div>

          {/* 사용자 검색 (자동완성) */}
          <div className="mt-4">
            <label className="mb-1 block text-xs font-medium text-gray-500">
              사용자 검색
            </label>
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="이름 또는 아이디"
              className="h-9"
            />
            {suggestions.length > 0 && (
              <ul className="mt-1 rounded-lg border border-gray-200 bg-white py-1 text-sm shadow-sm">
                {suggestions.map((name) => (
                  <li
                    key={name}
                    className="cursor-pointer px-3 py-1.5 text-gray-700 hover:bg-gray-50"
                  >
                    {name}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* 권한 선택 */}
          <div className="mt-3">
            <label className="mb-1 block text-xs font-medium text-gray-500">권한</label>
            <div className="flex gap-1.5">
              {(Object.keys(PERMISSION_LABEL) as Permission[]).map((p) => (
                <Button
                  key={p}
                  type="button"
                  size="sm"
                  variant={permission === p ? "default" : "outline"}
                  className={
                    permission === p ? "bg-[#0F6E56] text-white hover:bg-[#0d5f4a]" : ""
                  }
                  onClick={() => setPermission(p)}
                >
                  {PERMISSION_LABEL[p]}
                </Button>
              ))}
            </div>
          </div>

          <Separator className="my-4" />

          {/* 이미 공유된 사용자 */}
          <div>
            <p className="mb-2 text-xs font-medium text-gray-500">공유 중인 사용자</p>
            <ul className="space-y-1.5">
              {MOCK_SHARES.map((share) => (
                <li
                  key={share.id}
                  className="flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50 px-3 py-2"
                >
                  <span className="text-sm text-gray-800">{share.name}</span>
                  <span className="flex items-center gap-2">
                    <Badge variant="outline">{PERMISSION_LABEL[share.permission]}</Badge>
                    <Button variant="ghost" size="xs" className="text-red-600" disabled>
                      제거
                    </Button>
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="mt-5 flex justify-end gap-2">
            <Button variant="outline" size="sm" disabled>
              취소
            </Button>
            <Button
              size="sm"
              className="bg-[#0F6E56] text-white hover:bg-[#0d5f4a]"
              disabled
            >
              공유
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
