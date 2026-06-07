import { useState, type FormEvent } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Sun, Moon, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { api } from '@/lib/api'
import { useTheme } from '@/lib/useTheme'
import { ApiError } from '@/types'
import type { AuthResponse } from '@/types'

export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const intendedPath = (location.state as { from?: string } | null)?.from || '/'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { theme, toggleTheme } = useTheme()

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      await api.post<AuthResponse>('/api/auth/login', {
        username,
        api_key: password,
      })
      navigate(intendedPath)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError('Invalid username or password')
      } else {
        setError('Unable to connect to server')
      }
      setPassword('')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-surface-page px-4 overflow-hidden">
      {/* Ambient grid */}
      <div className="pointer-events-none absolute inset-0 opacity-[0.03]" style={{ backgroundImage: 'linear-gradient(var(--ambient-grid-line) 1px, transparent 1px), linear-gradient(90deg, var(--ambient-grid-line) 1px, transparent 1px)', backgroundSize: '48px 48px' }} />
      {/* Radial glow */}
      <div className="pointer-events-none absolute left-1/2 top-1/2 h-[600px] w-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-signal-blue/[0.04] blur-3xl" />

      {/* Theme toggle */}
      <Button
        variant="ghost"
        size="icon"
        onClick={toggleTheme}
        className="absolute top-4 right-4 text-text-tertiary hover:text-text-primary"
        aria-label="Toggle theme"
      >
        {theme === 'dark' ? <Sun className="size-5" /> : <Moon className="size-5" />}
      </Button>

      <Card className="w-full max-w-[400px] relative z-10 border border-border-muted shadow-xl">
        <CardHeader className="items-center pb-2 pt-8">
          <h1 className="text-3xl font-light tracking-tight">
            docs
            <span className="font-semibold text-signal-blue">
              fy
            </span>
          </h1>
          <p className="mt-1 text-sm text-text-tertiary">
            Sign in to your account
          </p>
        </CardHeader>

        <CardContent className="px-6 pb-8">
          <form onSubmit={handleSubmit} className="flex flex-col gap-5" data-testid="login-form">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                type="text"
                required
                placeholder="Enter your username"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={isSubmitting}
                className="h-10"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                required
                placeholder="Enter your password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isSubmitting}
                className="h-10"
              />
            </div>

            {error && (
              <div
                role="alert"
                className="animate-fade-in rounded-lg border border-signal-red/30 bg-signal-red/10 px-3 py-2 text-sm text-signal-red"
              >
                {error}
              </div>
            )}

            <Button
              type="submit"
              disabled={isSubmitting}
              className="mt-1 h-10 w-full bg-signal-blue text-white hover:bg-signal-blue/90 transition-colors duration-150"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Signing in...
                </>
              ) : (
                'Sign In'
              )}
            </Button>
          </form>

          <p className="mt-6 text-center text-xs text-text-tertiary">
            Admin login: username <strong>admin</strong> with the admin password.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
