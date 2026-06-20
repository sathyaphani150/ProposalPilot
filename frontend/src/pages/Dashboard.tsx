import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { FileText, PlusCircle, Clock } from 'lucide-react'
import { getErrorMessage } from '@/api/client'
import { rfpApi } from '@/api/endpoints'
import type { RFPSession, RFPStatus } from '@/types'
import { formatDistanceToNow } from 'date-fns'

const STATUS_CONFIG: Record<RFPStatus, { label: string; className: string }> = {
  uploaded: { label: 'Uploaded', className: 'badge badge-uploaded' },
  analyzing: { label: 'Analyzing...', className: 'badge badge-analyzing' },
  analyzed: { label: 'Analyzed', className: 'badge badge-analyzed' },
  analysis_failed: { label: 'Analysis Failed', className: 'badge badge-danger' },
  prep_generating: { label: 'Generating Prep', className: 'badge badge-analyzing' },
  prep_ready: { label: 'Prep Ready', className: 'badge badge-prep-ready' },
  war_room_running: { label: 'War Room Active', className: 'badge badge-war-room' },
  war_room_done: { label: 'War Room Done', className: 'badge badge-prep-ready' },
  proposal_ready: { label: 'Proposal Ready', className: 'badge badge-done' },
}

export function Dashboard() {
  const navigate = useNavigate()
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['rfp-sessions'],
    queryFn: () => rfpApi.list({ limit: 20 }),
  })

  useEffect(() => {
    if (isError && error) toast.error(getErrorMessage(error))
  }, [isError, error])

  const sessions = data?.items ?? []
  const total = data?.total ?? 0
  const pipelineStages = [
    { label: 'Uploaded', count: sessions.filter((s) => s.status === 'uploaded').length },
    { label: 'Analyzing', count: sessions.filter((s) => ['analyzing', 'prep_generating'].includes(s.status)).length },
    { label: 'Analyzed', count: sessions.filter((s) => ['analyzed', 'prep_ready'].includes(s.status)).length },
    { label: 'War Room', count: sessions.filter((s) => ['war_room_running', 'war_room_done'].includes(s.status)).length },
    { label: 'Proposal Ready', count: sessions.filter((s) => s.status === 'proposal_ready').length },
  ]

  const getNextAction = (session: RFPSession) => {
    switch (session.status) {
      case 'uploaded':
        return { label: 'Analyze RFP', path: `/rfp/${session.id}/analysis` }
      case 'analyzed':
      case 'prep_ready':
        return { label: 'View Analysis', path: `/rfp/${session.id}/analysis` }
      case 'war_room_done':
        return { label: 'View War Room', path: `/rfp/${session.id}/war-room` }
      default:
        return { label: 'View', path: `/rfp/${session.id}/analysis` }
    }
  }

  return (
    <div className="content-stack">
      <div className="page-header">
        <div>
          <h1>Mission Control</h1>
          <p className="page-subtitle">Manage your RFP engagements and AI-generated proposals</p>
        </div>
        <button className="btn btn-primary btn-lg" onClick={() => navigate('/rfp/new')}>
          <PlusCircle size={18} />
          New RFP
        </button>
      </div>

      <div className="panel panel--raised">
        <div className="flex items-center justify-between flex-wrap gap-4 mb-4">
          <div>
            <span className="text-xs text-muted">Total RFPs</span>
            <div className="mono-data pipeline-count">
              {isLoading ? <span className="skeleton" style={{ width: 48, height: 32, display: 'inline-block' }} /> : total}
            </div>
          </div>
          <span className="badge badge-analyzed">Pipeline Funnel</span>
        </div>
        <div className="pipeline-funnel">
          {pipelineStages.map((stage) => (
            <div className="pipeline-step" key={stage.label}>
              <span>{stage.label}</span>
              <span className="mono-data pipeline-count">{isLoading ? '-' : stage.count}</span>
            </div>
          ))}
        </div>
      </div>

      <section>
        <div className="flex items-center justify-between mb-4">
          <h2>Recent Engagements</h2>
          <span className="text-xs text-muted mono-data">{total} total</span>
        </div>

        {isLoading ? (
          <div className="content-stack">
            {[1, 2, 3].map((i) => <div key={i} className="skeleton panel" style={{ height: 80 }} />)}
          </div>
        ) : sessions.length === 0 ? (
          <EmptyState onNew={() => navigate('/rfp/new')} />
        ) : (
          <div className="content-stack">
            {sessions.map((session) => {
              const nextAction = getNextAction(session)
              const config = STATUS_CONFIG[session.status] ?? STATUS_CONFIG.uploaded
              return (
                <div key={session.id} className="panel session-row" onClick={() => navigate(nextAction.path)}>
                  <div className="flex items-center gap-3">
                    <div className="icon-chip"><FileText size={20} /></div>
                    <div>
                      <div className="font-semibold mb-2">{session.title}</div>
                      <div className="flex items-center gap-2 flex-wrap">
                        {session.client_name ? <span className="text-xs text-muted">{session.client_name}</span> : null}
                        <span className="text-xs text-muted">
                          <Clock size={11} style={{ display: 'inline', marginRight: 3 }} />
                          {formatDistanceToNow(new Date(session.created_at), { addSuffix: true })}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className={config.className}>{config.label}</span>
                    <button className="btn btn-secondary btn-sm" onClick={(e) => { e.stopPropagation(); navigate(nextAction.path) }}>
                      {nextAction.label}
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}

function EmptyState({ onNew }: { onNew: () => void }) {
  return (
    <div className="panel panel--raised empty-state">
      <svg className="empty-illustration" viewBox="0 0 120 90" role="img" aria-label="RFP command table">
        <path d="M16 68h88" stroke="currentColor" strokeWidth="2" opacity=".35" />
        <rect x="27" y="18" width="42" height="54" rx="5" fill="none" stroke="currentColor" strokeWidth="2" />
        <path d="M36 31h24M36 42h18M36 53h24" stroke="currentColor" strokeWidth="2" opacity=".8" />
        <path d="M76 28l18 10-18 10z" fill="currentColor" opacity=".22" />
        <circle cx="92" cy="58" r="7" fill="currentColor" opacity=".3" />
      </svg>
      <div>
        <h3 className="mb-2">No RFPs Yet</h3>
        <p className="text-muted max-readable">
          Upload your first RFP document to generate a leadership-ready RFP analysis, client-call strategy, evidence, and architecture.
        </p>
      </div>
      <button className="btn btn-primary btn-lg" onClick={onNew}>
        <PlusCircle size={18} />
        Upload First RFP
      </button>
    </div>
  )
}
