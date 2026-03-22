import { cn } from '@/lib/utils'
import type { ProjectStatus } from '@/types'

const STATUS_COLORS: Record<ProjectStatus, string> = {
  ready: 'bg-green-500',
  generating: 'bg-blue-500 animate-pulse-status',
  error: 'bg-red-500',
  aborted: 'bg-amber-500',
}

const STATUS_LABELS: Record<ProjectStatus, string> = {
  ready: 'Ready',
  generating: 'Generating',
  error: 'Error',
  aborted: 'Aborted',
}

const STATUS_TITLES: Record<ProjectStatus, string> = {
  ready: 'Documentation is ready',
  generating: 'Generation in progress',
  error: 'Generation failed',
  aborted: 'Generation was aborted',
}

interface StatusDotProps {
  status: ProjectStatus
  className?: string
  showTitle?: boolean
}

export default function StatusDot({ status, className, showTitle = true }: StatusDotProps) {
  return (
    <span
      role="img"
      className={cn('inline-block w-2.5 h-2.5 rounded-full shrink-0', STATUS_COLORS[status], className)}
      aria-label={STATUS_LABELS[status]}
      title={showTitle ? STATUS_TITLES[status] : undefined}
    />
  )
}
