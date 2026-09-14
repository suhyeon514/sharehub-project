import { useEffect, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { XIcon } from "lucide-react"
import ShareRow from "@/components/sharing/ShareRow"
import { Button } from "@/components/ui/button"
import ShareCreateForm from "@/components/sharing/ShareCreateForm"
import { Separator } from "@/components/ui/separator"
import { ApiError, apiGet } from "@/lib/api"

type Permission = "view" | "download" | "edit"
type ShareList = {
  document: { id: number; title: string }
  shares: { id: number; shared_with: { id: number; username: string }; permission: Permission }[]
}
type LoadState =
  | { status: "loading" }
  | { status: "blocked"; message: string }
  | { status: "success"; data: ShareList }
  | { status: "error"; message: string; retryable: boolean }


export default function SharePage() {
  const { id = "" } = useParams()
  const [attempt, setAttempt] = useState(0)
  // 문서 이동·재시도마다 이전 결과를 비우고 새 요청을 시작한다.
  return <ShareContent key={`${id}:${attempt}`} id={id} onRetry={() => setAttempt((value) => value + 1)} />
}

function ShareContent({ id, onRetry }: { id: string; onRetry: () => void }) {
  const navigate = useNavigate()
  const validId = /^[1-9]\d*$/.test(id) && Number.isSafeInteger(Number(id))
  const [state, setState] = useState<LoadState>(() => validId
    ? { status: "loading" }
    : { status: "error", message: "올바른 문서 주소가 아닙니다.", retryable: false })

  useEffect(() => {
    if (!validId) return
    const controller = new AbortController()
    apiGet<ShareList>(`/api/documents/${id}/shares`, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState({ status: "success", data })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof ApiError && error.status === 401) {
          navigate("/login", { replace: true, state: { from: `/documents/${id}/share` } })
          return
        }
        if (error instanceof ApiError && error.code === "DOCUMENT_BLOCKED") {
          setState({ status: "blocked", message: error.message })
          return
        }
        setState({
          status: "error",
          message: error instanceof ApiError ? error.message : "서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.",
          retryable: !(error instanceof ApiError) || error.status >= 500,
        })
      })
    return () => controller.abort()
  }, [id, validId, navigate])

  const close = () => navigate("/documents/mine")
  return (
    <div>
      <header className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900">자료 공유</h1>
        <p className="mt-1.5 text-sm text-gray-500">개별 공유 중인 사용자와 부여된 권한을 확인하세요.</p>
      </header>
      <div className="rounded-xl border border-gray-200 bg-gray-100 p-4 sm:p-8">
        <section aria-labelledby="share-title" className="mx-auto w-full max-w-2xl rounded-2xl bg-white p-5 sm:p-7 shadow-xl ring-1 ring-black/10">
          <div className="flex items-center justify-between">
            <h2 id="share-title" className="text-base font-semibold text-gray-900">자료 공유하기</h2>
            <Button variant="ghost" size="icon-sm" aria-label="닫기" onClick={close}><XIcon /></Button>
          </div>
          {state.status === "success" && <p className="mt-2 break-words text-sm font-medium text-gray-700">{state.data.document.title}</p>}
          {state.status === "success" && (
            <ShareCreateForm
              documentId={id}
              shares={state.data.shares}
              onBlocked={(message) => setState({ status: "blocked", message })}
              onCreated={(share) => setState((current) => current.status === "success"
                ? { status: "success", data: { ...current.data, shares: [...current.data.shares, share] } }
                : current)}
            />
          )}
          <Separator className="my-4" />
          <div aria-live="polite" aria-busy={state.status === "loading"}>
            {state.status !== "blocked" && <p className="mb-3 text-sm font-semibold text-gray-600">
              공유 중인 사용자{state.status === "success" ? ` ${state.data.shares.length}명` : ""}
            </p>}
            {state.status === "blocked" && (
              <div role="alert" className="space-y-2 rounded-lg bg-amber-50 p-4">
                <p className="text-sm font-semibold text-amber-900">공유가 제한된 문서입니다.</p>
                <p className="text-sm text-amber-900">{state.message}</p>
                <p className="text-sm text-gray-600">차단 중에는 공유 목록 조회와 공유 추가·권한 변경·해제를 할 수 없습니다.</p>
              </div>
            )}
            {state.status === "loading" && <p className="py-4 text-sm text-gray-500">공유 목록을 불러오는 중입니다.</p>}
            {state.status === "error" && (
              <div role="alert" className="space-y-3 py-3">
                <p className="text-sm text-red-600">{state.message}</p>
                {state.retryable && <Button variant="outline" size="sm" onClick={onRetry}>다시 시도</Button>}
              </div>
            )}
            {state.status === "success" && (state.data.shares.length === 0
              ? <p className="py-4 text-sm text-gray-500">개별 공유 중인 사용자가 없습니다.</p>
              : <ul className="max-h-80 space-y-3 overflow-y-auto">
                {state.data.shares.map((share) => (
                  <ShareRow key={`${share.id}:${share.permission}`} documentId={id} share={share}
                    onBlocked={(message) => setState({ status: "blocked", message })}
                    onUpdated={(updated) => setState((current) => current.status === "success"
                      ? { status: "success", data: { ...current.data, shares: current.data.shares.map((item) => item.id === updated.id ? updated : item) } }
                      : current)}
                    onDeleted={(shareId) => setState((current) => current.status === "success"
                      ? { status: "success", data: { ...current.data, shares: current.data.shares.filter((item) => item.id !== shareId) } }
                      : current)}
                  />
                ))}
              </ul>)}
          </div>
          <div className="mt-6 flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={close}>{state.status === "blocked" ? "내 자료로 돌아가기" : "취소"}</Button>
          </div>
        </section>
      </div>
    </div>
  )
}
