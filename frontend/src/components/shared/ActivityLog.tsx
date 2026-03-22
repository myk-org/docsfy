import { useRef, useEffect } from 'react'
import { CheckCircle2, Loader2, XCircle, Circle } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { LogEntry, ProjectStatus } from '@/types'

interface ActivityLogProps {
  entries: LogEntry[]
  status: ProjectStatus
}

const ENTRY_ICONS = {
  done: <CheckCircle2 className="size-3.5 text-green-500 shrink-0" />,
  active: <Loader2 className="size-3.5 text-blue-500 animate-spin shrink-0" />,
  error: <XCircle className="size-3.5 text-red-500 shrink-0" />,
  pending: <Circle className="size-3.5 text-muted-foreground opacity-50 shrink-0" />,
} as const

function StatusHeader({ status }: { status: ProjectStatus }) {
  if (status === 'generating') {
    return (
      <div className="flex items-center gap-2 text-sm font-medium text-blue-500" title="Generation in progress">
        <Loader2 className="size-4 animate-spin" />
        Generating...
      </div>
    )
  }
  if (status === 'ready') {
    return (
      <div className="text-sm font-medium text-green-500" title="All pages generated successfully">Complete</div>
    )
  }
  if (status === 'error') {
    return (
      <div className="text-sm font-medium text-red-500" title="Generation encountered an error">Failed</div>
    )
  }
  if (status === 'aborted') {
    return (
      <div className="text-sm font-medium text-amber-500" title="Generation was stopped by user">Aborted</div>
    )
  }
  return null
}

export default function ActivityLog({ entries, status }: ActivityLogProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const isAtBottomRef = useRef(true)

  // Track whether user is scrolled near the bottom
  useEffect(() => {
    const scrollEl = scrollAreaRef.current?.querySelector('[data-radix-scroll-area-viewport]') as HTMLElement | null
    if (!scrollEl) return
    function handleScroll() {
      if (!scrollEl) return
      const threshold = 40
      isAtBottomRef.current = scrollEl.scrollHeight - scrollEl.scrollTop - scrollEl.clientHeight < threshold
    }
    scrollEl.addEventListener('scroll', handleScroll, { passive: true })
    return () => scrollEl.removeEventListener('scroll', handleScroll)
  }, [])

  // Only auto-scroll if user is already at the bottom
  useEffect(() => {
    if (isAtBottomRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [entries.length])

  return (
    <div className="border rounded-lg">
      <div className="flex items-center justify-between px-3 py-2 border-b bg-muted/30">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Activity Log
        </span>
        <StatusHeader status={status} />
      </div>
      <ScrollArea ref={scrollAreaRef} className="h-[300px]">
        <div className="p-3 flex flex-col gap-1.5">
          {entries.map((entry) => (
            <div
              key={entry.id}
              className="flex items-start gap-2 animate-fade-in"
            >
              <div className="mt-0.5">{ENTRY_ICONS[entry.type]}</div>
              <span
                className="text-[0.8rem] leading-relaxed font-mono"
              >
                {entry.message}
              </span>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>
    </div>
  )
}
