import { useState, useMemo, useRef, useEffect } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { ChevronRight, Trash2, GitBranch, ChevronsDown, ChevronsUp, Copy } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import StatusDot from './StatusDot'
import { cn } from '@/lib/utils'
import { TREE_EXPANDED_KEY, TOAST_DEFAULT_MS } from '@/lib/constants'
import type { Project } from '@/types'

export interface SelectedVariant {
  name: string
  branch: string
  provider: string
  model: string
  owner: string
}

interface ProjectTreeProps {
  projects: Project[]
  selectedVariant: SelectedVariant | null
  onSelectVariant: (v: SelectedVariant) => void
  onDeleteAll: (name: string, owner?: string) => void
  searchQuery: string
  isAdmin: boolean
  role: string
}

interface RepoGroup {
  name: string
  owner: string
  groupKey: string
  branches: BranchGroup[]
}

interface BranchGroup {
  branch: string
  variants: Project[]
}

function groupProjects(projects: Project[], isAdmin: boolean): RepoGroup[] {
  // Group by owner/name for admins to keep different owners separate
  const byKey = new Map<string, Map<string, Project[]>>()

  for (const p of projects) {
    const groupKey = isAdmin ? `${p.owner}/${p.name}` : p.name
    if (!byKey.has(groupKey)) byKey.set(groupKey, new Map())
    const branches = byKey.get(groupKey)!
    if (!branches.has(p.branch)) branches.set(p.branch, [])
    branches.get(p.branch)!.push(p)
  }

  const groups: RepoGroup[] = []
  for (const [groupKey, branches] of byKey) {
    const branchGroups: BranchGroup[] = []
    let groupName = groupKey
    let groupOwner = ''
    for (const [branch, variants] of branches) {
      variants.sort((a, b) => {
        const aTime = a.updated_at ? new Date(a.updated_at).getTime() : 0
        const bTime = b.updated_at ? new Date(b.updated_at).getTime() : 0
        return bTime - aTime
      })
      branchGroups.push({ branch, variants })
      if (!groupOwner && variants.length > 0) {
        groupOwner = variants[0].owner
        groupName = variants[0].name
      }
    }
    branchGroups.sort((a, b) => a.branch.localeCompare(b.branch))
    groups.push({ name: groupName, owner: groupOwner, groupKey, branches: branchGroups })
  }

  groups.sort((a, b) => a.groupKey.localeCompare(b.groupKey))
  return groups
}

function countByStatus(projects: Project[]): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const p of projects) {
    counts[p.status] = (counts[p.status] || 0) + 1
  }
  return counts
}

type FlatRow =
  | { type: 'repo'; name: string; owner: string; groupKey: string; totalVariants: number; counts: Record<string, number> }
  | { type: 'branch'; repoName: string; groupKey: string; branch: string }
  | { type: 'variant'; project: Project }

