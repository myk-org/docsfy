import { useState, useEffect, useCallback, useRef, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Plus,
  Users,
  Shield,
  Key,
  LogOut,
  ChevronLeft,
  ChevronRight,
  FileText,
  Loader2,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import Layout from '@/components/layout/Layout'
import SearchInput from '@/components/shared/SearchInput'
import ProjectTree from '@/components/shared/ProjectTree'
import type { SelectedVariant } from '@/components/shared/ProjectTree'
import GenerateForm from '@/components/shared/GenerateForm'
import VariantDetail from '@/components/shared/VariantDetail'
import { useModal } from '@/components/shared/ModalProvider'
import UsersPanel from '@/components/admin/UsersPanel'
import AccessPanel from '@/components/admin/AccessPanel'
import { api } from '@/lib/api'
import { wsManager } from '@/lib/websocket'
import { TOAST_DEFAULT_MS, TOAST_ERROR_MS, WS_POLLING_FALLBACK_MS, SELECTED_VIEW_KEY, SIDEBAR_COLLAPSED_KEY, GENERATION_STAGES } from '@/lib/constants'
import type {
  Project,
  AuthResponse,
  ProjectsResponse,
  WebSocketMessage,
  LogEntry,
  DocPlan,
} from '@/types'
import { ApiError } from '@/types'

type SelectedView =
  | { type: 'generate' }
  | { type: 'variant'; name: string; branch: string; provider: string; model: string; owner: string }
  | { type: 'users' }
  | { type: 'access' }
  | { type: 'empty' }

export default function DashboardPage() {
  const navigate = useNavigate()
  const { modalConfirm, modalPrompt, modalAlert } = useModal()

  // Auth state
  const [username, setUsername] = useState('')
  const [role, setRole] = useState('')
  const [isAdmin, setIsAdmin] = useState(false)
  const [authChecked, setAuthChecked] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  // Data state
  const [projects, setProjects] = useState<Project[]>([])
  const [projectsLoaded, setProjectsLoaded] = useState(false)
  const [knownModels, setKnownModels] = useState<Record<string, string[]>>({})
  const [knownBranches, setKnownBranches] = useState<Record<string, string[]>>({})
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedView, setSelectedView] = useState<SelectedView>(() => {
    try {
      const stored = localStorage.getItem(SELECTED_VIEW_KEY)
      if (stored) {
        const parsed = JSON.parse(stored) as SelectedView
        if (parsed && typeof parsed === 'object' && 'type' in parsed && parsed.type !== 'empty') {
          return parsed
        }
      }
    } catch {
      /* ignore corrupt localStorage */
    }
    return { type: 'empty' }
  })

  // Sidebar state
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true'
  })

  // Ref for the handleGenerated fallback timeout so it can be cleared
  const generatedTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Change password (rotate API key) via modal

  // Auth check
  useEffect(() => {
    let cancelled = false
    async function checkAuth() {
      try {
        const data = await api.get<AuthResponse>('/api/auth/me')
        if (cancelled) return
        console.debug('[Dashboard] Auth check:', data.username, 'role:', data.role, 'admin:', data.is_admin)
        setUsername(data.username)
        setRole(data.role)
        setIsAdmin(data.is_admin)
        setAuthChecked(true)
      } catch (err) {
        if (cancelled) return
        console.debug('[Dashboard] Auth check failed, redirecting to login')
        if (err instanceof ApiError && err.status === 401) {
          navigate('/login')
        } else {
          // Network errors, 500s, etc. — show error state instead of infinite loading
          setAuthError(err instanceof ApiError ? err.detail : 'Unable to connect to server')
          setAuthChecked(true)
        }
      }
    }
    checkAuth()
    return () => { cancelled = true }
  }, [navigate])

  // Initial data load
  useEffect(() => {
    if (!authChecked) return
    let cancelled = false
    async function loadProjects() {
      try {
        const data = await api.get<ProjectsResponse>('/api/projects')
        if (cancelled) return
        setProjects(data.projects)
        setKnownModels(data.known_models)
        setKnownBranches(data.known_branches)
      } catch {
        /* handled by api interceptor */
      } finally {
        if (!cancelled) setProjectsLoaded(true)
      }
    }
    loadProjects()
    return () => { cancelled = true }
  }, [authChecked])

  // Persist selectedView to localStorage (skip 'empty' — no point restoring to empty)
  useEffect(() => {
    if (selectedView.type === 'empty') {
      localStorage.removeItem(SELECTED_VIEW_KEY)
    } else {
      localStorage.setItem(SELECTED_VIEW_KEY, JSON.stringify(selectedView))
    }
  }, [selectedView])

  // Validate restored selectedView against loaded projects.
  // If a variant view was restored but the variant no longer exists, reset to empty.
  const hasValidatedRestoredView = useRef(false)
  useEffect(() => {
    if (hasValidatedRestoredView.current || !projectsLoaded) return
    hasValidatedRestoredView.current = true
    if (selectedView.type === 'variant') {
      const exists = projects.some(
        (p) =>
          p.name === selectedView.name &&
          p.branch === selectedView.branch &&
          p.ai_provider === selectedView.provider &&
          p.ai_model === selectedView.model &&
          p.owner === selectedView.owner
      )
      if (!exists) {
        setSelectedView({ type: 'empty' })
      }
    }
  }, [projects, selectedView, projectsLoaded])

  // Validate restored admin views against isAdmin.
  // If a non-admin user has a stored 'users' or 'access' view, reset to empty.
  useEffect(() => {
    if (!authChecked) return
    if (!isAdmin && (selectedView.type === 'users' || selectedView.type === 'access')) {
      setSelectedView({ type: 'empty' })
      localStorage.removeItem(SELECTED_VIEW_KEY)
    }
  }, [authChecked, isAdmin, selectedView])

  // WebSocket handler
  const handleWsMessage = useCallback((message: WebSocketMessage) => {
    if (message.type === 'sync') {
      console.debug('[Dashboard] WS sync received, projects:', message.projects.length)
      setProjects(message.projects)
      setKnownModels(message.known_models)
      setKnownBranches(message.known_branches)
    } else if (message.type === 'progress') {
      setProjects((prev) => {
        const exists = prev.some(
          (p) => p.name === message.name && p.branch === message.branch &&
                 p.ai_provider === message.provider && p.ai_model === message.model &&
                 p.owner === message.owner
        )
        if (!exists) {
          // Variant not yet in local state — trigger a full refresh
          api.get<ProjectsResponse>('/api/projects').then((data) => {
            setProjects(data.projects)
            setKnownModels(data.known_models)
            setKnownBranches(data.known_branches)
          }).catch(() => { /* best-effort */ })
          return prev
        }
        return prev.map((p) =>
          p.name === message.name &&
          p.branch === message.branch &&
          p.ai_provider === message.provider &&
          p.ai_model === message.model &&
          p.owner === message.owner
            ? {
                ...p,
                status: message.status as Project['status'],
                current_stage: message.current_stage ?? p.current_stage,
                page_count: message.page_count ?? p.page_count,
                plan_json: message.plan_json ?? p.plan_json,
                error_message: message.error_message ?? p.error_message,
              }
            : p
        )
      })
    } else if (message.type === 'status_change') {
      setProjects((prev) => {
        const exists = prev.some(
          (p) => p.name === message.name && p.branch === message.branch &&
                 p.ai_provider === message.provider && p.ai_model === message.model &&
                 p.owner === message.owner
        )
        if (!exists) {
          api.get<ProjectsResponse>('/api/projects').then((data) => {
            setProjects(data.projects)
            setKnownModels(data.known_models)
            setKnownBranches(data.known_branches)
          }).catch(() => { /* best-effort */ })
          return prev
        }
        return prev.map((p) =>
          p.name === message.name &&
          p.branch === message.branch &&
          p.ai_provider === message.provider &&
          p.ai_model === message.model &&
          p.owner === message.owner
            ? {
                ...p,
                status: message.status as Project['status'],
                page_count: message.page_count ?? p.page_count,
                last_generated: message.last_generated ?? p.last_generated,
                last_commit_sha: message.last_commit_sha ?? p.last_commit_sha,
                error_message: message.error_message ?? p.error_message,
              }
            : p
        )
      })
    }
  }, [])

  // WebSocket connection
  useEffect(() => {
    if (!authChecked) return
    wsManager.connect()
    const unsub = wsManager.onMessage(handleWsMessage)
    return () => {
      unsub()
    }
  }, [authChecked, handleWsMessage])

  // Sidebar collapse toggle
  function toggleSidebar() {
    setSidebarCollapsed((prev) => {
      const next = !prev
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next))
      return next
    })
  }

  // After generation starts, immediately select the new variant.
  // If WebSocket sync doesn't deliver the variant within 5s, fetch via HTTP.
  function handleGenerated(name: string, branch: string, provider: string, model: string) {
    console.debug('[Dashboard] Generate success:', name, branch, provider, model)
    setSelectedView({
      type: 'variant',
      name,
      branch,
      provider,
      model,
      owner: username,
    })
    // Clear any previous fallback timeout
    if (generatedTimeoutRef.current) {
      clearTimeout(generatedTimeoutRef.current)
    }
    generatedTimeoutRef.current = setTimeout(async () => {
      generatedTimeoutRef.current = null
      // Check if the variant is already in the projects list
      const found = projects.some(
        (p) => p.name === name && p.branch === branch && p.ai_provider === provider && p.ai_model === model && p.owner === username
      )
      if (!found) {
        console.debug('[Dashboard] New variant not yet in state, fetching via HTTP')
        try {
          const data = await api.get<ProjectsResponse>('/api/projects')
          setProjects(data.projects)
          setKnownModels(data.known_models)
          setKnownBranches(data.known_branches)
        } catch {
          /* best-effort fallback */
        }
      }
    }, WS_POLLING_FALLBACK_MS / 2) // 5s
  }

  // Variant selection
  function handleSelectVariant(v: SelectedVariant) {
    console.debug('[Dashboard] View changed: variant', v.name, v.branch, v.provider, v.model, 'owner:', v.owner)
    setSelectedView({
      type: 'variant',
      name: v.name,
      branch: v.branch,
      provider: v.provider,
      model: v.model,
      owner: v.owner,
    })
  }

  // Delete a single variant — called by VariantDetail after successful DELETE
  function handleDeleteVariant(name: string, branch: string, provider: string, model: string, owner: string) {
    // Optimistic removal from local state
    setProjects(prev => prev.filter(p =>
      !(p.name === name && p.branch === branch && p.ai_provider === provider && p.ai_model === model && p.owner === owner)
    ))
    // Clear selection if the deleted variant was selected
    if (
      selectedView.type === 'variant' &&
      selectedView.name === name &&
      selectedView.branch === branch &&
      selectedView.provider === provider &&
      selectedView.model === model &&
      selectedView.owner === owner
    ) {
      setSelectedView({ type: 'empty' })
    }
  }

  // Delete all variants of a project
  async function handleDeleteAll(name: string, ownerFilter?: string) {
    const displayName = ownerFilter ? `${ownerFilter}/${name}` : name
    const confirmed = await modalConfirm({
      title: 'Delete All Variants',
      message: `Delete all variants of "${displayName}"? This cannot be undone.`,
      danger: true,
      confirmText: 'Delete',
    })
    if (!confirmed) return
    try {
      // Collect distinct owners for this project name so each delete call
      // includes the required ?owner= query parameter.
      const owners = [...new Set(
        projects
          .filter((p) => p.name === name && (!ownerFilter || p.owner === ownerFilter))
          .map((p) => p.owner)
      )]
      for (const owner of owners) {
        await api.delete(`/api/projects/${name}?owner=${encodeURIComponent(owner)}`)
      }
      toast.success(`Deleted all variants of "${displayName}"`, { duration: TOAST_DEFAULT_MS })
      // Optimistic removal from local state
      setProjects(prev => prev.filter(p => !(p.name === name && (!ownerFilter || p.owner === ownerFilter))))
      setSelectedView({ type: 'empty' })
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'Failed to delete'
      toast.error(detail, { duration: TOAST_ERROR_MS })
    }
  }

  // Logout — use sendBeacon so the POST isn't canceled by navigation
  function handleLogout() {
    wsManager.disconnect()
    // sendBeacon is fire-and-forget and survives page navigation
    if (navigator.sendBeacon) {
      navigator.sendBeacon('/api/auth/logout')
    } else {
      // Fallback for older browsers
      api.post('/api/auth/logout').catch(() => {})
    }
    window.location.href = '/login'
  }

  // Change password (rotate API key)
  async function handleChangePassword() {
    const newPassword = await modalPrompt({
      title: 'Change Password',
      message: 'Enter a new password (minimum 16 characters) or leave empty to auto-generate one.',
      inputType: 'password',
      placeholder: 'New password (optional)',
    })
    // User cancelled the prompt
    if (newPassword === null) return

    try {
      const body = newPassword ? { new_key: newPassword } : {}
      const data = await api.post<{ new_api_key: string }>('/api/auth/rotate-key', body)
      await modalAlert({
        title: 'Password Changed',
        message: `Your new password is: ${data.new_api_key}\n\nSave it — you'll need it to log in again.`,
      })
      wsManager.disconnect()
      navigate('/login')
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'Failed to change password'
      toast.error(detail, { duration: TOAST_ERROR_MS })
    }
  }

  if (!authChecked) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <div className="animate-pulse text-muted-foreground text-sm">Loading...</div>
      </div>
    )
  }

  if (authError) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-background gap-3">
        <p className="text-sm text-destructive">{authError}</p>
        <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
          Retry
        </Button>
      </div>
    )
  }

  const filteredProjects = searchQuery
    ? projects.filter(p => p.name.toLowerCase().includes(searchQuery.toLowerCase()))
    : projects
  const repoCount = new Set(filteredProjects.map(p => p.name)).size

  const sidebar = (
    <div className="flex flex-col h-full min-h-0">
      {/* New Generation button */}
      {role !== 'viewer' && (
        <div className="p-3 pb-0">
          <Button
            variant="default"
            className="w-full h-9 gap-2 bg-gradient-to-r from-indigo-600 to-violet-600 text-white hover:from-indigo-500 hover:to-violet-500 transition-all duration-200"
            onClick={() => setSelectedView({ type: 'generate' })}
            title="Generate documentation for a new repository"
          >
            <Plus className="size-4" />
            New Generation
          </Button>
        </div>
      )}

      {/* Search */}
      <div className="px-3 pt-3">
        <SearchInput
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Search projects..."
        />
      </div>

      {/* Projects section header */}
      <div className="flex items-center justify-between px-3 pt-4 pb-1">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Projects
        </span>
        <span className="text-[11px] text-muted-foreground" title={`${repoCount} unique repositories`}>{repoCount}</span>
      </div>

      {/* Project tree */}
      <ProjectTree
        projects={projects}
        selectedVariant={
          selectedView.type === 'variant'
            ? {
                name: selectedView.name,
                branch: selectedView.branch,
                provider: selectedView.provider,
                model: selectedView.model,
                owner: selectedView.owner,
              }
            : null
        }
        onSelectVariant={handleSelectVariant}
        onDeleteAll={handleDeleteAll}
        searchQuery={searchQuery}
        isAdmin={isAdmin}
        role={role}
      />

      <Separator className="mx-3" />

      {/* Admin section */}
      {isAdmin && (
        <>
          <div className="px-3 pt-3 pb-1">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Admin
            </span>
          </div>
          <div className="px-2">
            <SidebarItem
              icon={<Users className="size-4" />}
              label="Users"
              active={selectedView.type === 'users'}
              onClick={() => setSelectedView({ type: 'users' })}
              title="Manage users and API keys"
            />
            <SidebarItem
              icon={<Shield className="size-4" />}
              label="Access"
              active={selectedView.type === 'access'}
              onClick={() => setSelectedView({ type: 'access' })}
              title="Manage project access permissions"
            />
          </div>
          <Separator className="mx-3 mt-2" />
        </>
      )}

      {/* Settings */}
      <div className="px-2 pt-2 pb-2 mt-auto">
        <SidebarItem
          icon={<Key className="size-4" />}
          label="Change Password"
          onClick={handleChangePassword}
          data-testid="change-password"
          title="Change your API key / password"
        />
        <SidebarItem
          icon={<LogOut className="size-4" />}
          label="Logout"
          onClick={handleLogout}
          data-testid="logout"
          title="Sign out of docsfy"
        />
      </div>

      {/* Collapse toggle */}
      <button
        type="button"
        onClick={toggleSidebar}
        className="hidden sm:flex items-center justify-center h-8 border-t border-border text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
        aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {sidebarCollapsed ? (
          <ChevronRight className="size-4" />
        ) : (
          <ChevronLeft className="size-4" />
        )}
      </button>
    </div>
  )

  return (
    <Layout
      sidebar={sidebar}
      sidebarCollapsed={sidebarCollapsed}
      onToggleSidebar={toggleSidebar}
    >
      <MainPanel
        selectedView={selectedView}
        username={username}
        projects={projects}
        knownModels={knownModels}
        knownBranches={knownBranches}
        isAdmin={isAdmin}
        role={role}
        onDelete={handleDeleteVariant}
        onGenerated={handleGenerated}
        onVariantRegenerate={(name, branch, provider, model, owner) => {
          setSelectedView({ type: 'variant', name, branch, provider, model, owner })
        }}
      />
    </Layout>
  )
}

