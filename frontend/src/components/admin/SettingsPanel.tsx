import { useState, useEffect, useRef } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import Combobox from '@/components/shared/Combobox'
import { api } from '@/lib/api'
import { VALID_PROVIDERS, TOAST_DEFAULT_MS, TOAST_ERROR_MS } from '@/lib/constants'
import { ApiError } from '@/types'
import type { AvailableModels, AdminSettings, AdminSettingsResponse } from '@/types'

interface SettingsPanelProps {
  availableModels: AvailableModels
  onSettingsSaved?: () => void
}

function EnvWarning({ envVarName }: { envVarName: string }) {
  return (
    <p className="text-xs text-signal-orange mt-1">
      ⚠ Controlled by environment variable <code className="font-mono">{envVarName}</code>. Changes will be lost on server restart — remove the env var to make this setting persistent.
    </p>
  )
}

export default function SettingsPanel({ availableModels, onSettingsSaved }: SettingsPanelProps) {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [envOverrides, setEnvOverrides] = useState<Record<string, string>>({})

  const [provider, setProvider] = useState('')
  const [model, setModel] = useState('')
  const [visionProvider, setVisionProvider] = useState('')
  const [visionModel, setVisionModel] = useState('')
  const [timeout, setTimeout_] = useState(60)
  const [concurrentPages, setConcurrentPages] = useState(10)

  const initialRef = useRef<AdminSettings | null>(null)

  useEffect(() => {
    loadSettings()
  }, [])

  async function loadSettings() {
    setFetchError(null)
    setLoading(true)
    try {
      const data = await api.get<AdminSettingsResponse>('/api/admin/settings')
      const s = data.settings
      setProvider(s.default_ai_provider || '')
      setModel(s.default_ai_model || '')
      setVisionProvider(s.vision_provider || '')
      setVisionModel(s.vision_model || '')
      setTimeout_(s.ai_cli_timeout)
      setConcurrentPages(s.max_concurrent_pages)
      setEnvOverrides(data.env_overrides)
      initialRef.current = { ...s }
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'Failed to load settings'
      setFetchError(detail)
    } finally {
      setLoading(false)
    }
  }

  function handleProviderChange(value: string | null) {
    if (value === null) return
    const v = value === '__clear__' ? '' : value
    setProvider(v)
    if (!v) {
      setModel('')
    } else {
      const models = availableModels[v]
      if (!models?.some(m => m.id === model)) {
        setModel('')
      }
    }
  }

  function handleVisionProviderChange(value: string | null) {
    if (value === null) return
    const v = value === '__clear__' ? '' : value
    setVisionProvider(v)
    if (!v) {
      setVisionModel('')
    } else {
      const models = availableModels[v]
      if (!models?.some(m => m.id === visionModel)) {
        setVisionModel('')
      }
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()

    const current: AdminSettings = {
      default_ai_provider: provider,
      default_ai_model: model,
      vision_provider: visionProvider,
      vision_model: visionModel,
      ai_cli_timeout: timeout,
      max_concurrent_pages: concurrentPages,
    }

    const initial = initialRef.current
    if (!initial) return

    const changed: Partial<AdminSettings> = {}
    for (const key of Object.keys(current) as (keyof AdminSettings)[]) {
      if (current[key] !== initial[key]) {
        ;(changed as Record<string, unknown>)[key] = current[key]
      }
    }

    if (Object.keys(changed).length === 0) {
      toast.info('No changes to save', { duration: TOAST_DEFAULT_MS })
      return
    }

    setSaving(true)
    try {
      await api.put('/api/admin/settings', { settings: changed })
      toast.success('Settings saved', { duration: TOAST_DEFAULT_MS })
      initialRef.current = { ...current }
      onSettingsSaved?.()
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'Failed to save settings'
      toast.error(detail, { duration: TOAST_ERROR_MS })
    } finally {
      setSaving(false)
    }
  }

  const modelOptions = provider
    ? (availableModels[provider] ?? []).map(m => ({ value: m.id, label: m.name || m.id }))
    : []

  const visionModelOptions = visionProvider
    ? (availableModels[visionProvider] ?? []).map(m => ({ value: m.id, label: m.name || m.id }))
    : []

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="size-5 animate-spin text-text-secondary" />
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className="flex flex-col items-center gap-2 py-16">
        <p className="text-sm text-signal-red">{fetchError}</p>
        <Button variant="outline" size="sm" onClick={loadSettings}>
          Retry
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6 p-6 max-w-lg mx-auto w-full">
      <h2 className="text-xl font-semibold text-text-primary">Settings</h2>

      <form onSubmit={handleSave} className="flex flex-col gap-6">
        {/* Generation Defaults */}
        <div className="flex flex-col gap-4">
          <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider">Generation Defaults</h3>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="default-provider">Default AI Provider</Label>
            <Select value={provider || '__clear__'} onValueChange={handleProviderChange} disabled={saving}>
              <SelectTrigger id="default-provider" className="w-full">
                <SelectValue placeholder="No default" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__clear__">No default</SelectItem>
                {VALID_PROVIDERS.map((p) => (
                  <SelectItem key={p} value={p}>{p}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {envOverrides.default_ai_provider && (
              <EnvWarning envVarName={envOverrides.default_ai_provider} />
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="default-model">Default AI Model</Label>
            <Combobox
              options={modelOptions}
              value={model}
              onChange={setModel}
              placeholder={provider ? 'Select or type model...' : 'Select a provider first'}
              disabled={saving || !provider}
            />
            {envOverrides.default_ai_model && (
              <EnvWarning envVarName={envOverrides.default_ai_model} />
            )}
          </div>
        </div>

        {/* Vision */}
        <div className="flex flex-col gap-4">
          <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider">Vision (Image Description)</h3>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="vision-provider">Vision AI Provider</Label>
            <Select value={visionProvider || '__clear__'} onValueChange={handleVisionProviderChange} disabled={saving}>
              <SelectTrigger id="vision-provider" className="w-full">
                <SelectValue placeholder="Same as generation provider" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__clear__">Same as generation provider</SelectItem>
                {VALID_PROVIDERS.map((p) => (
                  <SelectItem key={p} value={p}>{p}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {envOverrides.vision_provider && (
              <EnvWarning envVarName={envOverrides.vision_provider} />
            )}
          </div>

          {visionProvider && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="vision-model">Vision AI Model</Label>
              <Combobox
                options={visionModelOptions}
                value={visionModel}
                onChange={setVisionModel}
                placeholder="Select or type model..."
                disabled={saving}
              />
              {envOverrides.vision_model && (
                <EnvWarning envVarName={envOverrides.vision_model} />
              )}
            </div>
          )}
        </div>

        {/* Performance */}
        <div className="flex flex-col gap-4">
          <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider">Performance</h3>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ai-timeout">AI CLI Timeout (min)</Label>
            <Input
              id="ai-timeout"
              type="number"
              min={1}
              value={timeout}
              onChange={(e) => setTimeout_(Number(e.target.value))}
              disabled={saving}
            />
            {envOverrides.ai_cli_timeout && (
              <EnvWarning envVarName={envOverrides.ai_cli_timeout} />
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="max-concurrent">Max Concurrent Pages</Label>
            <Input
              id="max-concurrent"
              type="number"
              min={1}
              value={concurrentPages}
              onChange={(e) => setConcurrentPages(Number(e.target.value))}
              disabled={saving}
            />
            {envOverrides.max_concurrent_pages && (
              <EnvWarning envVarName={envOverrides.max_concurrent_pages} />
            )}
          </div>
        </div>

        <Button type="submit" disabled={saving} className="w-full">
          {saving ? (
            <>
              <Loader2 className="size-4 animate-spin mr-2" />
              Saving...
            </>
          ) : (
            'Save Settings'
          )}
        </Button>
      </form>
    </div>
  )
}
