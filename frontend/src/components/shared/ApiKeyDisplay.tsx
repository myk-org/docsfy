import { useState, useRef, useEffect } from 'react'
import { AlertTriangle, Check, Copy } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { COPY_FEEDBACK_MS } from '@/lib/constants'

interface ApiKeyDisplayProps {
  username: string
  role: string
  password: string
  onDismiss: () => void
}

export default function ApiKeyDisplay({
  username,
  role,
  password,
  onDismiss,
}: ApiKeyDisplayProps) {
  const [copied, setCopied] = useState(false)
  const [copyFailed, setCopyFailed] = useState(false)
  const mountedRef = useRef(true)

  useEffect(() => {
    return () => { mountedRef.current = false }
  }, [])

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(password)
      setCopied(true)
      setTimeout(() => { if (mountedRef.current) setCopied(false) }, COPY_FEEDBACK_MS)
    } catch {
      // Clipboard API may be unavailable (e.g. non-HTTPS or denied permission)
      setCopyFailed(true)
      setTimeout(() => { if (mountedRef.current) setCopyFailed(false) }, COPY_FEEDBACK_MS)
    }
  }

  return (
    <div className="flex flex-col gap-4 rounded-lg border p-4">
      {/* Warning banner */}
      <div className="flex items-center gap-2 rounded-md border border-signal-orange/30 bg-signal-orange/10 px-3 py-2 text-sm text-signal-orange">
        <AlertTriangle className="size-4 shrink-0" />
        <span className="font-medium">
          Save this password &mdash; it won&apos;t be shown again!
        </span>
      </div>

      {/* User info */}
      <div className="flex flex-col gap-2 text-sm">
        <div>
          <span className="text-text-secondary">Username: </span>
          <span className="font-bold">{username}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-text-secondary">Role: </span>
          <RoleBadge role={role} />
        </div>
        <div>
          <span className="text-text-secondary">Password: </span>
          <code className="font-mono break-all">{password}</code>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <Button variant="outline" size="sm" onClick={handleCopy}>
          {copied ? (
            <>
              <Check className="size-4 mr-1.5" />
              Copied!
            </>
          ) : copyFailed ? (
            <>
              <Copy className="size-4 mr-1.5" />
              Copy failed — select manually
            </>
          ) : (
            <>
              <Copy className="size-4 mr-1.5" />
              Copy Password
            </>
          )}
        </Button>
        <Button size="sm" onClick={onDismiss}>
          Done
        </Button>
      </div>
    </div>
  )
}

const ROLE_STYLES: Record<string, string> = {
  admin: 'bg-signal-green/10 text-signal-green border-signal-green/20',
  user: 'bg-signal-blue/10 text-signal-blue border-signal-blue/20',
}
const DEFAULT_ROLE_STYLE = 'bg-surface-elevated text-text-tertiary border-border-default'

function RoleBadge({ role }: { role: string }) {
  return (
    <Badge className={ROLE_STYLES[role] || DEFAULT_ROLE_STYLE}>
      {role}
    </Badge>
  )
}
