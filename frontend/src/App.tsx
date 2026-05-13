import { useState, useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import { Box, CircularProgress, Alert, Snackbar } from '@mui/material'
import useSessionStore from '@/stores/sessionStore'
import useAgentStore from '@/stores/agentStore'
import MainLayout from '@/components/Layout/MainLayout'
import SessionList from '@/components/Session/SessionList'
import ChatWindow from '@/components/Chat/ChatWindow'
import AgentSelector from '@/components/Agent/AgentSelector'
import HumanIntervention from '@/components/Agent/HumanIntervention'
import './App.css'

function App() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Initialize stores
  const fetchSessions = useSessionStore((state) => state.fetchSessions)
  const fetchAgents = useAgentStore((state) => state.fetchAgents)
  const currentSessionId = useSessionStore((state) => state.currentSessionId)

  // Fetch initial data
  useEffect(() => {
    const initialize = async () => {
      try {
        setLoading(true)
        await Promise.all([fetchSessions(), fetchAgents()])
      } catch (err: any) {
        setError(err.message || 'Failed to initialize application')
        console.error('Initialization error:', err)
      } finally {
        setLoading(false)
      }
    }

    initialize()
  }, [fetchSessions, fetchAgents])

  // Handle errors
  const handleErrorClose = () => {
    setError(null)
  }

  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh',
          bgcolor: 'background.default',
        }}
      >
        <CircularProgress />
      </Box>
    )
  }

  return (
    <>
      <MainLayout>
        <Routes>
          <Route path="/" element={<SessionList />} />
          <Route path="/sessions/:sessionId" element={<ChatWindow />} />
          <Route path="/agents" element={<AgentSelector />} />
          <Route path="/intervention" element={<HumanIntervention />} />
        </Routes>
      </MainLayout>

      {/* Error notification */}
      <Snackbar
        open={!!error}
        autoHideDuration={6000}
        onClose={handleErrorClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleErrorClose} severity="error" sx={{ width: '100%' }}>
          {error}
        </Alert>
      </Snackbar>

      {/* Human intervention dialog (global) */}
      <HumanIntervention />
    </>
  )
}

export default App