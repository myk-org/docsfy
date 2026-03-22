import { useState, useEffect, useCallback } from 'react'
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
import { TOAST_DEFAULT_MS, TOAST_ERROR_MS, VALID_PROVIDERS } from '@/lib/constants'
import { ApiError } from '@/types'
const DEFAULT_PROVIDER = 'cursor'
const DEFAULT_BRANCH = 'main'

const SK_REPO = 'docsfy-repo'
const SK_BRANCH = 'docsfy-branch'
const SK_FORCE = 'docsfy-force'

interface GenerateFormProps {
  knownModels: Record<string, string[]>
  knownBranches: Record<string, string[]>
  onGenerated?: (name: string, branch: string, provider: string, model: string) => void
}

function extractRepoName(url: string): string {
  const trimmed = url.replace(/\.git$/, '').replace(/\/+$/, '')
  const lastSlash = trimmed.lastIndexOf('/')
  if (lastSlash === -1) return trimmed
  const afterColon = trimmed.lastIndexOf(':')
  const idx = Math.max(lastSlash, afterColon)
  return trimmed.slice(idx + 1)
}

export default function GenerateForm({
  knownModels,
  knownBranches,
  onGenerated,
}: GenerateFormProps) {
  const [repoUrl, setRepoUrl] = useState('')
  const [branch, setBranch] = useState(DEFAULT_BRANCH)
  const [provider, setProvider] = useState<string>(DEFAULT_PROVIDER)
  const [model, setModel] = useState('')
  const [force, setForce] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Determine the default model for a given provider
  const getDefaultModel = useCallback(
    (prov: string): string => {
      const models = knownModels[prov]
      return models && models.length > 0 ? models[0] : ''
    },
    [knownModels],
  )

  // Restore form state from sessionStorage on mount
  useEffect(() => {
    const savedRepo = sessionStorage.getItem(SK_REPO)
    const savedBranch = sessionStorage.getItem(SK_BRANCH)
    const savedForce = sessionStorage.getItem(SK_FORCE)

    if (savedRepo) setRepoUrl(savedRepo)
    if (savedBranch) setBranch(savedBranch)
    if (savedForce === 'true') setForce(true)
  }, [])

  // Set default model when provider or knownModels changes.
  // When knownModels arrives asynchronously (via API / WebSocket) and the
  // model field is still empty, this fills it with the first available model
  // for the current provider.
  useEffect(() => {
    const models = knownModels[provider]
    if (!models || models.length === 0) return

    setModel((prev) => {
      // Keep current model if it's valid for this provider
      if (prev && models.includes(prev)) return prev
      // Otherwise pick the first known model
      return models[0]
    })
  }, [provider, knownModels])

  function sanitizeRepoUrlForStorage(value: string): string {
    try {
      const url = new URL(value)
      url.username = ''
      url.password = ''
      return url.toString()
    } catch {
      return value
    }
  }

  function saveToSession(key: string, value: string, isRepoUrl = false) {
    sessionStorage.setItem(key, isRepoUrl ? sanitizeRepoUrlForStorage(value) : value)
  }

  function clearFormState() {
    sessionStorage.removeItem(SK_REPO)
    sessionStorage.removeItem(SK_BRANCH)
    sessionStorage.removeItem(SK_FORCE)
    setRepoUrl('')
    setBranch(DEFAULT_BRANCH)
    setProvider(DEFAULT_PROVIDER)
    setModel(getDefaultModel(DEFAULT_PROVIDER))
    setForce(false)
  }

  function handleRepoChange(value: string) {
    setRepoUrl(value)
    saveToSession(SK_REPO, value, true)
  }

  function handleBranchChange(value: string) {
    setBranch(value)
    saveToSession(SK_BRANCH, value)
  }

  function handleProviderChange(value: string) {
    setProvider(value)
    // Auto-fill model with first model for new provider if current model is not valid
    const models = knownModels[value]
    if (models && models.length > 0) {
      if (!models.includes(model)) {
        setModel(models[0])
      }
    } else {
      setModel('')
    }
  }

  function handleForceChange(checked: boolean) {
    setForce(checked)
    saveToSession(SK_FORCE, String(checked))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    const submittedRepoUrl = repoUrl.trim()
    const submittedBranch = branch
    const submittedProvider = provider
    const submittedModel = model
    const submittedForce = force

    if (!submittedRepoUrl) {
      toast.error('Please enter a repository URL', { duration: TOAST_ERROR_MS })
      return
    }

    setIsSubmitting(true)
    try {
      await api.post('/api/generate', {
        repo_url: submittedRepoUrl,
        branch: submittedBranch,
        ai_provider: submittedProvider,
        ai_model: submittedModel,
        force: submittedForce,
      })

      const projectName = extractRepoName(submittedRepoUrl)
      toast.success(`Generation started for ${projectName}`, {
        duration: TOAST_DEFAULT_MS,
      })
      onGenerated?.(projectName, submittedBranch, submittedProvider, submittedModel)
      clearFormState()
    } catch (err) {
      const detail =
        err instanceof ApiError ? err.detail : 'Failed to start generation'
      toast.error(detail, { duration: TOAST_ERROR_MS })
    } finally {
      setIsSubmitting(false)
    }
  }

  const repoName = repoUrl.trim() ? extractRepoName(repoUrl) : ''
  const branchOptions = repoName && knownBranches[repoName] ? knownBranches[repoName] : []
  const modelOptions = knownModels[provider] ?? []

  return (
    <div className="flex items-start justify-center h-full p-8">
      <form onSubmit={handleSubmit} className="w-full max-w-lg flex flex-col gap-5">
        <div>
          <h2 className="text-lg font-semibold text-foreground">New Generation</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Generate documentation from a Git repository.
          </p>
        </div>

        {/* Repository URL */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="repo-url" title="HTTPS or SSH URL of the Git repository">Repository URL</Label>
          <Input
            id="repo-url"
            data-testid="repo-url"
            type="text"
            placeholder="https://github.com/org/repo"
            value={repoUrl}
            onChange={(e) => handleRepoChange(e.target.value)}
            disabled={isSubmitting}
          />
        </div>

        {/* Branch */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="branch" title="Git branch to generate documentation from">Branch</Label>
          <Combobox
            options={branchOptions}
            value={branch}
            onChange={handleBranchChange}
            placeholder="main"
            disabled={isSubmitting}
            data-testid="branch-input"
          />
        </div>

        {/* Provider */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="provider-select" title="AI service provider to use for generation">Provider</Label>
          <Select disabled={isSubmitting} value={provider} onValueChange={(v) => { if (v) handleProviderChange(v) }}>
            <SelectTrigger id="provider-select" data-testid="provider-select" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {VALID_PROVIDERS.map((p) => (
                <SelectItem key={p} value={p}>
                  {p}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Model */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="model" title="Specific AI model to use">Model</Label>
          <Combobox
            options={modelOptions}
            value={model}
            onChange={setModel}
            placeholder="Select or type model..."
            disabled={isSubmitting}
            data-testid="model-input"
          />
        </div>

        {/* Force */}
        <div className="flex items-center gap-2" title="Ignore cache and regenerate all pages from scratch">
          <input
            id="force"
            data-testid="force-checkbox"
            type="checkbox"
            checked={force}
            onChange={(e) => handleForceChange(e.target.checked)}
            disabled={isSubmitting}
            className="size-4 rounded border-border accent-primary cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
          />
          <Label htmlFor="force" className="cursor-pointer select-none">
            Force full regeneration
          </Label>
        </div>

        {/* Submit */}
        <Button type="submit" disabled={isSubmitting} className="w-full mt-2" data-testid="generate-btn" title="Start documentation generation">
          {isSubmitting ? (
            <>
              <Loader2 className="size-4 animate-spin mr-2" />
              Generating...
            </>
          ) : (
            'Generate'
          )}
        </Button>
      </form>
    </div>
  )
}
