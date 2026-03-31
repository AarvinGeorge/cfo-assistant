import { Box } from '@mui/material'
import { Outlet } from 'react-router-dom'
import Sidebar from './components/layout/Sidebar'

export default function App() {
  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <Sidebar />
      <Box component="main" sx={{ flexGrow: 1, overflow: 'auto' }}>
        <Outlet />
      </Box>
    </Box>
  )
}