function SidebarItem({
  icon,
  label,
  active,
  onClick,
  title,
  'data-testid': testId,
}: {
  icon: ReactNode
  label: string
  active?: boolean
  onClick: () => void
  title?: string
  'data-testid'?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      title={title}
      className={`flex items-center gap-2.5 w-full px-2 py-1.5 rounded-md text-sm transition-colors ${
        active
          ? 'bg-accent text-accent-foreground'
          : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
      }`}
    >
      {icon}
      {label}
    </button>
  )
}

function buildLogEntries(project: Project): LogEntry[] {
  const entries: LogEntry[] = []
  const stages = [...GENERATION_STAGES]
  const currentIdx = stages.indexOf((project.current_stage || '') as typeof GENERATION_STAGES[number])

  const genPagesIdx = stages.indexOf('generating_pages')
  const validatingIdx = stages.indexOf('validating')
  const crossLinkIdx = stages.indexOf('cross_linking')
  const renderIdx = stages.indexOf('rendering')

  let plan: DocPlan | null = null
  if (project.plan_json) {
    try {
      plan = JSON.parse(project.plan_json) as DocPlan
    } catch {
      /* ignore invalid JSON */
    }
  }

  const totalPages = plan
    ? plan.navigation.reduce((sum, group) => sum + group.pages.length, 0)
    : 0

  // Cloning
  if (currentIdx > 0) {
    entries.push({ id: 'clone', type: 'done', message: 'Cloned repository', timestamp: Date.now() })
  } else if (currentIdx === 0) {
    entries.push({ id: 'clone', type: 'active', message: 'Cloning repository...', timestamp: Date.now() })
  }

  // Planning (covers both 'planning' and 'incremental_planning' at indices 1 and 2)
  if (currentIdx > 2) {
    entries.push({
      id: 'plan',
      type: 'done',
      message: `Planned documentation structure (${totalPages} pages)`,
      timestamp: Date.now(),
    })
  } else if (currentIdx === 1) {
    entries.push({ id: 'plan', type: 'active', message: 'Planning documentation structure...', timestamp: Date.now() })
  } else if (currentIdx === 2) {
    entries.push({ id: 'plan', type: 'active', message: 'Planning incremental update...', timestamp: Date.now() })
  }

  // Page generation entries
  if (plan && currentIdx >= genPagesIdx) {
    let pageIdx = 0
    for (const group of plan.navigation) {
      for (const page of group.pages) {
        pageIdx++
        if (pageIdx <= project.page_count) {
          entries.push({
            id: `page-${pageIdx}`,
            type: 'done',
            message: `Generated page ${pageIdx} of ${totalPages}: ${page.title}`,
            timestamp: Date.now(),
          })
        } else if (pageIdx === project.page_count + 1 && project.status === 'generating' && currentIdx === genPagesIdx) {
          entries.push({
            id: `page-${pageIdx}`,
            type: 'active',
            message: `Generating page ${pageIdx} of ${totalPages}: ${page.title}...`,
            timestamp: Date.now(),
          })
        } else if (project.status === 'generating') {
          entries.push({
            id: `page-${pageIdx}`,
            type: 'pending',
            message: `Page ${pageIdx} of ${totalPages}: ${page.title}`,
            timestamp: Date.now(),
          })
        }
      }
    }
  }

  // Validating (stage after page generation)
  if (currentIdx > validatingIdx) {
    entries.push({ id: 'validate', type: 'done', message: 'Validated documentation against codebase', timestamp: Date.now() })
  } else if (currentIdx === validatingIdx) {
    entries.push({ id: 'validate', type: 'active', message: 'Validating documentation against codebase...', timestamp: Date.now() })
  }

  // Cross-linking
  if (currentIdx > crossLinkIdx) {
    entries.push({ id: 'crosslink', type: 'done', message: 'Added cross-page links', timestamp: Date.now() })
  } else if (currentIdx === crossLinkIdx) {
    entries.push({ id: 'crosslink', type: 'active', message: 'Adding cross-page links...', timestamp: Date.now() })
  }

  // Rendering
  if (currentIdx > renderIdx || (project.status === 'ready' && currentIdx >= renderIdx)) {
    entries.push({ id: 'render', type: 'done', message: 'Rendered documentation site', timestamp: Date.now() })
  } else if (currentIdx === renderIdx) {
    entries.push({ id: 'render', type: 'active', message: 'Rendering documentation site...', timestamp: Date.now() })
  }

  // Terminal states
  if (project.status === 'ready') {
    entries.push({ id: 'done', type: 'done', message: 'Documentation ready!', timestamp: Date.now() })
  }
  if (project.status === 'error') {
    entries.push({
      id: 'fail',
      type: 'error',
      message: `Generation failed: ${project.error_message || 'Unknown error'}`,
      timestamp: Date.now(),
    })
  }
  if (project.status === 'aborted') {
    entries.push({ id: 'abort', type: 'error', message: 'Generation aborted', timestamp: Date.now() })
  }

  return entries
}

