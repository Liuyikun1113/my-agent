import React, { useState, useEffect, useCallback, createContext, useContext } from 'react'
import {
  Snackbar,
  Alert,
  AlertColor,
  Typography,
  Box,
  IconButton,
} from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'

interface ToastMessage {
  id: string
  message: string
  severity: AlertColor
  duration?: number
  action?: React.ReactNode
}

interface ToastContextType {
  showToast: (message: string, severity?: AlertColor, duration?: number) => void
  showSuccess: (message: string) => void
  showError: (message: string) => void
  showWarning: (message: string) => void
  showInfo: (message: string) => void
}

const ToastContext = createContext<ToastContextType | null>(null)

export const useToast = (): ToastContextType => {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return context
}

interface ToastProviderProps {
  children: React.ReactNode
  maxToasts?: number
}

export const ToastProvider: React.FC<ToastProviderProps> = ({ children, maxToasts = 5 }) => {
  const [toasts, setToasts] = useState<ToastMessage[]>([])

  const addToast = useCallback(
    (message: string, severity: AlertColor = 'info', duration: number = 6000) => {
      const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
      const toast: ToastMessage = { id, message, severity, duration }

      setToasts((prev) => {
        const next = [...prev, toast]
        return next.slice(-maxToasts)
      })

      if (duration > 0) {
        setTimeout(() => {
          setToasts((prev) => prev.filter((t) => t.id !== id))
        }, duration)
      }
    },
    [maxToasts]
  )

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const contextValue: ToastContextType = {
    showToast: addToast,
    showSuccess: (msg) => addToast(msg, 'success'),
    showError: (msg) => addToast(msg, 'error'),
    showWarning: (msg) => addToast(msg, 'warning'),
    showInfo: (msg) => addToast(msg, 'info'),
  }

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      {toasts.map((toast, index) => (
        <Snackbar
          key={toast.id}
          open={true}
          autoHideDuration={toast.duration}
          onClose={() => removeToast(toast.id)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          sx={{
            bottom: `${16 + index * 60}px !important`,
          }}
        >
          <Alert
            severity={toast.severity}
            onClose={() => removeToast(toast.id)}
            variant="filled"
            sx={{
              minWidth: 300,
              borderRadius: 1.5,
              boxShadow: 4,
            }}
            action={
              toast.action || (
                <IconButton
                  size="small"
                  color="inherit"
                  onClick={() => removeToast(toast.id)}
                >
                  <CloseIcon fontSize="small" />
                </IconButton>
              )
            }
          >
            <Typography variant="body2">{toast.message}</Typography>
          </Alert>
        </Snackbar>
      ))}
    </ToastContext.Provider>
  )
}

// Standalone toast component for simple use cases
const Toast: React.FC = () => {
  return null
}

export default Toast
