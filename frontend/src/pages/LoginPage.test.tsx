import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import LoginPage from './LoginPage'

vi.mock('@/lib/websocket', () => ({
  wsManager: { connect: vi.fn(), disconnect: vi.fn(), onMessage: vi.fn() },
}))

function renderLogin() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  )
}

describe('LoginPage', () => {
  it('renders username and password inputs', () => {
    renderLogin()
    expect(screen.getByLabelText('Username')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
  })

  it('renders the submit button', () => {
    renderLogin()
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeInTheDocument()
  })

  it('does not show an error message initially', () => {
    renderLogin()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('renders the brand text', () => {
    renderLogin()
    expect(screen.getByText('docs')).toBeInTheDocument()
    expect(screen.getByText('fy')).toBeInTheDocument()
  })

  it('renders the admin hint', () => {
    renderLogin()
    expect(
      screen.getByText(/Admin login: username/),
    ).toBeInTheDocument()
  })
})
