import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import ApiKeyDisplay from '@/components/shared/ApiKeyDisplay'
import { useModal } from '@/components/shared/ModalProvider'
import { api } from '@/lib/api'
import { TOAST_DEFAULT_MS, TOAST_ERROR_MS } from '@/lib/constants'
import { ApiError } from '@/types'
import type { User, CreateUserResponse, RotateKeyResponse } from '@/types'

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString()
}

function RoleBadge({ role }: { role: string }) {
  if (role === 'admin') {
    return (
      <Badge className="bg-green-500/10 text-green-600 border-green-500/20">
        {role}
      </Badge>
    )
  }
  if (role === 'user') {
    return (
      <Badge className="bg-blue-500/10 text-blue-600 border-blue-500/20">
        {role}
      </Badge>
    )
  }
  return (
    <Badge className="bg-gray-500/10 text-gray-600 border-gray-500/20">
      {role}
    </Badge>
  )
}

export default function UsersPanel() {
  const { modalConfirm, modalPrompt } = useModal()

  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [newUsername, setNewUsername] = useState('')
  const [newRole, setNewRole] = useState('user')
  const [isCreating, setIsCreating] = useState(false)
  const [createdUser, setCreatedUser] = useState<CreateUserResponse | null>(null)
  const [rotatedKey, setRotatedKey] = useState<RotateKeyResponse | null>(null)

  async function loadUsers() {
    setFetchError(null)
    try {
      const data = await api.get<{ users: User[] }>('/api/admin/users')
      setUsers(data.users)
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'Failed to load users'
      setFetchError(detail)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadUsers()
  }, [])

  async function handleCreateUser(e: React.FormEvent) {
    e.preventDefault()
    if (!newUsername.trim()) return

    setIsCreating(true)
    try {
      const data = await api.post<CreateUserResponse>('/api/admin/users', {
        username: newUsername.trim(),
        role: newRole,
      })
      setCreatedUser(data)
      setNewUsername('')
      setNewRole('user')
      toast.success(`User "${data.username}" created`, { duration: TOAST_DEFAULT_MS })
      await loadUsers()
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'Failed to create user'
      toast.error(detail, { duration: TOAST_ERROR_MS })
    } finally {
      setIsCreating(false)
    }
  }

  async function handleChangePassword(username: string) {
    const password = await modalPrompt({
      title: 'Change Password',
      message: `Enter a new password for "${username}". Leave empty to auto-generate.`,
      placeholder: 'New password (min 16 characters or empty)',
      inputType: 'password',
    })
    if (password === null) return

    const body: Record<string, string> = {}
    if (password.length > 0) {
      body.new_api_key = password
    }

    try {
      const data = await api.post<RotateKeyResponse>(
        `/api/admin/users/${encodeURIComponent(username)}/rotate-key`,
        Object.keys(body).length > 0 ? body : undefined,
      )
      setRotatedKey(data)
      toast.success(`Password changed for "${username}"`, { duration: TOAST_DEFAULT_MS })
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'Failed to change password'
      toast.error(detail, { duration: TOAST_ERROR_MS })
    }
  }

  async function handleDeleteUser(username: string) {
    const confirmed = await modalConfirm({
      title: 'Delete User',
      message: `Are you sure you want to delete "${username}"? This action cannot be undone.`,
      danger: true,
      confirmText: 'Delete',
    })
    if (!confirmed) return

    try {
      await api.delete(`/api/admin/users/${encodeURIComponent(username)}`)
      toast.success(`User "${username}" deleted`, { duration: TOAST_DEFAULT_MS })
      await loadUsers()
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'Failed to delete user'
      toast.error(detail, { duration: TOAST_ERROR_MS })
    }
  }

  return (
    <div className="flex flex-col gap-6 p-6 max-w-3xl mx-auto w-full">
      <h2 className="text-xl font-semibold text-foreground">User Management</h2>

      {/* Create user form */}
      <form onSubmit={handleCreateUser} className="flex flex-col gap-3 rounded-lg border p-4">
        <h3 className="text-sm font-medium">Create User</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="flex flex-col gap-1.5 sm:col-span-1">
            <Label htmlFor="new-username">Username</Label>
            <Input
              id="new-username"
              value={newUsername}
              onChange={(e) => setNewUsername(e.target.value)}
              placeholder="Enter username"
              required
              disabled={isCreating}
            />
          </div>
          <div className="flex flex-col gap-1.5 sm:col-span-1">
            <Label htmlFor="new-role">Role</Label>
            <Select value={newRole} onValueChange={(v) => { if (v) setNewRole(v) }}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="user">user</SelectItem>
                <SelectItem value="admin">admin</SelectItem>
                <SelectItem value="viewer">viewer</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-end sm:col-span-1">
            <Button type="submit" disabled={isCreating} className="w-full">
              {isCreating ? (
                <>
                  <Loader2 className="size-4 animate-spin mr-2" />
                  Creating...
                </>
              ) : (
                'Create User'
              )}
            </Button>
          </div>
        </div>
      </form>

      {/* Created user key display */}
      {createdUser && (
        <ApiKeyDisplay
          username={createdUser.username}
          role={createdUser.role}
          password={createdUser.api_key}
          onDismiss={() => setCreatedUser(null)}
        />
      )}

      {/* Rotated key display */}
      {rotatedKey && (
        <ApiKeyDisplay
          username={rotatedKey.username}
          role={users.find(u => u.username === rotatedKey.username)?.role ?? 'user'}
          password={rotatedKey.new_api_key}
          onDismiss={() => setRotatedKey(null)}
        />
      )}

      {/* Users table */}
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </div>
      ) : fetchError ? (
        <div className="flex flex-col items-center gap-2 py-8">
          <p className="text-sm text-destructive">{fetchError}</p>
          <Button variant="outline" size="sm" onClick={() => { setLoading(true); loadUsers() }}>
            Retry
          </Button>
        </div>
      ) : users.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-8">
          No users created yet.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Username</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((user) => (
              <TableRow key={user.id}>
                <TableCell className="font-medium">{user.username}</TableCell>
                <TableCell>
                  <RoleBadge role={user.role} />
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {formatDate(user.created_at)}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleChangePassword(user.username)}
                    >
                      Change Password
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleDeleteUser(user.username)}
                    >
                      Delete
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
