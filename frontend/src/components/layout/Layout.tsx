import { useState, useCallback, useEffect, useRef, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sun, Moon, Menu, X, ExternalLink, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useTheme } from '@/lib/useTheme'
import { DOCSFY_DOCS_URL, DOCSFY_REPO_URL } from '@/lib/constants'

interface LayoutProps {
  sidebar: ReactNode
  children: ReactNode
  sidebarCollapsed: boolean
  onToggleSidebar: () => void
}

export default function Layout({
  sidebar,
  children,
  sidebarCollapsed,
  onToggleSidebar,
}: LayoutProps) {
  const navigate = useNavigate()
  const { theme, toggleTheme } = useTheme()
  const [mobileOpen, setMobileOpen] = useState(false)
  const hamburgerRef = useRef<HTMLButtonElement>(null)

  const closeMobile = useCallback(() => {
    setMobileOpen(false)
    // Restore focus to the hamburger button for keyboard accessibility
    setTimeout(() => hamburgerRef.current?.focus(), 0)
  }, [])

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-background">
      {/* Header */}
      <header className="sticky top-0 z-40 flex items-center justify-between h-12 px-4 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="flex items-center gap-3">
          {/* Mobile hamburger */}
          <Button
            ref={hamburgerRef}
            variant="ghost"
            size="icon-sm"
            onClick={() => setMobileOpen(true)}
            className="sm:hidden text-muted-foreground hover:text-foreground"
            aria-label="Open menu"
          >
            <Menu className="size-4" />
          </Button>

          {/* Logo — uses SPA navigation instead of hard reload */}
          <button type="button" onClick={() => navigate('/')} className="flex items-center gap-2 cursor-pointer">
            <h1 className="text-lg font-light tracking-tight">
              docs
              <span className="font-semibold bg-gradient-to-r from-indigo-500 to-violet-500 bg-clip-text text-transparent">
                fy
              </span>
            </h1>
          </button>

          {/* Docs badge */}
          <a
            href={DOCSFY_DOCS_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:inline-flex items-center gap-1 rounded-md border border-border px-2 py-0.5 text-[11px] font-medium text-muted-foreground hover:text-foreground hover:border-foreground/20 transition-colors"
          >
            Docs
            <ExternalLink className="size-2.5" />
          </a>
        </div>

        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={toggleTheme}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </Button>
        </div>
      </header>

      {/* Body: sidebar + main */}
      <div className="flex flex-1 min-h-0">
        {/* Desktop sidebar – collapsed icon strip */}
        {sidebarCollapsed && (
          <div className="hidden sm:flex flex-col items-center border-r border-border bg-sidebar w-10 shrink-0">
            <div className="flex-1" />
            <button
              type="button"
              onClick={onToggleSidebar}
              className="flex items-center justify-center w-full h-8 border-t border-border text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
              aria-label="Expand sidebar"
            >
              <ChevronRight className="size-4" />
            </button>
          </div>
        )}
        <aside
          className={cn(
            'hidden sm:flex flex-col border-r border-border bg-sidebar transition-[width] duration-200 ease-in-out',
            sidebarCollapsed ? 'w-0 overflow-hidden' : 'w-64'
          )}
        >
          {sidebar}
        </aside>

        {/* Mobile sidebar drawer */}
        {mobileOpen && (
          <MobileDrawer onClose={closeMobile}>
            {sidebar}
          </MobileDrawer>
        )}

        {/* Main panel */}
        <main className="flex-1 min-w-0 overflow-auto">
          {children}
        </main>
      </div>

      {/* Footer */}
      <footer className="flex items-center justify-center h-8 border-t border-border bg-background text-xs text-muted-foreground shrink-0">
        Powered by{' '}
        <a
          href={DOCSFY_REPO_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="ml-1 hover:text-foreground transition-colors underline-offset-2 hover:underline"
        >
          docsfy
        </a>
      </footer>
    </div>
  )
}

/** Mobile drawer with focus trapping and Escape-to-close */
function MobileDrawer({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  const drawerRef = useCallback((node: HTMLElement | null) => {
    if (node) {
      // Focus the close button on open
      const closeBtn = node.querySelector<HTMLButtonElement>('[aria-label="Close menu"]')
      closeBtn?.focus()
    }
  }, [])

  // Close on Escape and trap focus inside the drawer
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        onClose()
        return
      }
      // Focus trap: Tab wraps within the drawer
      if (e.key === 'Tab') {
        const drawer = document.querySelector('[data-mobile-drawer]')
        if (!drawer) return
        const focusable = drawer.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
        if (focusable.length === 0) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  return (
    <>
      <div
        className="fixed inset-0 z-50 bg-black/50 sm:hidden"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        ref={drawerRef}
        data-mobile-drawer
        role="dialog"
        aria-modal="true"
        aria-label="Navigation menu"
        className="fixed inset-y-0 left-0 z-50 flex flex-col w-72 bg-sidebar border-r border-border shadow-xl sm:hidden animate-fade-in"
      >
        <div className="flex items-center justify-between h-12 px-4 border-b border-border">
          <h1 className="text-lg font-light tracking-tight">
            docs
            <span className="font-semibold bg-gradient-to-r from-indigo-500 to-violet-500 bg-clip-text text-transparent">
              fy
            </span>
          </h1>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Close menu"
          >
            <X className="size-4" />
          </Button>
        </div>
        {children}
      </aside>
    </>
  )
}
