import { useState, useCallback } from 'react'

type Theme = 'dark' | 'light'

function getStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem('theme')
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    // localStorage may be unavailable in restricted contexts
  }
  return 'dark'
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(getStoredTheme)

  // Reads from DOM (not React state) intentionally — the DOM is the source of
  // truth during the gap between index.html's inline script and React hydration.
  const toggleTheme = useCallback(() => {
    const current = document.documentElement.getAttribute('data-theme') || 'dark'
    const next: Theme = current === 'dark' ? 'light' : 'dark'
    document.documentElement.setAttribute('data-theme', next)
    document.documentElement.classList.toggle('dark', next === 'dark')
    try {
      localStorage.setItem('theme', next)
    } catch {
      // localStorage may be unavailable in restricted contexts
    }
    setTheme(next)
  }, [])

  return { theme, toggleTheme }
}
