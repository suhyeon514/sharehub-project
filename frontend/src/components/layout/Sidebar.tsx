import { useState } from "react"
import { ChevronDownIcon } from "lucide-react"
import { Link, NavLink, useLocation } from "react-router-dom"

const menuItems = [
  { label: "대시보드", to: "/" },
  { label: "내 자료", to: "/documents/mine" },
  { label: "자료 업로드", to: "/documents/upload" },
  { label: "공유받은 자료", to: "/documents/shared" },
  { label: "팀 자료", to: "/documents/team" },
  { label: "검색", to: "/search" },
]

export default function Sidebar() {
  const location = useLocation()
  const inAdmin = location.pathname === "/admin"
  const [adminExpanded, setAdminExpanded] = useState(inAdmin)
  const tab = new URLSearchParams(location.search).get("tab")
  const activeTab = tab === "documents" || tab === "activity-logs" || tab === "unblock-requests" ? tab : "users"
  let isAdmin = false
  try { isAdmin = JSON.parse(localStorage.getItem("sharehub_user") ?? "null")?.role === "admin" } catch { /* 메뉴 표시용이며 API에서 최종 검사한다. */ }
  return (
    <aside className="flex h-full w-64 shrink-0 flex-col bg-[#0F6E56] px-4 py-6 text-white">
      <div className="mb-8 px-2">
        <h1 className="text-2xl font-bold">ShareHub</h1>
        <p className="mt-1 text-sm text-white/70">
          사내 자료공유 서비스
        </p>
      </div>

      <nav className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto">
        {menuItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              [
                "rounded-lg px-4 py-3 text-sm font-medium transition",
                isActive
                  ? "bg-white text-[#0F6E56]"
                  : "text-white/90 hover:bg-white/10",
              ].join(" ")
            }
          >
            {item.label}
          </NavLink>
        ))}
        {isAdmin && (
          <div>
            <button type="button" aria-expanded={adminExpanded} aria-controls="admin-submenu" onClick={() => setAdminExpanded((expanded) => !expanded)} className={`flex w-full items-center justify-between rounded-lg px-4 py-3 text-sm font-medium transition ${inAdmin ? "bg-white text-[#0F6E56]" : "text-white/90 hover:bg-white/10"}`}>
              관리자
              <ChevronDownIcon aria-hidden="true" className={`size-4 transition-transform ${adminExpanded ? "" : "-rotate-90"}`} />
            </button>
              <ul id="admin-submenu" hidden={!adminExpanded} aria-label="관리자 하위 메뉴" className="mb-3 ml-3 mt-2 space-y-1 border-l border-white/25 pl-1">
                {[
                  { value: "users", label: "사용자" },
                  { value: "documents", label: "문서" },
                  { value: "unblock-requests", label: "소명 관리" },
                  { value: "activity-logs", label: "활동 로그" },
                ].map((item) => (
                  <li key={item.value}>
                    <Link to={`/admin?tab=${item.value}`} aria-current={inAdmin && activeTab === item.value ? "page" : undefined}
                      className={`block rounded-lg px-3 py-2 text-sm transition ${inAdmin && activeTab === item.value ? "bg-white/20 font-semibold text-white" : "text-white/85 hover:bg-white/10"}`}>
                      {item.label}
                    </Link>
                  </li>
                ))}
              </ul>
          </div>
        )}
      </nav>

      <div className="border-t border-white/20 pt-4">
        <p className="px-2 text-xs text-white/60">
          ShareHub Project
        </p>
      </div>
    </aside>
  )
}
