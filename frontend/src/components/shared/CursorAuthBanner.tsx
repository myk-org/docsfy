import { AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ProviderStatus } from '@/types'

interface CursorAuthBannerProps {
  status: ProviderStatus
  className?: string
}

const _TITLE_BY_REASON: Record<string, string> = {
  agent_missing: 'Cursor agent missing',
  no_models: 'No Cursor models found',
  unavailable: 'Cursor unavailable',
  auth_expired: 'Cursor browser login expired',
  api_key_not_applied: 'Cursor unavailable (API key is set)', // pragma: allowlist secret
}

/** Notice when Cursor models are unavailable (admin gets detailed diagnosis). */
export default function CursorAuthBanner({ status, className }: CursorAuthBannerProps) {
  // Credential flag is admin-only; its absence means the API redacted it.
  const redacted = typeof status.has_api_key !== 'boolean' // pragma: allowlist secret
  const keyConfigured =
    status.has_api_key === true || status.reason === 'api_key_not_applied' // pragma: allowlist secret

  let title: string
  let hint: string
  if (redacted) {
    title = 'Cursor unavailable'
    hint = status.hint || 'Cursor is unavailable. Contact an administrator.'
  } else if (status.reason && _TITLE_BY_REASON[status.reason]) {
    title = _TITLE_BY_REASON[status.reason]
    hint =
      status.hint ||
      (keyConfigured
        ? 'CURSOR_API_KEY is set (it does not expire) but Cursor is unavailable. Check sidecar env/restart/network.'
        : 'Cursor is unavailable. Check sidecar logs, network, and agent/CLI health.')
  } else if (keyConfigured) {
    title = 'Cursor unavailable (API key is set)'
    hint =
      status.hint ||
      'CURSOR_API_KEY is set (it does not expire) but Cursor is unavailable. Check sidecar env/restart/network.'
  } else {
    title = 'Cursor unavailable'
    hint =
      status.hint ||
      'Cursor is unavailable. Check sidecar logs, network, and agent/CLI health.'
  }

  const showApiKeyPreference =
    !redacted && !keyConfigured && status.reason === 'auth_expired'

  return (
    <div
      className={cn(
        'rounded-lg border border-signal-orange/30 bg-signal-orange/10 p-3 flex items-start gap-3',
        className,
      )}
      role="status"
      data-testid="cursor-auth-banner"
    >
      <AlertTriangle className="h-4 w-4 text-signal-orange shrink-0 mt-0.5" />
      <div className="flex flex-col gap-1 min-w-0">
        <p className="text-sm font-medium text-text-primary">
          {title}
          {status.reason ? ` (${status.reason})` : ''}
        </p>
        <p className="text-xs text-text-secondary break-words">{hint}</p>
        {showApiKeyPreference && (
          <p className="text-xs text-text-tertiary">
            <code className="text-caption font-mono">CURSOR_API_KEY</code> does not expire.
            Prefer it over <code className="text-caption font-mono">agent login</code> on Dev/prod.
          </p>
        )}
      </div>
    </div>
  )
}
