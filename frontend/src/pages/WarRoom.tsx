import { useState } from 'react'
import type { ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  Bot,
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
import type { AgentName, WarRoomSession } from '@/types'

const agentConfig: Array<{ key: AgentName; label: string; icon: ReactNode; color: string }> = [
  { key: 'architect', label: 'Tech Architect', icon: <UserRoundCog size={20} />, color: 'var(--color-primary-light)' },
  { key: 'cfo', label: 'CFO / Pricing', icon: <Calculator size={20} />, color: 'var(--color-success)' },
  { key: 'competitor', label: 'Competitor Strategist', icon: <Shield size={20} />, color: 'var(--color-warning)' },
  { key: 'proposal', label: 'Proposal Writer', icon: <FileText size={20} />, color: 'var(--color-info)' },
  { key: 'supervisor', label: 'Supervisor', icon: <Bot size={20} />, color: 'var(--color-accent)' },
]

function formatOutputValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => `- ${typeof item === 'string' ? item : JSON.stringify(item, null, 2)}`).join('\n')
  }
  if (value && typeof value === 'object') {
    return JSON.stringify(value, null, 2)
  }
  return String(value ?? '')
}

function renderAgentOutput(agent: AgentName, output: unknown): string {
  if (!output) return 'No output generated.'
  if (typeof output === 'string') return output
  if (!output || typeof output !== 'object') return String(output)

  const typed = output as Record<string, unknown>
  const sections: string[] = []
  const add = (label: string, key: string) => {
    if (typed[key] !== undefined && typed[key] !== null && typed[key] !== '') {
      sections.push(`${label}\n${formatOutputValue(typed[key])}`)
    }
  }

  if (agent === 'architect') {
    add('Architecture Summary', 'architecture_summary')
    add('Recommended Stack', 'recommended_stack')
    add('Reusable Components', 'reusable_components')
    add('Assumptions', 'assumptions')
    add('Technical Risks', 'technical_risks')
    add('Validation Questions', 'validation_questions')
  } else if (agent === 'cfo') {
    add('Team Structure', 'team_structure')
    add('Estimated Duration (weeks)', 'estimated_duration_weeks')
    add('Effort Breakdown', 'effort_breakdown')
    add('Cost Estimate', 'cost_estimate')
    add('Financial Risks', 'financial_risks')
    add('Margin Assessment', 'margin_assessment')
  } else if (agent === 'competitor') {
    add('Differentiators', 'differentiators')
    add('Win Themes', 'win_themes')
    add('Competitive Risks', 'competitive_risks')
    add('Value Proposition', 'value_proposition')
    add('Executive Messaging', 'executive_messaging')
  } else {
    if (agent === 'supervisor') {
      add('Status', 'status')
      add('Summary', 'summary')
      add('Timeline (weeks)', 'timeline_weeks')
      add('Approval Notes', 'approval_notes')
      add('Confidence', 'confidence')
      add('Loop Reason', 'loop_reason')
      add('Should Loop', 'should_loop')
      return sections.length > 0 ? sections.join('\n\n') : JSON.stringify(output, null, 2)
    }
    add('Executive Summary', 'executive_summary')
    add('Proposed Solution', 'proposed_solution')
    add('Architecture Section', 'architecture_section')
    add('Delivery Approach', 'delivery_approach')
    add('Cost Section', 'cost_section')
    add('Competitive Positioning', 'competitive_positioning')
    add('Risks', 'risks')
    add('Assumptions', 'assumptions')
    add('Exclusions', 'exclusions')
  }

  add('Reasoning', 'reasoning')
  add('Confidence', 'confidence')

  return sections.length > 0 ? sections.join('\n\n') : JSON.stringify(output, null, 2)
}

