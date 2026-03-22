import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  useEffect,
  type ReactNode,
} from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface ConfirmOptions {
  title: string
  message: string
  danger?: boolean
  confirmText?: string
  cancelText?: string
}

interface AlertOptions {
  title: string
  message: string
}

interface PromptOptions {
  title: string
  message: string
  hint?: string
  placeholder?: string
  inputType?: string
}

interface ModalContextValue {
  modalConfirm: (options: ConfirmOptions) => Promise<boolean>
  modalAlert: (options: AlertOptions) => Promise<void>
  modalPrompt: (options: PromptOptions) => Promise<string | null>
}

const ModalContext = createContext<ModalContextValue | null>(null)

export function useModal(): ModalContextValue {
  const ctx = useContext(ModalContext)
  if (!ctx) {
    throw new Error('useModal must be used within a ModalProvider')
  }
  return ctx
}

type ModalMode = 'confirm' | 'alert' | 'prompt'

interface ModalState {
  open: boolean
  mode: ModalMode
  title: string
  message: string
  danger: boolean
  confirmText: string
  cancelText: string
  hint: string
  placeholder: string
  inputType: string
  inputValue: string
}

const INITIAL_STATE: ModalState = {
  open: false,
  mode: 'confirm',
  title: '',
  message: '',
  danger: false,
  confirmText: 'OK',
  cancelText: 'Cancel',
  hint: '',
  placeholder: '',
  inputType: 'text',
  inputValue: '',
}

export default function ModalProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ModalState>(INITIAL_STATE)
  const resolveRef = useRef<((value: unknown) => void) | null>(null)
  const confirmButtonRef = useRef<HTMLButtonElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Auto-focus the right element when the modal opens
  useEffect(() => {
    if (!state.open) return
    // Delay to let the dialog render
    const timer = setTimeout(() => {
      if (state.mode === 'prompt') {
        inputRef.current?.focus()
      } else {
        confirmButtonRef.current?.focus()
      }
    }, 50)
    return () => clearTimeout(timer)
  }, [state.open, state.mode])

  // Clean up pending promise resolvers on unmount to avoid memory leaks
  useEffect(() => {
    return () => {
      if (resolveRef.current) {
        // Resolve with null (cancel signal) so awaiting callers don't hang.
        // Using null instead of undefined matches the cancellation convention
        // used by modalPrompt (where null means "user cancelled").
        resolveRef.current(null)
        resolveRef.current = null
      }
    }
  }, [])

  const dismiss = useCallback((value: unknown) => {
    resolveRef.current?.(value)
    resolveRef.current = null
    setState(INITIAL_STATE)
  }, [])

  const modalConfirm = useCallback(
    (options: ConfirmOptions): Promise<boolean> => {
      return new Promise((resolve) => {
        resolveRef.current = resolve as (value: unknown) => void
        setState({
          open: true,
          mode: 'confirm',
          title: options.title,
          message: options.message,
          danger: options.danger ?? false,
          confirmText: options.confirmText ?? 'Confirm',
          cancelText: options.cancelText ?? 'Cancel',
          hint: '',
          placeholder: '',
          inputType: 'text',
          inputValue: '',
        })
      })
    },
    [],
  )

  const modalAlert = useCallback(
    (options: AlertOptions): Promise<void> => {
      return new Promise((resolve) => {
        resolveRef.current = resolve as (value: unknown) => void
        setState({
          open: true,
          mode: 'alert',
          title: options.title,
          message: options.message,
          danger: false,
          confirmText: 'OK',
          cancelText: 'Cancel',
          hint: '',
          placeholder: '',
          inputType: 'text',
          inputValue: '',
        })
      })
    },
    [],
  )

  const modalPrompt = useCallback(
    (options: PromptOptions): Promise<string | null> => {
      return new Promise((resolve) => {
        resolveRef.current = resolve as (value: unknown) => void
        setState({
          open: true,
          mode: 'prompt',
          title: options.title,
          message: options.message,
          danger: false,
          confirmText: 'OK',
          cancelText: 'Cancel',
          hint: options.hint ?? '',
          placeholder: options.placeholder ?? '',
          inputType: options.inputType ?? 'text',
          inputValue: '',
        })
      })
    },
    [],
  )

  function handleCancel() {
    if (state.mode === 'confirm') {
      dismiss(false)
    } else if (state.mode === 'alert') {
      dismiss(undefined)
    } else {
      dismiss(null)
    }
  }

  function handleConfirm() {
    if (state.mode === 'confirm') {
      dismiss(true)
    } else if (state.mode === 'alert') {
      dismiss(undefined)
    } else {
      dismiss(state.inputValue)
    }
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      handleCancel()
    }
  }

  return (
    <ModalContext.Provider value={{ modalConfirm, modalAlert, modalPrompt }}>
      {children}
      <Dialog open={state.open} onOpenChange={handleOpenChange}>
        <DialogContent showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>{state.title}</DialogTitle>
            <DialogDescription>{state.message}</DialogDescription>
          </DialogHeader>

          {state.mode === 'prompt' && (
            <div className="flex flex-col gap-1.5">
              <Input
                ref={inputRef}
                type={state.inputType}
                placeholder={state.placeholder}
                value={state.inputValue}
                onChange={(e) =>
                  setState((prev) => ({ ...prev, inputValue: e.target.value }))
                }
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    handleConfirm()
                  }
                }}
              />
              {state.hint && (
                <p className="text-xs text-muted-foreground">{state.hint}</p>
              )}
            </div>
          )}

          <DialogFooter>
            {state.mode !== 'alert' && (
              <Button variant="outline" onClick={handleCancel}>
                {state.cancelText}
              </Button>
            )}
            <Button
              ref={confirmButtonRef}
              variant={state.danger ? 'destructive' : 'default'}
              onClick={handleConfirm}
            >
              {state.confirmText}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ModalContext.Provider>
  )
}
