import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useModal } from '@/components/shared/ModalProvider'
import { api } from '@/lib/api'
import { TOAST_DEFAULT_MS, TOAST_ERROR_MS } from '@/lib/constants'
import { ApiError } from '@/types'

interface AccessEntry {
  username: string
}

export default function AccessPanel() {
  const { modalConfirm } = useModal()

  // Grant form
  const [grantProject, setGrantProject] = useState('')
  const [grantUsername, setGrantUsername] = useState('')
  const [grantOwner, setGrantOwner] = useState('')
  const [isGranting, setIsGranting] = useState(false)

  // Lookup form
  const [lookupProject, setLookupProject] = useState('')
  const [lookupOwner, setLookupOwner] = useState('')
  const [isLooking, setIsLooking] = useState(false)
  const [accessList, setAccessList] = useState<AccessEntry[] | null>(null)
  const [lookupContext, setLookupContext] = useState<{ project: string; owner: string } | null>(null)

  async function handleGrant(e: React.FormEvent) {
    e.preventDefault()
    if (!grantProject.trim() || !grantUsername.trim() || !grantOwner.trim()) return

    setIsGranting(true)
    try {
      await api.post(`/api/admin/projects/${encodeURIComponent(grantProject.trim())}/access`, {
        username: grantUsername.trim(),
        owner: grantOwner.trim(),
      })
      toast.success(
        `Access granted to "${grantUsername.trim()}" for "${grantProject.trim()}"`,
        { duration: TOAST_DEFAULT_MS },
      )
      setGrantUsername('')
      // Refresh access list if we're looking at the same project
      if (
        lookupContext &&
        lookupContext.project === grantProject.trim() &&
        lookupContext.owner === grantOwner.trim()
      ) {
        await fetchAccessList(lookupContext.project, lookupContext.owner)
      }
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'Failed to grant access'
      toast.error(detail, { duration: TOAST_ERROR_MS })
    } finally {
      setIsGranting(false)
    }
  }

  async function fetchAccessList(project: string, owner: string) {
    setIsLooking(true)
    try {
      const data = await api.get<AccessEntry[]>(
        `/api/admin/projects/${encodeURIComponent(project)}/access?owner=${encodeURIComponent(owner)}`,
      )
      setAccessList(data)
      setLookupContext({ project, owner })
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'Failed to list access'
      toast.error(detail, { duration: TOAST_ERROR_MS })
      setAccessList(null)
      setLookupContext(null)
    } finally {
      setIsLooking(false)
    }
  }

  async function handleLookup(e: React.FormEvent) {
    e.preventDefault()
    if (!lookupProject.trim() || !lookupOwner.trim()) return
    await fetchAccessList(lookupProject.trim(), lookupOwner.trim())
  }

  async function handleRevoke(username: string) {
    if (!lookupContext) return

    const confirmed = await modalConfirm({
      title: 'Revoke Access',
      message: `Revoke access for "${username}" on project "${lookupContext.project}"?`,
      danger: true,
      confirmText: 'Revoke',
    })
    if (!confirmed) return

    try {
      await api.delete(
        `/api/admin/projects/${encodeURIComponent(lookupContext.project)}/access/${encodeURIComponent(username)}?owner=${encodeURIComponent(lookupContext.owner)}`,
      )
      toast.success(`Access revoked for "${username}"`, { duration: TOAST_DEFAULT_MS })
      await fetchAccessList(lookupContext.project, lookupContext.owner)
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'Failed to revoke access'
      toast.error(detail, { duration: TOAST_ERROR_MS })
    }
  }

  return (
    <div className="flex flex-col gap-6 p-6 max-w-3xl mx-auto w-full">
      <h2 className="text-xl font-semibold text-foreground">Access Management</h2>

      {/* Grant access form */}
      <form onSubmit={handleGrant} className="flex flex-col gap-3 rounded-lg border p-4">
        <h3 className="text-sm font-medium">Grant Access</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="grant-project">Project Name</Label>
            <Input
              id="grant-project"
              value={grantProject}
              onChange={(e) => setGrantProject(e.target.value)}
              placeholder="e.g. my-repo"
              required
              disabled={isGranting}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="grant-username">Username</Label>
            <Input
              id="grant-username"
              value={grantUsername}
              onChange={(e) => setGrantUsername(e.target.value)}
              placeholder="Username to grant access"
              required
              disabled={isGranting}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="grant-owner">Owner</Label>
            <Input
              id="grant-owner"
              value={grantOwner}
              onChange={(e) => setGrantOwner(e.target.value)}
              placeholder="Project owner"
              required
              disabled={isGranting}
            />
          </div>
          <div className="flex items-end">
            <Button type="submit" disabled={isGranting} className="w-full">
              {isGranting ? (
                <>
                  <Loader2 className="size-4 animate-spin mr-2" />
                  Granting...
                </>
              ) : (
                'Grant Access'
              )}
            </Button>
          </div>
        </div>
      </form>

      {/* Lookup access form */}
      <form onSubmit={handleLookup} className="flex flex-col gap-3 rounded-lg border p-4">
        <h3 className="text-sm font-medium">Lookup Access</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lookup-project">Project Name</Label>
            <Input
              id="lookup-project"
              value={lookupProject}
              onChange={(e) => setLookupProject(e.target.value)}
              placeholder="e.g. my-repo"
              required
              disabled={isLooking}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lookup-owner">Owner</Label>
            <Input
              id="lookup-owner"
              value={lookupOwner}
              onChange={(e) => setLookupOwner(e.target.value)}
              placeholder="Project owner"
              required
              disabled={isLooking}
            />
          </div>
          <div className="flex items-end">
            <Button type="submit" disabled={isLooking} className="w-full">
              {isLooking ? (
                <>
                  <Loader2 className="size-4 animate-spin mr-2" />
                  Loading...
                </>
              ) : (
                'List Access'
              )}
            </Button>
          </div>
        </div>

        {/* Access list results */}
        {accessList !== null && lookupContext && (
          <div className="mt-2">
            {accessList.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                No access entries found for this project.
              </p>
            ) : (
              <ul className="flex flex-col gap-2">
                {accessList.map((entry) => (
                  <li
                    key={entry.username}
                    className="flex items-center justify-between rounded-md border px-3 py-2"
                  >
                    <span className="text-sm font-medium">{entry.username}</span>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleRevoke(entry.username)}
                    >
                      Revoke
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </form>
    </div>
  )
}
