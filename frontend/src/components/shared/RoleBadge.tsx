import { Badge } from '@/components/ui/badge'
import { BADGE_STYLES } from '@/lib/constants'

const ROLE_BADGE_MAP = new Map<string, string>([
  ['admin', BADGE_STYLES.green],
  ['user', BADGE_STYLES.blue],
])

export default function RoleBadge({ role }: { role: string }) {
  return (
    <Badge className={ROLE_BADGE_MAP.get(role) ?? BADGE_STYLES.muted}>
      {role}
    </Badge>
  )
}
