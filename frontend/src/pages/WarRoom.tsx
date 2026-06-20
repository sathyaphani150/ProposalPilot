import { useState } from 'react'
import type { CSSProperties } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  BriefcaseBusiness,
  Lightbulb,
  RefreshCw,
} from 'lucide-react'

import { rfpApi, warRoomApi } from '@/api/endpoints'
import { getErrorMessage } from '@/api/client'
import { useWarRoom } from '@/hooks/useWarRoom'
import { agentConfig } from '@/config/agents'
import type { AgentName, AgentStatus, WarRoomAgentOutput, WarRoomSession } from '@/types'

function stripGeneratedBy(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => stripGeneratedBy(item))
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .filter(([key]) => key !== 'generated_by')
        .map(([key, nestedValue]) => [key, stripGeneratedBy(nestedValue)]),
    )
  }
  return value
}

function formatOutputValue(value: unknown): string {
  const cleanedValue = stripGeneratedBy(value)

  if (Array.isArray(cleanedValue)) {
    return cleanedValue
      .map((item) => {
        if (typeof item === 'string') return `- ${item}`
        if (item && typeof item === 'object') {
          return `- ${Object.entries(item as Record<string, unknown>)
            .map(([key, nestedValue]) => `${key}: ${typeof nestedValue === 'object' ? JSON.stringify(nestedValue) : String(nestedValue)}`)
            .join(', ')}`
        }
        return `- ${String(item)}`
      })
      .join('\n')
  }
  if (cleanedValue && typeof cleanedValue === 'object') {
    return Object.entries(cleanedValue as Record<string, unknown>)
      .map(([key, nestedValue]) => `${key}: ${typeof nestedValue === 'object' ? JSON.stringify(nestedValue) : String(nestedValue)}`)
      .join('\n')
  }
  return String(cleanedValue ?? '')
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
    add('Architecture Pattern', 'architecture_pattern')
    add('Recommended Stack', 'recommended_stack')
    add('Reusable Components', 'reusable_components')
    add('Assumptions', 'assumptions')
    add('Technical Risks', 'technical_risks')
    add('Validation Questions', 'validation_questions')
  } else if (agent === 'cfo') {
    add('Team Structure', 'team_structure')
    add('Estimated Duration (weeks)', 'estimated_duration_weeks')
    add('Effort Breakdown', 'effort_breakdown')
    add('Pricing Model', 'pricing_model_recommendation')
    add('Cost Estimate', 'cost_estimate')
    add('Financial Risks', 'financial_risks')
    add('Margin Assessment', 'margin_assessment')
  } else if (agent === 'competitor') {
    add('Positioning Strategy', 'positioning_strategy')
    add('Differentiators', 'differentiators')
    add('Win Themes', 'win_themes')
    add('Competitive Risks', 'competitive_risks')
    add('Value Proposition', 'value_proposition')
    add('Executive Messaging', 'executive_messaging')
  } else {
    add('Executive Summary', 'executive_summary')
    add('Client Problem Restatement', 'client_problem_restatement')
    add('Proposed Solution Narrative', 'proposed_solution_narrative')
    add('Proposed Solution', 'proposed_solution')
    add('Architecture Section', 'architecture_section')
    add('Commercial Summary', 'commercial_summary')
    add('Delivery Approach', 'delivery_approach')
    add('Cost Section', 'cost_section')
    add('Competitive Positioning', 'competitive_positioning')
    add('Compliance Matrix', 'compliance_matrix')
    add('Open Risks And Assumptions', 'open_risks_and_assumptions')
    add('Consistency Flags', 'consistency_flags')
    add('Risks', 'risks')
    add('Assumptions', 'assumptions')
    add('Exclusions', 'exclusions')
  }

  add('Reasoning', 'reasoning')
  add('Confidence', 'confidence')

  return sections.length > 0 ? sections.join('\n\n') : JSON.stringify(stripGeneratedBy(output), null, 2)
}

function parseOutputSections(outputText: string) {
  return outputText.split('\n\n').map((section) => {
    const [label, ...valueLines] = section.split('\n')
    return { label, value: valueLines.join('\n').trim() }
  }).filter((section) => section.label)
}

function confidencePercent(value: unknown) {
  if (typeof value !== 'number' || Number.isNaN(value)) return null
  return Math.round((value <= 1 ? value * 100 : value))
}

function getAgentStatus(agent: AgentName, liveStatus: AgentStatus | undefined, warRoom: WarRoomSession): AgentStatus {
  if (liveStatus) return liveStatus
  if (warRoom.agent_outputs?.[agent]) return 'done'
  if (warRoom.status === 'running') return 'thinking'
  if (warRoom.status === 'failed') return 'error'
  return 'idle'
}

function statusBadgeClass(status: AgentStatus) {
  if (status === 'done') return 'badge-done'
  if (status === 'error') return 'badge-danger'
  if (status === 'thinking' || status === 'writing') return 'badge-war-room'
  return 'badge-uploaded'
}

