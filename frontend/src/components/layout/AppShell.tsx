import { Outlet, NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  FileText,
  Database,
  Swords,
  PlusCircle,
  Zap,
} from 'lucide-react'

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/knowledge', icon: Database, label: 'Knowledge Base' },
]

const actionItems = [
  { to: '/rfp/new', icon: PlusCircle, label: 'New RFP', accent: true },
]

export function AppShell() {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main-content">
        <Topbar />
        <main className="page-content fade-in">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function Sidebar() {
  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">
          <Zap size={18} color="white" />
        </div>
        <div>
          <span className="sidebar-logo-text">ProposalPilot</span>
          <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginTop: 2 }}>
            RFP Intelligence
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {/* Quick action */}
        {actionItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `nav-item${isActive ? ' active' : ''}${item.accent ? ' btn-primary' : ''}`
            }
            style={({ isActive }) =>
              item.accent && !isActive
                ? {
                    background: 'rgba(37, 99, 235, 0.16)',
                    color: '#93c5fd',
                    border: '1px solid rgba(96, 165, 250, 0.28)',
                  }
                : {}
            }
          >
            <item.icon size={18} />
            {item.label}
          </NavLink>
        ))}

        {/* Main nav */}
        <span className="sidebar-section-label">Workspace</span>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          >
            <item.icon size={18} />
            {item.label}
          </NavLink>
        ))}

        {/* Workflow steps (contextual) */}
        <span className="sidebar-section-label">Workflow</span>
        <div
          className="nav-item"
          style={{ color: 'var(--color-text-muted)', fontSize: '0.8125rem', cursor: 'default' }}
        >
          <FileText size={16} />
          Analyze RFP
        </div>
        <div
          className="nav-item"
          style={{ color: 'var(--color-text-muted)', fontSize: '0.8125rem', cursor: 'default' }}
        >
          <Swords size={16} />
          War Room
        </div>
      </nav>

      {/* Footer */}
      <div
        style={{
          padding: 'var(--spacing-md)',
          borderTop: '1px solid var(--color-border)',
          fontSize: '0.75rem',
          color: 'var(--color-text-muted)',
        }}
      >
        <div style={{ fontWeight: 600, color: 'var(--color-text-secondary)' }}>
          Demo mode
        </div>
        <div>Grounded outputs only</div>
      </div>
    </aside>
  )
}

function Topbar() {
  const location = useLocation()
  const getTitle = () => {
    const path = location.pathname
    if (path === '/dashboard') return 'Dashboard'
    if (path === '/knowledge') return 'Knowledge Base'
    if (path.includes('/rfp/new')) return 'New RFP'
    if (path.includes('/analysis')) return 'RFP Analysis'
    if (path.includes('/war-room')) return 'Agent War Room'
    if (path.includes('/proposal')) return 'Proposal Editor'
    return 'ProposalPilot AI'
  }

  return (
    <header className="topbar">
      <div className="flex items-center justify-between w-full">
        <div>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>{getTitle()}</h2>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="pulse" />
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
              Grounded workflow ready
            </span>
          </div>
        </div>
      </div>
    </header>
  )
}
