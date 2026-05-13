import React from 'react'
import {
  Box,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider,
  Typography,
  Avatar,
  Chip,
} from '@mui/material'
import { useNavigate, useLocation } from 'react-router-dom'
import ChatIcon from '@mui/icons-material/Chat'
import PeopleIcon from '@mui/icons-material/People'
import SettingsIcon from '@mui/icons-material/Settings'
import AddIcon from '@mui/icons-material/Add'
import HistoryIcon from '@mui/icons-material/History'
import HelpIcon from '@mui/icons-material/Help'
import useSessionStore from '@/stores/sessionStore'
import useAgentStore from '@/stores/agentStore'

const Sidebar: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()

  // Get data from stores
  const sessions = useSessionStore((state) => state.sessions)
  const currentSessionId = useSessionStore((state) => state.currentSessionId)
  const agents = useAgentStore((state) => state.agents)
  const agentStatus = useAgentStore((state) => state.agentStatus)

  // Count online agents
  const onlineAgents = agents.filter(
    (agent) => agentStatus[agent.id]?.status === 'idle' || agentStatus[agent.id]?.status === 'busy'
  ).length

  // Navigation items
  const mainItems = [
    { text: 'Chat', icon: <ChatIcon />, path: '/' },
    { text: 'Agents', icon: <PeopleIcon />, path: '/agents' },
    { text: 'Settings', icon: <SettingsIcon />, path: '/settings' },
  ]

  // Session items
  const sessionItems = sessions.slice(0, 5).map((session) => ({
    id: session.id,
    text: session.title || `Session ${session.id.slice(0, 8)}`,
    path: `/sessions/${session.id}`,
    active: session.id === currentSessionId,
    unread: false, // You could add unread count logic here
  }))

  const handleNewSession = () => {
    // This would trigger a modal or API call
    console.log('Create new session')
    // For now, navigate to root
    navigate('/')
  }

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Logo/Header */}
      <Box sx={{ p: 2, textAlign: 'center', borderBottom: 1, borderColor: 'divider' }}>
        <Typography variant="h6" sx={{ fontWeight: 'bold', color: 'primary.main' }}>
          Multi-Agent
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Intelligent Assistant Platform
        </Typography>
      </Box>

      {/* Main Navigation */}
      <List sx={{ flexGrow: 1 }}>
        {mainItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton
              selected={location.pathname === item.path}
              onClick={() => navigate(item.path)}
              sx={{
                borderRadius: 1,
                mx: 1,
                mb: 0.5,
                '&.Mui-selected': {
                  bgcolor: 'primary.main',
                  color: 'white',
                  '&:hover': {
                    bgcolor: 'primary.dark',
                  },
                  '& .MuiListItemIcon-root': {
                    color: 'white',
                  },
                },
              }}
            >
              <ListItemIcon sx={{ minWidth: 40 }}>
                {item.icon}
              </ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>

      <Divider />

      {/* Sessions Section */}
      <Box sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="subtitle2" color="text.secondary">
            Recent Sessions
          </Typography>
          <Chip label={`${onlineAgents}/${agents.length}`} size="small" color="success" variant="outlined" />
        </Box>
        <List dense>
          {sessionItems.map((session) => (
            <ListItem key={session.id} disablePadding>
              <ListItemButton
                selected={session.active}
                onClick={() => navigate(session.path)}
                sx={{
                  borderRadius: 1,
                  mb: 0.5,
                  '&.Mui-selected': {
                    bgcolor: 'action.selected',
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: 36 }}>
                  <ChatIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText
                  primary={session.text}
                  primaryTypographyProps={{
                    variant: 'body2',
                    noWrap: true,
                    title: session.text,
                  }}
                />
                {session.unread && (
                  <Chip label="New" size="small" color="primary" sx={{ ml: 1 }} />
                )}
              </ListItemButton>
            </ListItem>
          ))}
        </List>
        <ListItemButton
          onClick={handleNewSession}
          sx={{
            borderRadius: 1,
            mt: 1,
            bgcolor: 'action.hover',
          }}
        >
          <ListItemIcon sx={{ minWidth: 36 }}>
            <AddIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="New Session" primaryTypographyProps={{ variant: 'body2' }} />
        </ListItemButton>
      </Box>

      <Divider />

      {/* Footer/Status */}
      <Box sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
          <Avatar sx={{ width: 32, height: 32, mr: 1 }}>U</Avatar>
          <Box>
            <Typography variant="body2">User</Typography>
            <Typography variant="caption" color="text.secondary">
              Online
            </Typography>
          </Box>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <ListItemButton
            sx={{ borderRadius: 1, flex: 1, p: 1 }}
            onClick={() => navigate('/history')}
          >
            <HistoryIcon fontSize="small" />
          </ListItemButton>
          <ListItemButton
            sx={{ borderRadius: 1, flex: 1, p: 1 }}
            onClick={() => navigate('/help')}
          >
            <HelpIcon fontSize="small" />
          </ListItemButton>
        </Box>
      </Box>
    </Box>
  )
}

export default Sidebar