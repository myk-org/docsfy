import { Badge } from '@/components/ui/badge'

const ROLE_STYLES: Record<string, string> = {
  admin: 'bg-signal-green/10 text-signal-green border-signal-green/20',
  user: 'bg-signal-blue/10 text-signal-blue border-signal-blue/20',
}
const DEFAULT_ROLE_STYLE = 'bg-surface-elevated text-text-tertiary border-border-default'

export default function RoleBadge({ role }: { role: string }) {
  return (
    <Badge className={ROLE_STYLES[role] || DEFAULT_ROLE_STYLE}>
      {role}
    </Badge>
  )
}
