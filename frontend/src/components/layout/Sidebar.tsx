import { NavLink } from "react-router-dom"

const menuItems = [
  { label: "대시보드", to: "/" },
  { label: "내 자료", to: "/documents/mine" },
  { label: "자료 업로드", to: "/documents/upload" },
  { label: "공유받은 자료", to: "/documents/shared" },
  { label: "팀 자료", to: "/documents/team" },
  { label: "검색", to: "/search" },
  { label: "관리자", to: "/admin" },
]

export default function Sidebar() {
  return (
    <aside className="flex h-screen w-64 flex-col bg-[#0F6E56] px-4 py-6 text-white">
      <div className="mb-8 px-2">
        <h1 className="text-2xl font-bold">ShareHub</h1>
        <p className="mt-1 text-sm text-white/70">
          사내 자료공유 서비스
        </p>
      </div>

      <nav className="flex flex-1 flex-col gap-2">
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
      </nav>

      <div className="border-t border-white/20 pt-4">
        <p className="px-2 text-xs text-white/60">
          ShareHub Project
        </p>
      </div>
    </aside>
  )
}