export default function Header() {
  return (
    <header className="flex h-16 items-center justify-between border-b border-gray-200 bg-white px-6">
      {/* 검색 영역 */}
      <div className="w-full max-w-md">
        <div className="relative">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400"
            aria-hidden="true"
          >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>

          <input
            type="search"
            placeholder="자료 또는 사용자 검색"
            className="h-10 w-full rounded-lg border border-gray-200 bg-gray-50 pl-10 pr-4 text-sm outline-none transition focus:border-[#0F6E56] focus:bg-white focus:ring-2 focus:ring-[#0F6E56]/10"
          />
        </div>
      </div>

      {/* 사용자 영역 */}
      <div className="ml-6 flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#0F6E56] text-sm font-semibold text-white">
          A
        </div>

        <div className="hidden sm:block">
          <p className="text-sm font-medium text-gray-800">
            admin
          </p>
          <p className="text-xs text-gray-500">
            관리자
          </p>
        </div>
      </div>
    </header>
  )
}