export function WarRoom() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const [callNotes, setCallNotes] = useState('')
  const [overrideText, setOverrideText] = useState('')

  const { data: session } = useQuery({
    queryKey: ['rfpSession', sessionId],
    queryFn: () => rfpApi.getById(sessionId!),
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

  const { mutate: startWarRoom, isPending: isStarting } = useMutation({
    mutationFn: () => warRoomApi.start(sessionId!, callNotes),
    onSuccess: () => {
      toast.success('War Room completed with grounded agent perspectives.')
      refetch()
    },
    onError: (error) => toast.error('Failed to run War Room: ' + getErrorMessage(error)),
  })

  const { mutate: applyOverride, isPending: isOverriding } = useMutation({
    mutationFn: () => warRoomApi.override(sessionId!, { guidance: overrideText }),
    onSuccess: () => {
      toast.success('Human guidance applied and War Room regenerated.')
      setOverrideText('')
      refetch()
    },
    onError: (error) => toast.error('Failed to apply override: ' + getErrorMessage(error)),
  })

  const busy = isLoading || isStarting || isOverriding

  return (
    <div className="fade-in">
      <div className="flex justify-between items-center" style={{ marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <BriefcaseBusiness size={28} color="var(--color-primary-light)" />
            Agent War Room
          </h1>
          <p style={{ color: 'var(--color-text-secondary)', marginTop: '0.35rem' }}>
            {session?.title || 'RFP Session'} - Architect, CFO, Competitor, and Proposal strategy
          </p>
        </div>
        <div className="flex gap-3">
          <button className="btn btn-secondary" onClick={() => navigate(`/rfp/${sessionId}/analysis`)}>
            Back to RFP Analysis
          </button>
          <button className="btn btn-primary" onClick={() => startWarRoom()} disabled={busy}>
            {busy ? <div className="spinner" style={{ width: 14, height: 14 }} /> : <RefreshCw size={16} />}
            {warRoom ? 'Regenerate War Room' : 'Run War Room'}
          </button>
        </div>
      </div>

      <div className="card-elevated" style={{ marginBottom: '1.5rem' }}>
        <div className="grid-2">
          <div>
            <label className="form-label">Call Notes / Clarifications</label>
            <textarea
              className="textarea"
              value={callNotes}
              onChange={(event) => setCallNotes(event.target.value)}
              placeholder="Paste prospect-call notes, constraints, or stakeholder clarifications here before running the War Room."
              style={{ minHeight: 130 }}
            />
          </div>
          <div>
            <label className="form-label">Human Override</label>
            <textarea
              className="textarea"
              value={overrideText}
              onChange={(event) => setOverrideText(event.target.value)}
              placeholder="Example: Use offshore-heavy model, reduce scope to MVP, keep architecture simple..."
              style={{ minHeight: 130 }}
            />
            <button
              className="btn btn-secondary"
              style={{ marginTop: '0.75rem' }}
              onClick={() => applyOverride()}
              disabled={busy || !overrideText.trim()}
            >
              Apply Override
            </button>
          </div>
        </div>
      </div>

      {!warRoom ? (
        <div className="card text-center" style={{ padding: '4rem' }}>
          <Lightbulb size={48} color="var(--color-text-muted)" style={{ margin: '0 auto 1rem' }} />
          <h3 style={{ marginBottom: '0.5rem' }}>No War Room Run Yet</h3>
          <p style={{ color: 'var(--color-text-secondary)', marginBottom: '1.5rem' }}>
            Run the War Room after reviewing the RFP analysis to get multi-role proposal strategy.
          </p>
          <button className="btn btn-primary" onClick={() => startWarRoom()} disabled={busy}>
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

          <div style={{ display: 'grid', gap: '1rem' }}>
            {agentConfig.map((agent) => (
              <div key={agent.key} className="card">
                <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', color: agent.color }}>
                  {agent.icon}
                  {agent.label}
                </h3>
                <pre
                  style={{
                    whiteSpace: 'pre-wrap',
                    color: 'var(--color-text-secondary)',
                    fontFamily: 'var(--font-sans)',
                    lineHeight: 1.6,
                    margin: 0,
                  }}
                >
                {renderAgentOutput(agent.key, warRoom.agent_outputs?.[agent.key])}
              </pre>
            </div>
          ))}
        </div>

        {warRoom.discussion_log?.length ? (
          <div className="card" style={{ marginTop: '1rem' }}>
            <h3 style={{ marginBottom: '1rem', color: 'var(--color-text-primary)' }}>Discussion Log</h3>
            <div style={{ display: 'grid', gap: '0.75rem' }}>
              {warRoom.discussion_log.map((entry, index) => (
                <div key={`${entry.agent}-${index}`} style={{ padding: '0.85rem 1rem', borderRadius: '14px', background: 'var(--color-surface-2)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', marginBottom: '0.35rem' }}>
                    <strong style={{ color: 'var(--color-primary-light)' }}>{entry.agent} → {entry.target_agent}</strong>
                    <span style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>{entry.timestamp ? new Date(entry.timestamp).toLocaleString() : 'just now'}</span>
                  </div>
                  <p style={{ margin: 0, color: 'var(--color-text-secondary)', lineHeight: 1.6 }}>{entry.comment}</p>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {warRoom.final_recommendations ? (
          <div className="card" style={{ marginTop: '1rem' }}>
            <h3 style={{ marginBottom: '1rem', color: 'var(--color-text-primary)' }}>Supervisor Validation</h3>
            <pre style={{ whiteSpace: 'pre-wrap', margin: 0, color: 'var(--color-text-secondary)', fontFamily: 'var(--font-sans)', lineHeight: 1.6 }}>
              {JSON.stringify(warRoom.final_recommendations, null, 2)}
            </pre>
          </div>
        ) : null}
      </>
      )}
    </div>
  )
}
