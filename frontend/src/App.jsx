/**
 * App root
 *
 * Configures React Router. All page routes are nested under MainLayout
 * so they share the sidebar + topbar shell.
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import Dashboard  from './pages/Dashboard'
import Repositories from './pages/Repositories'
import ComingSoon from './pages/ComingSoon'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<MainLayout />}>
          <Route index           element={<Dashboard />} />
          <Route path="/repositories"   element={<Repositories />} />
          <Route path="/investigations" element={<ComingSoon />} />
          <Route path="/deployments"    element={<ComingSoon />} />
          <Route path="/settings"       element={<ComingSoon />} />
          {/* Catch-all */}
          <Route path="*" element={<ComingSoon />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