export default function ProjectTree({
  projects,
  selectedVariant,
  onSelectVariant,
  onDeleteAll,
  searchQuery,
  isAdmin,
  role,
}: ProjectTreeProps) {
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    try {
      const stored = localStorage.getItem(TREE_EXPANDED_KEY)
      if (stored) {
        const parsed = JSON.parse(stored) as string[]
        if (Array.isArray(parsed)) return new Set(parsed)
      }
    } catch {
      /* ignore corrupt localStorage */
    }
    return new Set()
  })
  const parentRef = useRef<HTMLDivElement>(null)

  // When a variant is selected (e.g. after generation), auto-expand its repo and branch nodes
  useEffect(() => {
    if (!selectedVariant) return
    setExpanded((prev) => {
      const repoKey = isAdmin ? `${selectedVariant.owner}/${selectedVariant.name}` : selectedVariant.name
      const branchKey = `${repoKey}/${selectedVariant.branch}`
      if (prev.has(repoKey) && prev.has(branchKey)) return prev
      const next = new Set(prev)
      next.add(repoKey)
      next.add(branchKey)
      return next
    })
  }, [selectedVariant, isAdmin])

  // Persist expanded state to localStorage
  useEffect(() => {
    localStorage.setItem(TREE_EXPANDED_KEY, JSON.stringify([...expanded]))
  }, [expanded])

  const filtered = useMemo(() => {
    if (!searchQuery) return projects
    const q = searchQuery.toLowerCase()
    return projects.filter((p) => p.name.toLowerCase().includes(q))
  }, [projects, searchQuery])

  const groups = useMemo(() => groupProjects(filtered, isAdmin), [filtered, isAdmin])

  const flatRows = useMemo(() => {
    const rows: FlatRow[] = []
    for (const group of groups) {
      const allVariants = group.branches.flatMap((b) => b.variants)
      rows.push({
        type: 'repo',
        name: group.name,
        owner: group.owner,
        groupKey: group.groupKey,
        totalVariants: allVariants.length,
        counts: countByStatus(allVariants),
      })
      if (expanded.has(group.groupKey)) {
        for (const bg of group.branches) {
          const branchKey = `${group.groupKey}/${bg.branch}`
          rows.push({ type: 'branch', repoName: group.name, groupKey: group.groupKey, branch: bg.branch })
          if (expanded.has(branchKey)) {
            for (const v of bg.variants) {
              rows.push({ type: 'variant', project: v })
            }
          }
        }
      }
    }
    return rows
  }, [groups, expanded])

  const virtualizer = useVirtualizer({
    count: flatRows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 40,
    overscan: 10,
  })

  function toggleExpanded(key: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  function expandAll() {
    const allKeys: string[] = []
    for (const group of groups) {
      allKeys.push(group.groupKey)
      for (const bg of group.branches) {
        allKeys.push(`${group.groupKey}/${bg.branch}`)
      }
    }
    setExpanded(new Set(allKeys))
  }

  function collapseAll() {
    setExpanded(new Set())
  }

  function isSelected(p: Project) {
    return (
      selectedVariant !== null &&
      selectedVariant.name === p.name &&
      selectedVariant.branch === p.branch &&
      selectedVariant.provider === p.ai_provider &&
      selectedVariant.model === p.ai_model &&
      selectedVariant.owner === p.owner
    )
  }

  const canDelete = isAdmin || role === 'user'

  if (filtered.length === 0) {
    return (
      <div className="px-3 py-6 text-center text-sm text-muted-foreground">
        {searchQuery ? 'No projects match your search.' : 'No projects yet.'}
      </div>
    )
  }

  return (
    <div ref={parentRef} data-testid="project-tree" className="overflow-auto flex-1 min-h-0">
      <div className="flex items-center justify-end gap-0.5 px-3 pb-1">
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={expandAll}
          title="Expand all"
          aria-label="Expand all"
          className="text-muted-foreground hover:text-foreground"
        >
          <ChevronsDown className="size-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={collapseAll}
          title="Collapse all"
          aria-label="Collapse all"
          className="text-muted-foreground hover:text-foreground"
        >
          <ChevronsUp className="size-3.5" />
        </Button>
      </div>
      <div
        style={{ height: `${virtualizer.getTotalSize()}px`, position: 'relative', width: '100%' }}
      >
        {virtualizer.getVirtualItems().map((virtualRow) => {
          const row = flatRows[virtualRow.index]
          return (
            <div
              key={virtualRow.key}
              data-index={virtualRow.index}
              ref={virtualizer.measureElement}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              {row.type === 'repo' && (
                <RepoRow
                  name={isAdmin && row.owner ? `${row.owner}/${row.name}` : row.name}
                  totalVariants={row.totalVariants}
                  counts={row.counts}
                  isExpanded={expanded.has(row.groupKey)}
                  onToggle={() => toggleExpanded(row.groupKey)}
                  onDeleteAll={() => onDeleteAll(row.name, row.owner)}
                  canDelete={canDelete}
                />
              )}
              {row.type === 'branch' && (
                <BranchRow
                  branch={row.branch}
                  isExpanded={expanded.has(`${row.groupKey}/${row.branch}`)}
                  onToggle={() => toggleExpanded(`${row.groupKey}/${row.branch}`)}
                />
              )}
              {row.type === 'variant' && (
                <VariantRow
                  project={row.project}
                  isSelected={isSelected(row.project)}
                  isAdmin={isAdmin}
                  onSelect={() =>
                    onSelectVariant({
                      name: row.project.name,
                      branch: row.project.branch,
                      provider: row.project.ai_provider,
                      model: row.project.ai_model,
                      owner: row.project.owner,
                    })
                  }
                />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function RepoRow({
  name,
  totalVariants,
  counts,
  isExpanded,
  onToggle,
  onDeleteAll,
  canDelete,
}: {
  name: string
  totalVariants: number
  counts: Record<string, number>
  isExpanded: boolean
  onToggle: () => void
  onDeleteAll: () => void
  canDelete: boolean
}) {
  return (
    <div data-testid="project-group" className="group px-2 py-1.5 cursor-pointer hover:bg-muted/50 rounded-md transition-colors">
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={onToggle}
          className="flex items-center gap-1.5 flex-1 min-w-0 text-left"
        >
          <ChevronRight
            className={cn(
              'size-3.5 shrink-0 text-muted-foreground transition-transform duration-200',
              isExpanded && 'rotate-90'
            )}
          />
          <span className="text-sm font-medium truncate">{name}</span>
        </button>
        {canDelete && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onDeleteAll()
            }}
            className="opacity-0 group-hover:opacity-100 shrink-0 p-1 rounded-sm text-muted-foreground hover:text-destructive transition-all"
            aria-label={`Delete all variants of ${name}`}
            title="Delete all variants"
          >
            <Trash2 className="size-3.5" />
          </button>
        )}
      </div>
      {!isExpanded && (
        <div className="pl-5 mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
          <span>{totalVariants} variant{totalVariants !== 1 ? 's' : ''}</span>
          {(counts.ready ?? 0) > 0 && (
            <>
              <span>·</span>
              <span className="flex items-center gap-1">
                <StatusDot status="ready" showTitle={false} className="w-2 h-2" />
                <span className="text-green-500">{counts.ready} ready</span>
              </span>
            </>
          )}
          {(counts.generating ?? 0) > 0 && (
            <>
              <span>·</span>
              <span className="flex items-center gap-1">
                <StatusDot status="generating" showTitle={false} className="w-2 h-2" />
                <span className="text-blue-500">{counts.generating} generating</span>
              </span>
            </>
          )}
          {(counts.error ?? 0) > 0 && (
            <>
              <span>·</span>
              <span className="flex items-center gap-1">
                <StatusDot status="error" showTitle={false} className="w-2 h-2" />
                <span className="text-red-500">{counts.error} failed</span>
              </span>
            </>
          )}
          {(counts.aborted ?? 0) > 0 && (
            <>
              <span>·</span>
              <span className="flex items-center gap-1">
                <StatusDot status="aborted" showTitle={false} className="w-2 h-2" />
                <span className="text-amber-500">{counts.aborted} aborted</span>
              </span>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function BranchRow({
  branch,
  isExpanded,
  onToggle,
}: {
  branch: string
  isExpanded: boolean
  onToggle: () => void
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      title={`Branch: ${branch}`}
      className="flex items-center gap-1.5 w-full pl-6 pr-2 py-1.5 cursor-pointer hover:bg-muted/50 rounded-md transition-colors"
    >
      <ChevronRight
        className={cn(
          'size-3 shrink-0 text-muted-foreground transition-transform duration-200',
          isExpanded && 'rotate-90'
        )}
      />
      <GitBranch className="size-3 shrink-0 text-muted-foreground" />
      <span className="text-sm text-muted-foreground truncate">@{branch}</span>
    </button>
  )
}

function VariantRow({
  project,
  isSelected,
  isAdmin,
  onSelect,
}: {
  project: Project
  isSelected: boolean
  isAdmin: boolean
  onSelect: () => void
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => {
        if ((e.key === 'Enter' || e.key === ' ') && e.target === e.currentTarget) {
          e.preventDefault()
          onSelect()
        }
      }}
      title={`${project.ai_provider}/${project.ai_model} — ${project.status}${project.page_count ? ` (${project.page_count} pages)` : ''}`}
      className={cn(
        'flex items-center gap-2 w-full pl-11 pr-2 py-1.5 rounded-md transition-colors text-left cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        isSelected
          ? 'bg-accent text-accent-foreground'
          : 'hover:bg-muted/50 text-foreground'
      )}
    >
      <StatusDot status={project.status} showTitle={false} />
      <span className="text-sm truncate flex-1 min-w-0">
        {project.ai_provider} / {project.ai_model}
      </span>
      {project.generation_id && (
        <button
          type="button"
          className="text-[10px] text-muted-foreground font-mono cursor-pointer hover:text-foreground shrink-0 flex items-center gap-0.5 bg-transparent border-none p-0"
          title={`Click to copy: ${project.generation_id}`}
          aria-label="Copy generation ID"
          onClick={(e) => {
            e.stopPropagation()
            navigator.clipboard
              .writeText(project.generation_id!)
              .then(() => toast.success('Generation ID copied', { duration: TOAST_DEFAULT_MS }))
              .catch(() => toast.error('Failed to copy'))
          }}
        >
          {project.generation_id.slice(0, 8)}
          <Copy className="size-2.5" />
        </button>
      )}
      {isAdmin && (
        <Badge variant="outline" className="text-[10px] px-1 h-4 shrink-0">
          {project.owner}
        </Badge>
      )}
    </div>
  )
}