function MainPanel({
  selectedView,
  username,
  projects,
  knownModels,
  knownBranches,
  isAdmin,
  role,
  onDelete,
  onGenerated,
  onVariantRegenerate,
}: {
  selectedView: SelectedView
  username: string
  projects: Project[]
  knownModels: Record<string, string[]>
  knownBranches: Record<string, string[]>
  isAdmin: boolean
  role: string
  onDelete: (name: string, branch: string, provider: string, model: string, owner: string) => void
  onGenerated: (name: string, branch: string, provider: string, model: string) => void
  onVariantRegenerate: (name: string, branch: string, provider: string, model: string, owner: string) => void
}) {
  if (selectedView.type === 'empty') {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-8">
        <FileText className="size-12 text-muted-foreground/40 mb-4" />
        <h2 className="text-lg font-medium text-foreground mb-1">Welcome, {username}</h2>
        <p className="text-sm text-muted-foreground max-w-md">
          Select a project from the sidebar to view its documentation, or create a new generation to get started.
        </p>
      </div>
    )
  }

  if (selectedView.type === 'generate') {
    return (
      <GenerateForm
        knownModels={knownModels}
        knownBranches={knownBranches}
        onGenerated={onGenerated}
      />
    )
  }

  if (selectedView.type === 'variant') {
    const project = projects.find(
      (p) =>
        p.name === selectedView.name &&
        p.branch === selectedView.branch &&
        p.ai_provider === selectedView.provider &&
        p.ai_model === selectedView.model &&
        p.owner === selectedView.owner
    )

    if (!project) {
      return (
        <div className="flex flex-col items-center justify-center h-full text-center p-8">
          <Loader2 className="size-8 animate-spin text-muted-foreground mb-4" />
          <p className="text-sm text-muted-foreground">
            Waiting for project data...
          </p>
        </div>
      )
    }

    const logEntries = buildLogEntries(project)

    return (
      <VariantDetail
        project={project}
        logEntries={logEntries}
        knownModels={knownModels}
        isAdmin={isAdmin}
        role={role}
        onDelete={() => onDelete(project.name, project.branch, project.ai_provider, project.ai_model, project.owner)}
        onRegenerate={(provider, model) => {
          // Switch detail pane to the newly regenerated variant
          onVariantRegenerate(project.name, project.branch, provider, model, project.owner)
        }}
      />
    )
  }

  if (selectedView.type === 'users' && isAdmin) {
    return <UsersPanel />
  }

  if (selectedView.type === 'access' && isAdmin) {
    return <AccessPanel />
  }

  return null
}
