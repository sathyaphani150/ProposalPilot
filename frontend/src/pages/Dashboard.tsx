import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { FileText, PlusCircle, Database, Clock, TrendingUp, Swords } from 'lucide-react'
import { getErrorMessage } from '@/api/client'
import { rfpApi } from '@/api/endpoints'
import type { RFPSession, RFPStatus } from '@/types'
import { formatDistanceToNow } from 'date-fns'

const STATUS_CONFIG: Record<RFPStatus, { label: string; className: string }> = {
  uploaded:        { label: 'Uploaded',        className: 'badge badge-uploaded' },
  analyzing:       { label: 'Analyzing…',      className: 'badge badge-analyzing' },
  analyzed:        { label: 'Analyzed',         className: 'badge badge-analyzed' },
  analysis_failed: { label: 'Analysis Failed', className: 'badge badge-uploaded' },
  prep_generating: { label: 'Generating Prep', className: 'badge badge-analyzing' },
  prep_ready:      { label: 'Prep Ready',      className: 'badge badge-prep-ready' },
  war_room_running:{ label: 'War Room Active', className: 'badge badge-war-room' },
  war_room_done:   { label: 'War Room Done',   className: 'badge badge-prep-ready' },
  proposal_ready:  { label: 'Proposal Ready',  className: 'badge badge-done' },
}

export function Dashboard() {
  const navigate = useNavigate()

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['rfp-sessions'],
    queryFn: () => rfpApi.list({ limit: 20 }),
  })

  useEffect(() => {
    if (isError && error) {
      toast.error(getErrorMessage(error))
    }
  }, [isError, error])

  const sessions = data?.items ?? []
  const total = data?.total ?? 0

  const statCards = [
    { icon: FileText, label: 'Total RFPs', value: total, color: 'var(--color-primary)' },
    {
      icon: TrendingUp,
      label: 'Proposals Ready',
      value: sessions.filter((s) => s.status === 'proposal_ready').length,
      color: 'var(--color-success)',
    },
    {
      icon: Swords,
      label: 'In War Room',
      value: sessions.filter((s) => s.status === 'war_room_running').length,
      color: 'var(--color-status-war-room)',
    },
    {
      icon: Database,
      label: 'Analyzed',
      value: sessions.filter((s) => ['analyzed', 'war_room_running', 'war_room_done', 'proposal_ready'].includes(s.status)).length,
      color: 'var(--color-accent)',
    },
  ]

  const getNextAction = (session: RFPSession) => {
    switch (session.status) {
      case 'uploaded':
        return { label: 'Analyze RFP', path: `/rfp/${session.id}/analysis` }
      case 'analyzed':
        return { label: 'View Analysis', path: `/rfp/${session.id}/analysis` }
      case 'prep_ready':
        return { label: 'View Analysis', path: `/rfp/${session.id}/analysis` }
      case 'war_room_done':
        return { label: 'View War Room', path: `/rfp/${session.id}/war-room` }
      default:
        return { label: 'View', path: `/rfp/${session.id}/analysis` }
    }
  }

  return (
    <div className="flex-col gap-6" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 style={{ fontSize: '1.75rem', marginBottom: '0.25rem' }}>
            Welcome back 👋
          </h1>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>
            Manage your RFP engagements and AI-generated proposals
          </p>
        </div>
        <button
          className="btn btn-primary btn-lg"
          onClick={() => navigate('/rfp/new')}
        >
          <PlusCircle size={18} />
          New RFP
        </button>
      </div>

      {/* Stats */}
      <div className="grid-4">
        {statCards.map((stat) => (
          <div key={stat.label} className="card-elevated">
            <div className="flex items-center justify-between" style={{ marginBottom: '1rem' }}>
              <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', fontWeight: 500 }}>
                {stat.label}
              </span>
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 'var(--radius-md)',
                  background: `${stat.color}22`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <stat.icon size={18} color={stat.color} />
              </div>
            </div>
            <div style={{ fontSize: '2rem', fontWeight: 700, color: stat.color }}>
              {isLoading ? <div className="skeleton" style={{ width: 40, height: 32, display: 'inline-block' }} /> : stat.value}
            </div>
          </div>
        ))}
      </div>

      {/* Sessions List */}
      <div>
        <div className="flex items-center justify-between" style={{ marginBottom: '1rem' }}>
          <h2 style={{ fontSize: '1.125rem' }}>Recent Engagements</h2>
          <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
            {total} total
          </span>
        </div>

        {isLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton card" style={{ height: 80 }} />
            ))}
          </div>
        ) : sessions.length === 0 ? (
          <EmptyState onNew={() => navigate('/rfp/new')} />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {sessions.map((session) => {
              const nextAction = getNextAction(session)
              const config = STATUS_CONFIG[session.status] ?? STATUS_CONFIG.uploaded
              return (
                <div
                  key={session.id}
                  className="card"
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
                  onClick={() => navigate(nextAction.path)}
                >
                  <div className="flex items-center gap-3">
                    <div
                      style={{
                        width: 44,
                        height: 44,
                        borderRadius: 'var(--radius-md)',
                        background: 'var(--color-bg-hover)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                      }}
                    >
                      <FileText size={20} color="var(--color-primary-light)" />
                    </div>
                    <div>
                      <div style={{ fontWeight: 600, marginBottom: '0.2rem' }}>{session.title}</div>
                      <div className="flex items-center gap-2">
                        {session.client_name && (
                          <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                            {session.client_name}
                          </span>
                        )}
                        <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                          <Clock size={11} style={{ display: 'inline', marginRight: 3 }} />
                          {formatDistanceToNow(new Date(session.created_at), { addSuffix: true })}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={config.className}>{config.label}</span>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={(e) => { e.stopPropagation(); navigate(nextAction.path) }}
                    >
                      {nextAction.label}
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

function EmptyState({ onNew }: { onNew: () => void }) {
  return (
    <div
      className="card-elevated"
      style={{
        textAlign: 'center',
        padding: '4rem 2rem',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '1rem',
      }}
    >
      <div
        style={{
          width: 72,
          height: 72,
          borderRadius: 'var(--radius-xl)',
          background: 'rgba(124, 58, 237, 0.1)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          border: '1px solid rgba(124, 58, 237, 0.2)',
        }}
      >
        <FileText size={32} color="var(--color-primary-light)" />
      </div>
      <div>
        <h3 style={{ marginBottom: '0.5rem' }}>No RFPs Yet</h3>
        <p style={{ color: 'var(--color-text-muted)', maxWidth: 400 }}>
          Upload your first RFP document to generate a leadership-ready RFP analysis,
          client-call strategy, evidence, and architecture.
        </p>
      </div>
      <button className="btn btn-primary btn-lg" onClick={onNew}>
        <PlusCircle size={18} />
        Upload First RFP
      </button>
    </div>
  )
}
