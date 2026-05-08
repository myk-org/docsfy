import { useState, useCallback, useEffect } from 'react'
import {
  ExternalLink,
  Download,
  Trash2,
  Loader2,
  AlertTriangle,
  XCircle,
  Square,
  Copy,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Progress } from '@/components/ui/progress'
import Combobox from '@/components/shared/Combobox'
import ActivityLog from '@/components/shared/ActivityLog'
import { useModal } from '@/components/shared/ModalProvider'
import { api } from '@/lib/api'
import { TOAST_DEFAULT_MS, TOAST_ERROR_MS, VALID_PROVIDERS } from '@/lib/constants'
import { ApiError } from '@/types'
import type { Project, LogEntry, DocPlan, AvailableModels } from '@/types'

interface VariantDetailProps {
  project: Project
  logEntries: LogEntry[]
  availableModels: AvailableModels
  isAdmin: boolean
  role: string
  onDelete?: () => void
  onRegenerate?: (provider: string, model: string, force: boolean) => void
}

function getTotalPages(planJson: string | null): number {
  if (!planJson) return 0
  try {
    const plan: DocPlan = JSON.parse(planJson)
    return plan.navigation.reduce((sum, group) => sum + group.pages.length, 0)
  } catch {
    return 0
  }
}

function normalizeGitHubUrl(url: string): string | null {
  // Match SSH remotes: git@github.com:org/repo.git
  const sshMatch = url.match(/^git@github\.com:(.+?)(?:\.git)?$/)
  if (sshMatch) return `https://github.com/${sshMatch[1]}`

  // Match HTTPS remotes: https://github.com/org/repo[.git]
  try {
    const parsed = new URL(url)
    if (parsed.hostname === 'github.com') {
      return `https://github.com${parsed.pathname.replace(/\.git$/, '')}`
    }
  } catch {
    // Not a valid URL
  }

  return null
}

