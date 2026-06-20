import { Outlet, NavLink, useLocation, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  LayoutDashboard,
  Database,
  PlusCircle,
} from 'lucide-react'
import { rfpApi } from '@/api/endpoints'
import type { RFPStatus } from '@/types'

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
        <img className="sidebar-logo-icon" src="/proposalpilot-mark.svg" alt="" />
        <div>
          <span className="sidebar-logo-text">ProposalPilot</span>
          <div className="text-xs text-muted mt-2">
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

      </nav>
    </aside>
  )
}

function Topbar() {
  const location = useLocation()
  const { sessionId } = useParams<{ sessionId: string }>()
  const isSessionRoute = Boolean(sessionId && location.pathname.includes('/rfp/'))
  const { data: session } = useQuery({
    queryKey: ['rfpSession', sessionId],
    queryFn: () => rfpApi.getById(sessionId!),
    enabled: isSessionRoute,
  })
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
          <h2 className="topbar-title">{getTitle()}</h2>
        </div>
        {isSessionRoute && <SessionPipeline status={session?.status} />}
      </div>
    </header>
  )
}

function SessionPipeline({ status }: { status?: RFPStatus }) {
  const stages = [
    { label: 'Uploaded', statuses: ['uploaded', 'analyzing'] },
    { label: 'Analyzed', statuses: ['analyzed', 'prep_generating', 'prep_ready'] },
    { label: 'War Room', statuses: ['war_room_running', 'war_room_done'] },
    { label: 'Proposal', statuses: ['proposal_ready'] },
  ]
  const activeIndex = Math.max(0, stages.findIndex((stage) => stage.statuses.includes(status || 'uploaded')))
  return (
    <div className="pipeline">
      {stages.map((stage, index) => (
        <span key={stage.label} className="flex items-center">
          <span className={`pipeline-step ${index < activeIndex ? 'done' : index === activeIndex ? 'active' : ''}`}>
            <span className="status-dot" />
            {stage.label}
          </span>
          {index < stages.length - 1 ? <span className="pipeline-connector" /> : null}
        </span>
      ))}
    </div>
  )
}
