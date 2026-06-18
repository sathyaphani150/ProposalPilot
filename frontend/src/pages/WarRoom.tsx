import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  BriefcaseBusiness,
  Calculator,
  FileText,
  Lightbulb,
  RefreshCw,
  Shield,
  UserRoundCog,
} from 'lucide-react'
import { rfpApi, warRoomApi } from '@/api/endpoints'
import { getErrorMessage } from '@/api/client'
import type { RFPAnalysis, WarRoomResult, WarRoomSession } from '@/types'

function SectionCard({
  title,
  icon,
  children,
}: {
  title: string
  icon: ReactNode
  children: ReactNode
}) {
  return (
    <div className="insight-card">
      <h3 className="section-title">
        {icon}
        {title}
      </h3>
      {children}
    </div>
  )
}

function ListBlock({ items, empty }: { items?: string[]; empty: string }) {
  if (!items || items.length === 0) {
    return <p className="readable-text" style={{ color: 'var(--color-text-muted)' }}>{empty}</p>
  }
  return (
    <ul className="clean-list">
      {items.map((item, index) => (
        <li key={`${item}-${index}`}>{item}</li>
      ))}
    </ul>
  )
}

function parseGuidance(value: string): string[] {
  return value
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function asObject(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {}
}

function asText(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (Array.isArray(value)) return value.map(asText).filter(Boolean).join(', ')
  if (typeof value === 'object') return ''
  return String(value)
}

export function WarRoom() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const [guidanceText, setGuidanceText] = useState('Reduce scope to MVP\nUse Azure\nKeep costs low')
  const [autoRunAttempted, setAutoRunAttempted] = useState(false)

  const { data: session } = useQuery({
    queryKey: ['rfpSession', sessionId],
    queryFn: () => rfpApi.getById(sessionId!),
    enabled: !!sessionId,
  })

  const { data: analysisResponse } = useQuery({
    queryKey: ['rfpAnalysisForWarRoom', sessionId],
    queryFn: () => rfpApi.getAnalysis(sessionId!),
    enabled: !!sessionId,
  })

  const {
    data: statusResponse,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ['warRoomStatus', sessionId],
    queryFn: () => warRoomApi.getStatus(sessionId!),
    enabled: !!sessionId,
  })

  const warRoom = statusResponse?.war_room as WarRoomSession | null | undefined
  const analysis = analysisResponse?.analysis as RFPAnalysis | null | undefined
  const warRoomResult = warRoom?.agent_outputs as Partial<WarRoomResult> | undefined
  const analysisId = analysis?.id

  const { mutate: runWarRoom, isPending: isRunning } = useMutation({
    mutationFn: () => warRoomApi.run(analysisId!),
    onSuccess: () => {
      toast.success('War Room completed with structured agent outputs.')
      refetch()
    },
    onError: (error) => toast.error('Failed to run War Room: ' + getErrorMessage(error)),
  })

  const { mutate: rerunWarRoom, isPending: isRerunning } = useMutation({
    mutationFn: () => warRoomApi.rerun(analysisId!, parseGuidance(guidanceText)),
    onSuccess: () => {
      toast.success('War Room re-run with your guidance.')
      refetch()
    },
    onError: (error) => toast.error('Failed to rerun War Room: ' + getErrorMessage(error)),
  })

  const busy = isLoading || isRunning || isRerunning

  useEffect(() => {
    if (analysisId && !warRoom && !autoRunAttempted) {
      setAutoRunAttempted(true)
      runWarRoom()
    }
  }, [analysisId, autoRunAttempted, runWarRoom, warRoom])

  const architect = asObject(warRoomResult?.architect)
  const cfo = asObject(warRoomResult?.cfo)
  const competitor = asObject(warRoomResult?.competitor)
  const proposal = asObject(warRoomResult?.proposal)
  const guidanceItems = useMemo(() => parseGuidance(guidanceText), [guidanceText])

  return (
    <div className="fade-in">
      <div className="flex justify-between items-center" style={{ marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <BriefcaseBusiness size={28} color="var(--color-primary-light)" />
            Agent War Room
          </h1>
          <p style={{ color: 'var(--color-text-secondary)', marginTop: '0.35rem' }}>
            {session?.title || 'RFP Session'} - Architecture, finance, competitor, and proposal strategy
          </p>
        </div>
        <div className="flex gap-3">
          <button className="btn btn-secondary" onClick={() => navigate(`/rfp/${sessionId}/prep-pack`)}>
            Back to Prep Pack
          </button>
          <button className="btn btn-primary" onClick={() => runWarRoom()} disabled={busy || !analysisId}>
            {busy ? <div className="spinner" style={{ width: 14, height: 14 }} /> : <RefreshCw size={16} />}
            Run War Room
          </button>
        </div>
      </div>

      <div className="card-elevated" style={{ marginBottom: '1.5rem' }}>
        <div className="grid-2">
          <div>
            <label className="form-label">Human Guidance</label>
            <textarea
              className="textarea"
              value={guidanceText}
              onChange={(event) => setGuidanceText(event.target.value)}
              placeholder="Reduce scope to MVP, use Azure, keep costs low..."
              style={{ minHeight: 130 }}
            />
          </div>
          <div>
            <label className="form-label">Guidance Notes</label>
            <div className="insight-card" style={{ minHeight: 130 }}>
              <ListBlock items={guidanceItems} empty="Add guidance to steer the War Room rerun." />
            </div>
            <button className="btn btn-secondary" style={{ marginTop: '0.75rem' }} onClick={() => rerunWarRoom()} disabled={busy || guidanceItems.length === 0 || !analysisId}>
              Re-run War Room
            </button>
          </div>
        </div>
      </div>

      {!warRoom ? (
        <div className="card text-center" style={{ padding: '4rem' }}>
          <Lightbulb size={48} color="var(--color-text-muted)" style={{ margin: '0 auto 1rem' }} />
          <h3 style={{ marginBottom: '0.5rem' }}>No War Room Run Yet</h3>
          <p style={{ color: 'var(--color-text-secondary)', marginBottom: '1.5rem' }}>
            Run the War Room after analysis to get structured architect, CFO, competitor, and proposal outputs.
          </p>
          <button className="btn btn-primary" onClick={() => runWarRoom()} disabled={busy || !analysisId}>
            Run War Room
          </button>
        </div>
      ) : (
        <>
          <div className="card" style={{ marginBottom: '1.5rem' }}>
            <div className="flex justify-between items-center" style={{ flexWrap: 'wrap', gap: '1rem' }}>
              <div>
                <span className="badge badge-done" style={{ textTransform: 'uppercase' }}>
                  {warRoom.status}
                </span>
                <span style={{ marginLeft: '0.75rem', color: 'var(--color-text-secondary)' }}>
                  Matched projects: {warRoom.matched_projects?.length || 0}
                </span>
              </div>
              <span style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
                Generated {new Date(warRoom.updated_at || warRoom.created_at).toLocaleString()}
              </span>
            </div>
          </div>
        </>
      )}

      {warRoomResult && (
        <div className="content-stack" style={{ marginTop: '1.5rem' }}>
          <div className="prep-two-column">
            <SectionCard title="Architect Recommendations" icon={<UserRoundCog size={20} color="var(--color-primary-light)" />}>
              <p className="readable-text">{asText(architect.solution_design) || asText(architect.architecture_summary) || 'No architecture output generated.'}</p>
              <div style={{ marginTop: '0.75rem' }}>
                <h4 style={{ marginBottom: '0.5rem' }}>Technology Stack</h4>
                <ListBlock items={Array.isArray(architect.technology_stack) ? architect.technology_stack.map(asText).filter(Boolean) : []} empty="No technology stack generated." />
              </div>
              <div style={{ marginTop: '0.75rem' }}>
                <h4 style={{ marginBottom: '0.5rem' }}>Assumptions</h4>
                <ListBlock items={Array.isArray(architect.assumptions) ? architect.assumptions.map(asText).filter(Boolean) : []} empty="No assumptions generated." />
              </div>
              <div style={{ marginTop: '0.75rem' }}>
                <h4 style={{ marginBottom: '0.5rem' }}>Risks</h4>
                <ListBlock items={Array.isArray(architect.risks) ? architect.risks.map(asText).filter(Boolean) : []} empty="No risks generated." />
              </div>
            </SectionCard>
            <SectionCard title="CFO Estimates" icon={<Calculator size={20} color="var(--color-success)" />}>
              <div className="match-card">
                <p><strong>Team size:</strong> {asText(cfo.team_size) || 'N/A'}</p>
                <p><strong>Effort:</strong> {asText(cfo.effort_months) || 'N/A'} months</p>
                <p><strong>Estimated cost:</strong> {asText(cfo.estimated_cost) || 'N/A'}</p>
                <p><strong>Delivery model:</strong> {asText(cfo.delivery_model) || 'N/A'}</p>
              </div>
              <div style={{ marginTop: '0.75rem' }}>
                <h4 style={{ marginBottom: '0.5rem' }}>Cost Risks</h4>
                <ListBlock items={Array.isArray(cfo.cost_risks) ? cfo.cost_risks.map(asText).filter(Boolean) : []} empty="No cost risks generated." />
              </div>
            </SectionCard>
          </div>

          <div className="prep-two-column">
            <SectionCard title="Competitor Strategy" icon={<Shield size={20} color="var(--color-warning)" />}>
              <div style={{ marginBottom: '0.75rem' }}>
                <h4 style={{ marginBottom: '0.5rem' }}>Competitors</h4>
                <ListBlock items={Array.isArray(competitor.competitors) ? competitor.competitors.map(asText).filter(Boolean) : []} empty="No competitor list generated." />
              </div>
              <div style={{ marginBottom: '0.75rem' }}>
                <h4 style={{ marginBottom: '0.5rem' }}>Differentiators</h4>
                <ListBlock items={Array.isArray(competitor.differentiators) ? competitor.differentiators.map(asText).filter(Boolean) : []} empty="No differentiators generated." />
              </div>
              <div>
                <h4 style={{ marginBottom: '0.5rem' }}>Win Strategy</h4>
                <ListBlock items={Array.isArray(competitor.win_strategy) ? competitor.win_strategy.map(asText).filter(Boolean) : []} empty="No win strategy generated." />
              </div>
            </SectionCard>
            <SectionCard title="Proposal Summary" icon={<FileText size={20} color="var(--color-info)" />}>
              <p className="readable-text"><strong>Executive summary:</strong> {asText(proposal.executive_summary) || 'No proposal summary generated.'}</p>
              <p className="readable-text" style={{ marginTop: '0.75rem' }}><strong>Solution overview:</strong> {asText(proposal.solution_overview) || 'No solution overview generated.'}</p>
              <div style={{ marginTop: '0.75rem' }}>
                <h4 style={{ marginBottom: '0.5rem' }}>Differentiators</h4>
                <ListBlock items={Array.isArray(proposal.differentiators) ? proposal.differentiators.map(asText).filter(Boolean) : []} empty="No proposal differentiators generated." />
              </div>
            </SectionCard>
          </div>
        </div>
      )}
    </div>
  )
}
