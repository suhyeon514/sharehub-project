import { useRef, type ReactNode } from "react"
import { Dialog } from "@base-ui/react/dialog"

export default function AdminModal({ title, busy, onClose, children }: {
  title: string
  busy: boolean
  onClose: () => void
  children: ReactNode
}) {
  const returnFocus = useRef<HTMLElement | null>(
    document.activeElement instanceof HTMLElement ? document.activeElement : null,
  )
  return <Dialog.Root open onOpenChange={(open) => { if (!open && !busy) onClose() }}>
    <Dialog.Portal>
      <Dialog.Backdrop className="fixed inset-0 z-[100] bg-black/40" />
      <Dialog.Popup finalFocus={returnFocus} className="fixed left-1/2 top-1/2 z-[101] flex max-h-[calc(100dvh-3rem)] w-[calc(100%-2rem)] max-w-2xl -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl outline-none">
        <div className="flex items-start justify-between border-b border-gray-100 px-6 py-5">
          <Dialog.Title className="text-xl font-bold text-gray-900">{title}</Dialog.Title>
          <button type="button" aria-label={`${title} 창 닫기`} disabled={busy} onClick={onClose}
            className="rounded-md px-2 py-1 text-xl leading-none text-gray-400 transition hover:bg-gray-100 hover:text-gray-700 disabled:cursor-not-allowed disabled:opacity-50">×</button>
        </div>
        <div className="min-h-0 space-y-4 overflow-y-auto overscroll-contain px-6 py-5" aria-busy={busy}>{children}</div>
      </Dialog.Popup>
    </Dialog.Portal>
  </Dialog.Root>
}