function formatRepoUrl(url: string): string {
  const normalized = normalizeGitHubUrl(url)
  if (normalized) return normalized.replace(/^https?:\/\//, '')
  return url.replace(/^https?:\/\//, '')
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'N/A'
  const date = new Date(dateStr)
  return date.toLocaleString()
}

function repoHref(repoUrl: string): string {
  return normalizeGitHubUrl(repoUrl) ?? repoUrl
}

function commitUrl(repoUrl: string, sha: string): string | null {
  const base = normalizeGitHubUrl(repoUrl)
  if (!base) return null
  return `${base}/commit/${sha}`
}

async function deleteVariant(
  project: Project,
  modalConfirm: (opts: { title: string; message: string; danger: boolean; confirmText: string }) => Promise<boolean>,
  setIsDeleting: (v: boolean) => void,
  onDelete?: () => void,
) {
  const confirmed = await modalConfirm({
    title: 'Delete Variant',
    message: `Are you sure you want to delete ${project.name}/${project.branch}/${project.ai_provider}/${project.ai_model} (owner: ${project.owner})? This action cannot be undone.`,
    danger: true,
    confirmText: 'Delete',
  })
  if (!confirmed) return

  setIsDeleting(true)
  try {
    await api.delete(
      `/api/projects/${project.name}/${project.branch}/${project.ai_provider}/${project.ai_model}?owner=${encodeURIComponent(project.owner)}`
    )
    toast.success('Variant deleted', { duration: TOAST_DEFAULT_MS })
    onDelete?.()
  } catch (err) {
    const detail = err instanceof ApiError ? err.detail : 'Failed to delete'
    toast.error(detail, { duration: TOAST_ERROR_MS })
  } finally {
    setIsDeleting(false)
  }
}

function StatusBadge({ status }: { status: Project['status'] }) {
  const titles: Record<string, string> = {
    ready: 'Documentation is ready to view',
    generating: 'Documentation is being generated',
    error: 'Documentation generation failed',
    aborted: 'Documentation generation was aborted',
  }
  if (status === 'ready') {
    return <Badge data-testid="status-text" className="bg-green-500/10 text-green-600 border-green-500/20" title={titles[status]}>Ready</Badge>
  }
  if (status === 'generating') {
    return <Badge data-testid="status-text" className="bg-blue-500/10 text-blue-600 border-blue-500/20 animate-pulse" title={titles[status]}>Generating</Badge>
  }
  if (status === 'error') {
    return <Badge data-testid="status-text" variant="destructive" title={titles[status]}>Error</Badge>
  }
  if (status === 'aborted') {
    return <Badge data-testid="status-text" className="bg-amber-500/10 text-amber-600 border-amber-500/20" title={titles[status]}>Aborted</Badge>
  }
  return null
}

function InfoGrid({ project, isAdmin }: { project: Project; isAdmin: boolean }) {
  const sha = project.last_commit_sha
  const shortSha = sha ? sha.slice(0, 7) : null
  const shaLink = sha ? commitUrl(project.repo_url, sha) : null

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 text-sm">
      <div>
        <span className="text-muted-foreground">Repository</span>
        <div className="mt-0.5">
          <a
            href={repoHref(project.repo_url)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline break-all"
          >
            {formatRepoUrl(project.repo_url)}
          </a>
        </div>
      </div>
      <div>
        <span className="text-muted-foreground">AI Provider / Model</span>
        <div className="mt-0.5 font-medium">{project.ai_provider} / {project.ai_model}</div>
      </div>
      <div>
        <span className="text-muted-foreground">Branch</span>
        <div className="mt-0.5 font-medium">{project.branch}</div>
      </div>
      <div>
        <span className="text-muted-foreground" title="Number of documentation pages generated">Pages</span>
        <div className="mt-0.5 font-medium">{project.page_count}</div>
      </div>
      {shortSha && (
        <div>
          <span className="text-muted-foreground">Commit</span>
          <div className="mt-0.5">
            {shaLink ? (
              <a
                href={shaLink}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-primary hover:underline"
                title="Click to view commit on GitHub"
              >
                {shortSha}
              </a>
            ) : (
              <span className="font-mono font-medium">{shortSha}</span>
            )}
          </div>
        </div>
      )}
      {isAdmin && (
        <div>
          <span className="text-muted-foreground">Owner</span>
          <div className="mt-0.5 font-medium">{project.owner}</div>
        </div>
      )}
      <div>
        <span className="text-muted-foreground">Last Generated</span>
        <div className="mt-0.5 font-medium">{formatDate(project.last_generated)}</div>
      </div>
      {project.total_cost_usd != null && (
        <div>
          <span className="text-muted-foreground">Generation Cost</span>
          <div className="mt-0.5 font-medium">${project.total_cost_usd.toFixed(4)}</div>
        </div>
      )}
      {project.generation_id && (
        <div>
          <span className="text-muted-foreground">Generation ID</span>
          <div className="mt-0.5 flex items-center gap-1.5">
            <code className="text-sm font-mono font-medium break-all">{project.generation_id}</code>
            <button
              type="button"
              className="shrink-0 p-0.5 rounded-sm text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Copy generation ID"
              onClick={() => {
                navigator.clipboard
                  .writeText(project.generation_id!)
                  .then(() => toast.success('Generation ID copied', { duration: TOAST_DEFAULT_MS }))
                  .catch(() => toast.error('Failed to copy'))
              }}
              title="Copy generation ID"
            >
              <Copy className="size-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function RegenerateSection({
  project,
  availableModels,
  defaultForce,
  onRegenerate,
}: {
  project: Project
  availableModels: AvailableModels
  defaultForce: boolean
  onRegenerate?: (provider: string, model: string, force: boolean) => void
}) {
  const [provider, setProvider] = useState(project.ai_provider)
  const [model, setModel] = useState(project.ai_model)
  const [force, setForce] = useState(defaultForce)
  const [isStarting, setIsStarting] = useState(false)

  // Reset regenerate state when the selected variant changes
  const variantKey = `${project.name}/${project.branch}/${project.ai_provider}/${project.ai_model}/${project.owner}`
  useEffect(() => {
    setProvider(project.ai_provider)
    setModel(project.ai_model)
    setForce(defaultForce)
    setIsStarting(false)
  }, [variantKey]) // eslint-disable-line react-hooks/exhaustive-deps

  const getDefaultModel = useCallback(
    (prov: string): string => {
      const models = availableModels[prov]
      return models && models.length > 0 ? models[0].id : ''
    },
    [availableModels],
  )

  useEffect(() => {
    setModel((prev) => {
      const models = availableModels[provider]
      if (models && models.length > 0) {
        return prev || models[0].id
      }
      return prev
    })
  }, [provider, availableModels])

  function handleProviderChange(value: string) {
    setProvider(value)
    const models = availableModels[value]
    if (models && models.length > 0) {
      if (!models.some(m => m.id === model)) {
        setModel(models[0].id)
      }
    } else {
      setModel(getDefaultModel(value))
    }
  }

  async function handleRegenerate() {
    setIsStarting(true)
    try {
      await api.post('/api/generate', {
        repo_url: project.repo_url,
        branch: project.branch,
        ai_provider: provider,
        ai_model: model,
        force,
      })
      toast.success(`Regeneration started for ${project.name}`, { duration: TOAST_DEFAULT_MS })
      onRegenerate?.(provider, model, force)
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'Failed to start regeneration'
      toast.error(detail, { duration: TOAST_ERROR_MS })
    } finally {
      setIsStarting(false)
    }
  }

  const modelOptions = (availableModels[provider] ?? []).map(m => ({ value: m.id, label: m.name || m.id }))

  return (
    <div className="border-t border-dashed pt-4 mt-4">
      <h3 className="text-sm font-medium mb-3">Regenerate Documentation</h3>
      <div className="flex flex-col gap-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label>Provider</Label>
            <Select value={provider} onValueChange={(v) => { if (v) handleProviderChange(v) }}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {VALID_PROVIDERS.map((p) => (
                  <SelectItem key={p} value={p}>{p}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Model</Label>
            <Combobox
              options={modelOptions}
              value={model}
              onChange={setModel}
              placeholder="Select or type model..."
            />
          </div>
        </div>
        <div className="flex items-center gap-2" title="Ignore cache and regenerate all pages from scratch">
          <input
            id="regen-force"
            data-testid="data-regen-force"
            type="checkbox"
            checked={force}
            onChange={(e) => setForce(e.target.checked)}
            className="size-4 rounded border-border accent-primary cursor-pointer"
          />
          <Label htmlFor="regen-force" className="cursor-pointer select-none">
            Force full regeneration
          </Label>
        </div>
        <Button
          data-testid="data-regenerate-variant"
          onClick={handleRegenerate}
          disabled={isStarting || !model}
          className="w-full sm:w-auto"
          title="Re-generate documentation with these settings"
        >
          {isStarting ? (
            <>
              <Loader2 className="size-4 animate-spin mr-2" />
              Starting...
            </>
          ) : (
            'Regenerate'
          )}
        </Button>
      </div>
    </div>
  )
}

function ReadyView({
  project,
  logEntries,
  availableModels,
  isAdmin,
  role,
  onDelete,
  onRegenerate,
}: VariantDetailProps) {
  const { modalConfirm } = useModal()
  const [isDeleting, setIsDeleting] = useState(false)

  const isUpToDate = project.current_stage === 'up_to_date'

  function handleDelete() {
    deleteVariant(project, modalConfirm, setIsDeleting, onDelete)
  }

  const docsUrl = `/docs/${project.name}/${project.branch}/${project.ai_provider}/${project.ai_model}/?owner=${encodeURIComponent(project.owner)}`
  const downloadUrl = `/api/projects/${project.name}/${project.branch}/${project.ai_provider}/${project.ai_model}/download?owner=${encodeURIComponent(project.owner)}`

  return (
    <>
      {/* Success / up-to-date message */}
      {isUpToDate ? (
        <div className="rounded-lg border border-blue-500/20 bg-blue-500/5 px-4 py-3 text-sm text-blue-600">
          Documentation is already up to date.
        </div>
      ) : (
        <div className="rounded-lg border border-green-500/20 bg-green-500/5 px-4 py-3 text-sm text-green-600">
          Documentation generated successfully!
        </div>
      )}

      {/* Info grid */}
      <InfoGrid project={project} isAdmin={isAdmin} />

      {/* Activity log */}
      {logEntries.length > 0 && (
        <ActivityLog entries={logEntries} status={project.status} />
      )}

      {/* Actions */}
      <div className="flex flex-col sm:flex-row gap-2">
        <Button
          data-testid="view-docs"
          render={<a href={docsUrl} target="_blank" rel="noopener noreferrer" />}
          title="Open generated documentation in new tab"
        >
          <ExternalLink className="size-4 mr-1.5" />
          View Documentation
        </Button>
        <Button
          data-testid="download-btn"
          variant="outline"
          render={<a href={downloadUrl} />}
          title="Download documentation as tar.gz archive"
        >
          <Download className="size-4 mr-1.5" />
          Download
        </Button>
        {role !== 'viewer' && (
          <Button
            data-testid="data-delete-variant"
            variant="destructive"
            onClick={handleDelete}
            disabled={isDeleting}
            title="Permanently delete this documentation variant"
          >
            {isDeleting ? (
              <>
                <Loader2 className="size-4 animate-spin mr-1.5" />
                Deleting...
              </>
            ) : (
              <>
                <Trash2 className="size-4 mr-1.5" />
                Delete
              </>
            )}
          </Button>
        )}
      </div>

      {/* Regenerate */}
      {role !== 'viewer' && (
        <RegenerateSection
          project={project}
          availableModels={availableModels}
          defaultForce={false}
          onRegenerate={onRegenerate}
        />
      )}
    </>
  )
}

function GeneratingView({
  project,
  logEntries,
  isAdmin,
  role,
}: {
  project: Project
  logEntries: LogEntry[]
  isAdmin: boolean
  role: string
}) {
  const { modalConfirm } = useModal()
  const [isAborting, setIsAborting] = useState(false)

  const totalPages = getTotalPages(project.plan_json)
  const progressPercent = totalPages > 0 ? Math.round((project.page_count / totalPages) * 100) : 0

  async function handleAbort() {
    const confirmed = await modalConfirm({
      title: 'Abort Generation',
      message: 'Are you sure you want to abort this generation? Progress will be lost.',
      danger: true,
      confirmText: 'Abort',
    })
    if (!confirmed) return

    setIsAborting(true)
    try {
      await api.post(
        `/api/projects/${project.name}/${project.branch}/${project.ai_provider}/${project.ai_model}/abort?owner=${encodeURIComponent(project.owner)}`
      )
      toast.success('Abort requested', { duration: TOAST_DEFAULT_MS })
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'Failed to abort'
      toast.error(detail, { duration: TOAST_ERROR_MS })
    } finally {
      setIsAborting(false)
    }
  }

  return (
    <>
      {/* Info grid */}
      <InfoGrid project={project} isAdmin={isAdmin} />

      {/* Progress bar */}
      {totalPages > 0 && (
        <div className="flex flex-col gap-1.5">
          <Progress value={progressPercent}>
            <span className="text-sm font-medium">Progress</span>
          </Progress>
          <span className="text-xs text-muted-foreground">
            {project.page_count} of {totalPages} pages ({progressPercent}%)
          </span>
        </div>
      )}

      {/* Activity log */}
      <ActivityLog entries={logEntries} status={project.status} />

      {/* Abort button — hidden for viewers */}
      {role !== 'viewer' && (
        <div>
          <Button
            data-testid="data-abort-variant"
            variant="destructive"
            onClick={handleAbort}
            disabled={isAborting}
            title="Stop the documentation generation"
          >
            {isAborting ? (
              <>
                <Loader2 className="size-4 animate-spin mr-1.5" />
                Aborting...
              </>
            ) : (
              <>
                <Square className="size-4 mr-1.5" />
                Abort Generation
              </>
            )}
          </Button>
        </div>
      )}
    </>
  )
}

function ErrorAbortedView({
  project,
  logEntries,
  availableModels,
  isAdmin,
  role,
  onDelete,
  onRegenerate,
}: VariantDetailProps) {
  const { modalConfirm } = useModal()
  const [isDeleting, setIsDeleting] = useState(false)

  const isError = project.status === 'error'

  function handleDelete() {
    deleteVariant(project, modalConfirm, setIsDeleting, onDelete)
  }

  return (
    <>
      {/* Info grid */}
      <InfoGrid project={project} isAdmin={isAdmin} />

      {/* Error message */}
      {project.error_message && (
        <div
          className={`flex items-start gap-3 rounded-lg px-4 py-3 text-sm ${
            isError
              ? 'border-l-[3px] border-l-red-500 bg-red-500/5 text-red-600'
              : 'border-l-[3px] border-l-amber-500 bg-amber-500/5 text-amber-600'
          }`}
        >
          {isError ? (
            <XCircle className="size-4 shrink-0 mt-0.5" />
          ) : (
            <AlertTriangle className="size-4 shrink-0 mt-0.5" />
          )}
          <span>{project.error_message}</span>
        </div>
      )}

      {/* Activity log */}
      {logEntries.length > 0 && (
        <ActivityLog entries={logEntries} status={project.status} />
      )}

      {/* Regenerate + Delete (hidden for viewers) */}
      {role !== 'viewer' && (
        <>
          <RegenerateSection
            project={project}
            availableModels={availableModels}
            defaultForce={true}
            onRegenerate={onRegenerate}
          />
          <div className="mt-2">
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={isDeleting}
              title="Permanently delete this documentation variant"
            >
              {isDeleting ? (
                <>
                  <Loader2 className="size-4 animate-spin mr-1.5" />
                  Deleting...
                </>
              ) : (
                <>
                  <Trash2 className="size-4 mr-1.5" />
                  Delete
                </>
              )}
            </Button>
          </div>
        </>
      )}
    </>
  )
}

export default function VariantDetail({
  project,
  logEntries,
  availableModels,
  isAdmin,
  role,
  onDelete,
  onRegenerate,
}: VariantDetailProps) {
  return (
    <div className="flex flex-col gap-5 p-6 max-w-3xl mx-auto w-full">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-xl font-semibold text-foreground">{project.name}</h2>
        <Badge variant="secondary">@{project.branch}</Badge>
        <StatusBadge status={project.status} />
      </div>

      {/* Status-specific content */}
      {project.status === 'ready' && (
        <ReadyView
          project={project}
          logEntries={logEntries}
          availableModels={availableModels}
          isAdmin={isAdmin}
          role={role}
          onDelete={onDelete}
          onRegenerate={onRegenerate}
        />
      )}
      {project.status === 'generating' && (
        <GeneratingView
          project={project}
          logEntries={logEntries}
          isAdmin={isAdmin}
          role={role}
        />
      )}
      {(project.status === 'error' || project.status === 'aborted') && (
        <ErrorAbortedView
          project={project}
          logEntries={logEntries}
          availableModels={availableModels}
          isAdmin={isAdmin}
          role={role}
          onDelete={onDelete}
          onRegenerate={onRegenerate}
        />
      )}
    </div>
  )
}