function OutputValue({ label, value }: { label: string; value: string }) {
  if (label === 'Confidence') {
    const percent = confidencePercent(Number(value))
    return percent === null ? <p className="readable-text">{value}</p> : (
      <div className="confidence-meter">
        <div className="confidence-track"><div className="confidence-fill" style={{ width: `${percent}%` }} /></div>
        <span className="mono-data">{percent}%</span>
      </div>
    )
  }

  const lines = value.split('\n').map((line) => line.replace(/^-\s*/, '').trim()).filter(Boolean)
  if (lines.length > 1 || value.trim().startsWith('- ')) {
    return (
      <div className="chip-list">
        {lines.map((line, index) => <span className="output-chip" key={`${line}-${index}`}>{line}</span>)}
      </div>
    )
  }

  return <p className="readable-text">{value}</p>
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
    refetchInterval: (query) => {
      const latestWarRoom = (query.state.data as { war_room?: WarRoomSession | null } | undefined)?.war_room
      return latestWarRoom?.status === 'running' ? 2000 : false
    },
  })

  const warRoom = statusResponse?.war_room as WarRoomSession | null | undefined
  const { agentStatus } = useWarRoom(warRoom?.id)

  const { mutate: startWarRoom, isPending: isStarting } = useMutation({
    mutationFn: () => warRoomApi.start(sessionId!, callNotes),
    onSuccess: () => {
      toast.success('War Room started. Agent outputs will appear as the run completes.')
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
  const completedOutputs = agentConfig
    .map((agent) => warRoom?.agent_outputs?.[agent.key] as WarRoomAgentOutput | undefined)
    .filter((output): output is WarRoomAgentOutput => Boolean(output))
  const averageConfidence = completedOutputs.length
    ? Math.round(completedOutputs.reduce((sum, output) => sum + (confidencePercent(output.confidence) || 0), 0) / completedOutputs.length)
    : null
  const hasFallback = completedOutputs.some((output) => output.generated_by === 'deterministic_fallback')

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <div className="page-title">
            <BriefcaseBusiness size={28} color="var(--color-accent)" />
            <h1>Agent War Room</h1>
          </div>
          <p className="page-subtitle">
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

      <div className="panel panel--raised mb-4">
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
              className="btn btn-secondary mt-3"
              onClick={() => applyOverride()}
              disabled={busy || !overrideText.trim()}
            >
              Apply Override
            </button>
          </div>
        </div>
      </div>

      {!warRoom ? (
        <div className="panel panel--raised empty-state">
          <Lightbulb size={48} color="var(--color-accent)" />
          <h3>No War Room Run Yet</h3>
          <p className="page-subtitle">
            Run the War Room after reviewing the RFP analysis to get multi-role proposal strategy.
          </p>
          <button className="btn btn-primary" onClick={() => startWarRoom()} disabled={busy}>
            Run War Room
          </button>
        </div>
      ) : (
        <>
          <div className="panel mb-4">
            <div className="flex justify-between items-center flex-wrap gap-4">
              <div>
                <span
                  className={`badge ${
                    warRoom.status === 'failed'
                      ? ''
                      : warRoom.status === 'complete'
                        ? 'badge-done'
                        : 'badge-war-room'
                  }`}
                  style={{ textTransform: 'uppercase' }}
                >
                  {warRoom.status}
                </span>
                <span className="text-secondary mt-3">
                  Matched projects: <span className="mono-data">{warRoom.matched_projects?.length || 0}</span>
                </span>
              </div>
              <span className="text-muted text-sm mono-data">
                Generated {new Date(warRoom.updated_at || warRoom.created_at).toLocaleString()}
              </span>
            </div>
          </div>

          {warRoom.status === 'complete' ? (
            <div className="panel panel--raised mb-4">
              <div className="verdict-grid">
                <div>
                  <h3>Verdict Summary</h3>
                  <p className="text-secondary text-sm">Four-role synthesis complete</p>
                </div>
                <div className="stat-tile">
                  <span className="text-xs text-muted">Overall Confidence</span>
                  <div className="mono-data pipeline-count">{averageConfidence ?? 0}%</div>
                </div>
                <div className="stat-tile">
                  <span className="text-xs text-muted">Matched Projects</span>
                  <div className="mono-data pipeline-count">{warRoom.matched_projects?.length || 0}</div>
                </div>
                {hasFallback ? <span className="badge badge-analyzing">One or more seats used fallback output</span> : <span className="badge badge-done">All seats AI-generated</span>}
              </div>
            </div>
          ) : null}

          {warRoom.error_message ? (
            <div className="panel mb-4" style={{ borderColor: 'rgba(255, 107, 107, 0.35)' }}>
              <h3 className="mb-2" style={{ color: 'var(--color-error)' }}>War Room Failed</h3>
              <p className="readable-text">{warRoom.error_message}</p>
            </div>
          ) : null}

          <div className="agent-grid">
            {agentConfig.map((agent) => {
              const status = getAgentStatus(agent.key, agentStatus[agent.key], warRoom)
              const agentOutput = warRoom.agent_outputs?.[agent.key] as WarRoomAgentOutput | undefined
              const sections = parseOutputSections(renderAgentOutput(agent.key, agentOutput))
              return (
              <div key={agent.key} className="panel agent-seat" style={{ '--agent-color': agent.color } as CSSProperties}>
                <div className="agent-seat__header">
                  <h3 className="agent-name">
                    {agent.icon}
                    {agent.label}
                  </h3>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`badge status-chip ${statusBadgeClass(status)}`}>
                      <span className="status-dot" />
                      {status}
                    </span>
                    {(status === 'thinking' || status === 'writing') ? (
                      <span className="thinking-indicator" aria-label={`${agent.label} ${status}`}>
                        <span /><span /><span />
                      </span>
                    ) : null}
                  </div>
                </div>
                <div className="agent-output">
                  {sections.map((section) => (
                    <div className="agent-section" key={`${agent.key}-${section.label}`}>
                      <h4>{section.label}</h4>
                      <OutputValue label={section.label} value={section.value} />
                    </div>
                  ))}
                </div>
              </div>
            )})}
          </div>
        </>
      )}
    </div>
  )
}
