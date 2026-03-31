import { Box, Drawer, List, ListItemButton, ListItemIcon, ListItemText, IconButton, Tooltip } from '@mui/material'
import DashboardIcon from '@mui/icons-material/Dashboard'
import ChatIcon from '@mui/icons-material/Chat'
import DescriptionIcon from '@mui/icons-material/Description'
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import DarkModeIcon from '@mui/icons-material/DarkMode'
import LightModeIcon from '@mui/icons-material/LightMode'
import { useLocation, useNavigate } from 'react-router-dom'
import { useSessionStore } from '../../stores/sessionStore'

const EXPANDED_WIDTH = 240
const COLLAPSED_WIDTH = 64

const navItems = [
  { label: 'Dashboard', icon: <DashboardIcon />, path: '/dashboard' },
  { label: 'Chat', icon: <ChatIcon />, path: '/chat' },
  { label: 'Documents', icon: <DescriptionIcon />, path: '/documents' },
]

export default function Sidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { sidebarCollapsed, toggleSidebar, themeMode, toggleTheme } = useSessionStore()

  const width = sidebarCollapsed ? COLLAPSED_WIDTH : EXPANDED_WIDTH

  return (
    <Drawer
      variant="permanent"
      sx={{
        width,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width,
          boxSizing: 'border-box',
          borderRight: '1px solid',
          borderColor: 'divider',
          transition: 'width 0.2s ease',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        },
      }}
    >
      {/* Logo */}
      <Box sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
        <Box
          sx={{
            width: 32,
            height: 32,
            borderRadius: 1.5,
            bgcolor: 'primary.main',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            fontWeight: 700,
            fontSize: 14,
            flexShrink: 0,
          }}
        >
          F
        </Box>
        {!sidebarCollapsed && (
          <Box sx={{ fontWeight: 700, fontSize: 16, whiteSpace: 'nowrap' }}>FinSight</Box>
        )}
      </Box>

      {/* Navigation */}
      <List sx={{ flex: 1, px: 1 }}>
        {navItems.map((item) => {
          const active = location.pathname === item.path
          return (
            <Tooltip key={item.path} title={sidebarCollapsed ? item.label : ''} placement="right">
              <ListItemButton
                onClick={() => navigate(item.path)}
                sx={{
                  borderRadius: 2,
                  mb: 0.5,
                  bgcolor: active ? 'primary.main' : 'transparent',
                  color: active ? 'white' : 'text.secondary',
                  '&:hover': { bgcolor: active ? 'primary.main' : 'action.hover' },
                  minHeight: 44,
                  justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
                  px: sidebarCollapsed ? 1 : 2,
                }}
              >
                <ListItemIcon
                  sx={{
                    color: 'inherit',
                    minWidth: sidebarCollapsed ? 0 : 36,
                    justifyContent: 'center',
                  }}
                >
                  {item.icon}
                </ListItemIcon>
                {!sidebarCollapsed && <ListItemText primary={item.label} />}
              </ListItemButton>
            </Tooltip>
          )
        })}
      </List>

      {/* Bottom controls */}
      <Box sx={{ p: 1, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
        <Tooltip title={themeMode === 'dark' ? 'Light mode' : 'Dark mode'} placement="right">
          <IconButton onClick={toggleTheme} size="small" sx={{ alignSelf: sidebarCollapsed ? 'center' : 'flex-start' }}>
            {themeMode === 'dark' ? <LightModeIcon fontSize="small" /> : <DarkModeIcon fontSize="small" />}
          </IconButton>
        </Tooltip>
        <Tooltip title={sidebarCollapsed ? 'Expand' : 'Collapse'} placement="right">
          <IconButton onClick={toggleSidebar} size="small" sx={{ alignSelf: sidebarCollapsed ? 'center' : 'flex-start' }}>
            {sidebarCollapsed ? <ChevronRightIcon fontSize="small" /> : <ChevronLeftIcon fontSize="small" />}
          </IconButton>
        </Tooltip>
      </Box>
    </Drawer>
  )
}
