import React from 'react'
import {
  Box,
  Typography,
  IconButton,
  Badge,
  Tooltip,
  Avatar,
  Menu,
  MenuItem,
  Divider,
} from '@mui/material'
import NotificationsIcon from '@mui/icons-material/Notifications'
import HelpIcon from '@mui/icons-material/Help'
import DarkModeIcon from '@mui/icons-material/DarkMode'
import LightModeIcon from '@mui/icons-material/LightMode'
import SettingsIcon from '@mui/icons-material/Settings'
import LogoutIcon from '@mui/icons-material/Logout'
import useUIStore from '@/stores/uiStore'
import useAgentStore from '@/stores/agentStore'

const Header: React.FC = () => {
  const { themeMode, toggleTheme, showNotifications, setShowNotifications } = useUIStore()
  const interventions = useAgentStore((state) => state.getActiveInterventions())

  // Notification menu state
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null)
  const [userMenuAnchor, setUserMenuAnchor] = React.useState<null | HTMLElement>(null)

  const handleNotificationClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget)
  }

  const handleUserMenuClick = (event: React.MouseEvent<HTMLElement>) => {
    setUserMenuAnchor(event.currentTarget)
  }

  const handleClose = () => {
    setAnchorEl(null)
    setUserMenuAnchor(null)
  }

  const handleThemeToggle = () => {
    toggleTheme()
  }

  const handleNotificationsToggle = () => {
    setShowNotifications(!showNotifications)
  }

  // Count pending interventions
  const pendingInterventions = interventions.filter(
    (intervention) => intervention.status === 'pending'
  ).length

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
      {/* Left side - Title/Breadcrumb */}
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <Typography variant="h6" noWrap component="div" sx={{ fontWeight: 'bold' }}>
          Multi-Agent Assistant
        </Typography>
        <Divider orientation="vertical" flexItem sx={{ mx: 2, height: 24 }} />
        <Typography variant="body2" color="text.secondary">
          Real-time intelligent collaboration
        </Typography>
      </Box>

      {/* Right side - Actions */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        {/* Theme toggle */}
        <Tooltip title={`Switch to ${themeMode === 'light' ? 'dark' : 'light'} mode`}>
          <IconButton color="inherit" onClick={handleThemeToggle}>
            {themeMode === 'light' ? <DarkModeIcon /> : <LightModeIcon />}
          </IconButton>
        </Tooltip>

        {/* Notifications */}
        <Tooltip title="Notifications">
          <IconButton color="inherit" onClick={handleNotificationClick}>
            <Badge badgeContent={pendingInterventions} color="error">
              <NotificationsIcon />
            </Badge>
          </IconButton>
        </Tooltip>
        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={handleClose}
          PaperProps={{
            sx: { width: 320, maxHeight: 400 },
          }}
        >
          <Box sx={{ p: 2 }}>
            <Typography variant="subtitle1" fontWeight="bold">
              Notifications
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {pendingInterventions} pending interventions
            </Typography>
          </Box>
          <Divider />
          {interventions.length === 0 ? (
            <MenuItem disabled>No notifications</MenuItem>
          ) : (
            interventions.map((intervention) => (
              <MenuItem key={intervention.intervention_id} dense>
                <Box sx={{ width: '100%' }}>
                  <Typography variant="body2">
                    Human intervention required
                  </Typography>
                  <Typography variant="caption" color="text.secondary" noWrap>
                    {intervention.request_message?.slice(0, 50)}...
                  </Typography>
                </Box>
              </MenuItem>
            ))
          )}
        </Menu>

        {/* Help */}
        <Tooltip title="Help & Documentation">
          <IconButton color="inherit">
            <HelpIcon />
          </IconButton>
        </Tooltip>

        {/* User menu */}
        <Tooltip title="Account settings">
          <IconButton onClick={handleUserMenuClick} sx={{ p: 0 }}>
            <Avatar sx={{ width: 32, height: 32 }}>U</Avatar>
          </IconButton>
        </Tooltip>
        <Menu
          anchorEl={userMenuAnchor}
          open={Boolean(userMenuAnchor)}
          onClose={handleClose}
          transformOrigin={{ horizontal: 'right', vertical: 'top' }}
          anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        >
          <MenuItem disabled>
            <Box>
              <Typography variant="subtitle2">User Account</Typography>
              <Typography variant="caption" color="text.secondary">
                user@example.com
              </Typography>
            </Box>
          </MenuItem>
          <Divider />
          <MenuItem>
            <SettingsIcon fontSize="small" sx={{ mr: 1 }} />
            Settings
          </MenuItem>
          <MenuItem onClick={handleThemeToggle}>
            {themeMode === 'light' ? (
              <>
                <DarkModeIcon fontSize="small" sx={{ mr: 1 }} />
                Dark Mode
              </>
            ) : (
              <>
                <LightModeIcon fontSize="small" sx={{ mr: 1 }} />
                Light Mode
              </>
            )}
          </MenuItem>
          <MenuItem onClick={handleNotificationsToggle}>
            <NotificationsIcon fontSize="small" sx={{ mr: 1 }} />
            {showNotifications ? 'Disable' : 'Enable'} Notifications
          </MenuItem>
          <Divider />
          <MenuItem>
            <LogoutIcon fontSize="small" sx={{ mr: 1 }} />
            Logout
          </MenuItem>
        </Menu>
      </Box>
    </Box>
  )
}

export default Header