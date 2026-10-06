/**
 * MainLayout component
 *
 * Wraps all authenticated pages with the sidebar + topbar shell.
 * Child routes are rendered inside <main> via <Outlet>.
 */

import { Outlet } from 'react-router-dom'
import Sidebar from '../components/Sidebar'
import Topbar from '../components/Topbar'

export default function MainLayout() {
  return (
    <div className="app-shell">
      <Sidebar />

      <div className="main-content">
        <Topbar />

        <main id="main-content" tabIndex="-1">
          <div className="page-content">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
