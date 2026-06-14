import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Building,
  CheckCircle,
  Clock,
  Database,
  FileText,
  HelpCircle,
  Info,
  ListChecks,
  RotateCw,
  ShieldAlert,
  Target,
} from 'lucide-react'
import { rfpApi } from '@/api/endpoints'
import { getErrorMessage } from '@/api/client'
import type { ExecutiveInsight, ExecutiveIntelligence, ExecutiveReport, RFPAnalysis as RFPAnalysisType, RFPStatus } from '@/types'

function getStatusBadge(status: RFPStatus) {
  const labels: Record<RFPStatus, string> = {
    uploaded: 'Uploaded',
    analyzing: 'Analyzing',
    analyzed: 'Analyzed',
    analysis_failed: 'Failed',
    prep_generating: 'Generating Prep',
    prep_ready: 'Prep Ready',
    war_room_running: 'War Room Active',
    war_room_done: 'War Room Complete',
    proposal_ready: 'Proposal Ready',
  }
  const classes: Record<RFPStatus, string> = {
    uploaded: 'badge-uploaded',
    analyzing: 'badge-analyzing',
    analyzed: 'badge-analyzed',
    analysis_failed: 'badge-danger',
    prep_generating: 'badge-analyzing',
    prep_ready: 'badge-prep-ready',
    war_room_running: 'badge-war-room',
    war_room_done: 'badge-done',
    proposal_ready: 'badge-done',
  }
  return <span className={`badge ${classes[status]}`}>{labels[status]}</span>
}

function cleanDisplayText(value: string) {
  return value
    .replace(/\.{4,}\s*\d+/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

function usableItems(items?: string[]) {
  const blocked = new Set([
    'functional requirements',
    'non-functional requirements',
    'resource requirements',
    'checklist of documents',
    'documentation',
    'system documentation',
    'scope of work',
  ])
  return (items || [])
    .map(cleanDisplayText)
    .filter((item) => item.length > 14 && !blocked.has(item.toLowerCase()))
    .slice(0, 8)
}

function InsightSection({
  title,
  icon,
  items,
  empty,
  accent,
}: {
  title: string
  icon: ReactNode
  items?: string[]
  empty: string
  accent?: string
}) {
  const displayItems = usableItems(items)
  return (
    <div className="insight-card">
      <h3 className="section-title" style={accent ? { color: accent } : undefined}>
        {icon}
        {title}
        <span className="badge badge-uploaded" style={{ marginLeft: 'auto' }}>
          {displayItems.length}
        </span>
      </h3>
      {displayItems.length > 0 ? (
        <ul className="clean-list">
          {displayItems.map((item, index) => (
            <li key={`${title}-${index}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="readable-text" style={{ color: 'var(--color-text-muted)' }}>
          {empty}
        </p>
      )}
    </div>
  )
}

function sourceLabel(source: string) {
  const labels: Record<string, string> = {
    explicit_in_rfp: 'Explicit in RFP',
    inferred_from_rfp: 'Inferred from RFP',
    derived_from_industry_knowledge: 'Industry pattern',
  }
  return labels[source] || source.replaceAll('_', ' ')
}

function ExecutiveInsightCard({ item }: { item: ExecutiveInsight }) {
  return (
    <div className="match-card">
      <div className="flex justify-between items-center gap-3" style={{ marginBottom: '0.65rem' }}>
        <h4 style={{ margin: 0 }}>{item.title}</h4>
        <span className="badge badge-analyzed">{Math.round((item.confidence || 0) * 100)}%</span>
      </div>
      <p className="readable-text" style={{ color: 'var(--color-text-primary)' }}>{item.insight}</p>
      <p style={{ color: 'var(--color-text-muted)', fontSize: '0.86rem', marginTop: '0.75rem' }}>
        <strong>{sourceLabel(item.source)}:</strong> {cleanDisplayText(item.evidence || 'Evidence not available.')}
      </p>
      <p style={{ color: 'var(--color-primary-light)', fontSize: '0.9rem', marginTop: '0.75rem', lineHeight: 1.55 }}>
        {item.recommendation}
      </p>
    </div>
  )
}

function StrategicList({ items, empty }: { items?: string[]; empty: string }) {
  const displayItems = (items || []).map(cleanDisplayText).filter(Boolean)
  if (displayItems.length === 0) {
    return <p className="readable-text" style={{ color: 'var(--color-text-muted)' }}>{empty}</p>
  }
  return (
    <ul className="clean-list">
      {displayItems.map((item, index) => (
        <li key={`${item}-${index}`}>{item}</li>
      ))}
    </ul>
  )
}

function asText(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (Array.isArray(value)) return value.map(asText).filter(Boolean).join(', ')
  if (typeof value === 'object') return ''
  return String(value)
}

function asTextArray(value: unknown): string[] {
  if (!value) return []
  if (Array.isArray(value)) return value.map(asText).filter(Boolean)
  return [asText(value)].filter(Boolean)
}

function KeyValueGrid({ data, skip = [] }: { data?: Record<string, unknown>; skip?: string[] }) {
  const entries = Object.entries(data || {}).filter(([key, value]) => !skip.includes(key) && asText(value))
  if (entries.length === 0) return null
  return (
    <div className="grid-2" style={{ gap: '0.75rem' }}>
      {entries.map(([key, value]) => (
        <div className="match-card" key={key}>
          <span style={{ color: 'var(--color-text-muted)', fontSize: '0.78rem', textTransform: 'uppercase' }}>
            {key.replaceAll('_', ' ')}
          </span>
          <p className="readable-text" style={{ marginTop: '0.35rem' }}>{asText(value)}</p>
        </div>
      ))}
    </div>
  )
}

function ReportBullets({ items, empty }: { items?: unknown; empty: string }) {
  const displayItems = asTextArray(items)
  return <StrategicList items={displayItems} empty={empty} />
}

function RequirementCards({ items }: { items?: Array<Record<string, unknown>> }) {
  if (!items?.length) return <p className="readable-text">No solution requirements were normalized.</p>
  return (
    <div className="content-stack">
      {items.map((item, index) => (
        <div className="match-card" key={`${asText(item.requirement_name)}-${index}`}>
          <div className="flex justify-between items-center gap-3" style={{ marginBottom: '0.5rem' }}>
            <h4 style={{ margin: 0 }}>{asText(item.requirement_name) || 'Requirement'}</h4>
            <span className="badge badge-analyzed">{asText(item.category) || 'Scope'}</span>
          </div>
          <p className="readable-text" style={{ color: 'var(--color-text-primary)' }}>{asText(item.description)}</p>
          <p style={{ color: 'var(--color-primary-light)', fontSize: '0.88rem', marginTop: '0.65rem' }}>
            <strong>Priority:</strong> {asText(item.priority) || 'Medium'} · <strong>Confidence:</strong> {asText(item.confidence) || 'medium'}
          </p>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.86rem', marginTop: '0.65rem' }}>
            <strong>Evidence:</strong> {cleanDisplayText(asText(item.evidence) || 'Evidence not available.')}
          </p>
          <p className="readable-text" style={{ marginTop: '0.65rem' }}>{asText(item.interpretation)}</p>
        </div>
      ))}
    </div>
  )
}

function RiskCards({ items }: { items?: Array<Record<string, unknown>> }) {
  if (!items?.length) return <p className="readable-text">No executive risks were generated.</p>
  return (
    <div className="content-stack">
      {items.map((item, index) => (
        <div className="match-card" key={`${asText(item.risk_title)}-${index}`}>
          <div className="flex justify-between items-center gap-3" style={{ marginBottom: '0.5rem' }}>
            <h4 style={{ margin: 0 }}>{asText(item.risk_title) || 'Risk'}</h4>
            <span className="badge badge-danger">{asText(item.severity) || 'Medium'}</span>
          </div>
          <p className="readable-text"><strong>Impact:</strong> {asText(item.impact)}</p>
          <p className="readable-text"><strong>Mitigation:</strong> {asText(item.mitigation)}</p>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.86rem', marginTop: '0.5rem' }}>
            Probability: {asText(item.probability) || 'Medium'} · Owner: {asText(item.owner) || 'Joint'}
          </p>
        </div>
      ))}
    </div>
  )
}

function ExecutiveReportView({ report, analysis }: { report: ExecutiveReport; analysis: RFPAnalysisType }) {
  const tabs = [
    'CEO Brief',
    'Bid Decision',
    'Business Problem',
    'Solution Scope',
    'Missing Info',
    'Risks',
    'Delivery Plan',
    'Architecture',
    'CFO View',
    'Competitor Strategy',
    'Win Strategy',
    'Prospect Call Prep',
    'Proposal Outline',
    'Raw Extraction',
  ]
  const [activeTab, setActiveTab] = useState(tabs[0])
  const bid = report.bid_recommendation || {}
  const scoreBreakdown = bid.score_breakdown || {}
  const callPrep = report.prospect_call_prep || {}

  return (
    <div className="content-stack">
      <div className="card-elevated">
        <div className="prep-summary">
          <div>
            <h3 className="section-title">
              <Info size={20} color="var(--color-primary-light)" />
              CEO Brief
            </h3>
            <p className="readable-text" style={{ color: 'var(--color-text-primary)' }}>{report.ceo_brief}</p>
          </div>
          <div className="side-stack">
            <div className="insight-card" style={{ padding: '0.9rem' }}>
              <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>
                Bid decision
              </span>
              <strong style={{ display: 'block', marginTop: '0.35rem' }}>{bid.decision || 'Qualification needed'}</strong>
              <p style={{ color: 'var(--color-primary-light)', marginTop: '0.35rem' }}>
                Score: {String(bid.overall_score ?? 'N/A')}/100
              </p>
            </div>
            <ExtractionQuality analysis={analysis} />
          </div>
        </div>
      </div>

      <div className="insight-card" style={{ display: 'flex', gap: '0.5rem', overflowX: 'auto', padding: '0.65rem' }}>
        {tabs.map((tab) => (
          <button
            key={tab}
            className={`btn ${activeTab === tab ? 'btn-primary' : 'btn-secondary'}`}
            style={{ whiteSpace: 'nowrap', padding: '0.55rem 0.75rem' }}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      {activeTab === 'CEO Brief' && (
        <div className="prep-two-column">
          <div className="insight-card">
            <h3 className="section-title"><Info size={20} /> Executive Summary</h3>
            <p className="readable-text" style={{ color: 'var(--color-text-primary)' }}>{report.ceo_brief}</p>
          </div>
          <div className="insight-card">
            <h3 className="section-title"><Target size={20} /> Domain Signals</h3>
            <StrategicList items={analysis.domain_tags} empty="No domain tags generated." />
          </div>
        </div>
      )}

      {activeTab === 'Bid Decision' && (
        <div className="content-stack">
          <div className="insight-card">
            <h3 className="section-title"><Target size={20} /> {bid.decision || 'Bid Recommendation'}</h3>
            <p className="readable-text">{asText(bid.rationale)}</p>
          </div>
          <KeyValueGrid data={scoreBreakdown} />
        </div>
      )}

      {activeTab === 'Business Problem' && (
        <div className="insight-card">
          <h3 className="section-title"><Building size={20} /> Business Problem Intelligence</h3>
          <KeyValueGrid data={report.business_problem} />
        </div>
      )}

      {activeTab === 'Solution Scope' && (
        <div className="insight-card">
          <h3 className="section-title"><ListChecks size={20} /> Real Solution Scope</h3>
          <RequirementCards items={report.solution_scope} />
        </div>
      )}

      {activeTab === 'Missing Info' && (
        <div className="prep-two-column">
          {(report.missing_information || []).map((group) => (
            <div className="insight-card" key={group.category}>
              <h3 className="section-title"><HelpCircle size={20} /> {group.category}</h3>
              <StrategicList items={group.questions} empty="No questions generated." />
            </div>
          ))}
        </div>
      )}

      {activeTab === 'Risks' && (
        <div className="insight-card">
          <h3 className="section-title"><ShieldAlert size={20} /> Risk Assessment</h3>
          <RiskCards items={report.risk_assessment} />
        </div>
      )}

      {activeTab === 'Delivery Plan' && (
        <div className="insight-card">
          <h3 className="section-title"><Clock size={20} /> Delivery Complexity</h3>
          <KeyValueGrid data={report.delivery_complexity} />
        </div>
      )}

      {activeTab === 'Architecture' && (
        <div className="insight-card">
          <h3 className="section-title"><Database size={20} /> Architecture Recommendation</h3>
          <KeyValueGrid data={report.architecture_recommendation} />
        </div>
      )}

      {activeTab === 'CFO View' && (
        <div className="insight-card">
          <h3 className="section-title"><Activity size={20} /> Commercial / CFO Intelligence</h3>
          <KeyValueGrid data={report.commercial_intelligence} />
        </div>
      )}

      {activeTab === 'Competitor Strategy' && (
        <div className="content-stack">
          {(report.competitor_intelligence || []).map((item, index) => (
            <div className="match-card" key={`${asText(item.competitor_category)}-${index}`}>
              <h4>{asText(item.competitor_category)}</h4>
              <KeyValueGrid data={item} skip={['competitor_category']} />
            </div>
          ))}
        </div>
      )}

      {activeTab === 'Win Strategy' && (
        <div className="insight-card">
          <h3 className="section-title"><CheckCircle size={20} /> Win Strategy</h3>
          <StrategicList items={report.win_strategy} empty="No win strategy generated." />
        </div>
      )}

      {activeTab === 'Prospect Call Prep' && (
        <div className="content-stack">
          <div className="insight-card">
            <h3 className="section-title"><Target size={20} /> 30-second Opening</h3>
            <p className="readable-text">{asText(callPrep.opening_narrative_30_seconds)}</p>
          </div>
          <div className="prep-two-column">
            <InsightSection title="Strongest Talking Points" icon={<CheckCircle size={18} />} items={asTextArray(callPrep.strongest_talking_points)} empty="No talking points." />
            <InsightSection title="Avoid Overcommitting" icon={<AlertTriangle size={18} />} items={asTextArray(callPrep.avoid_overcommitting_on)} empty="No guardrails." />
          </div>
          <div className="prep-two-column">
            <InsightSection title="Technical Questions" icon={<Database size={18} />} items={asTextArray(callPrep.technical_questions)} empty="No technical questions." />
            <InsightSection title="Commercial Questions" icon={<Activity size={18} />} items={asTextArray(callPrep.commercial_questions)} empty="No commercial questions." />
          </div>
          <div className="prep-two-column">
            <InsightSection title="Risk Questions" icon={<ShieldAlert size={18} />} items={asTextArray(callPrep.risk_questions)} empty="No risk questions." />
            <InsightSection title="Assumptions to Validate" icon={<HelpCircle size={18} />} items={asTextArray(callPrep.assumptions_to_validate)} empty="No assumptions." />
          </div>
        </div>
      )}

      {activeTab === 'Proposal Outline' && (
        <div className="prep-two-column">
          <div className="insight-card">
            <h3 className="section-title"><FileText size={20} /> Proposal Outline</h3>
            <StrategicList items={report.proposal_outline} empty="No proposal outline." />
          </div>
          <div className="insight-card">
            <h3 className="section-title"><CheckCircle size={20} /> Quality Controls</h3>
            <KeyValueGrid data={(report.quality_checks?.checks || {}) as Record<string, unknown>} />
          </div>
        </div>
      )}

      {activeTab === 'Raw Extraction' && (
        <div className="content-stack">
          <div className="prep-two-column">
            <InsightSection title="Legacy Functional Requirements" icon={<ListChecks size={18} />} items={analysis.functional_requirements} empty="No functional requirements." />
            <InsightSection title="Excluded Noise" icon={<AlertTriangle size={18} />} items={(report.excluded_noise || []).map((item) => `${asText(item.category)}: ${asText(item.text)}`)} empty="No excluded noise captured." />
          </div>
          <div className="prep-two-column">
            <InsightSection title="Integration/Data Signals" icon={<Database size={18} />} items={[...(analysis.integration_needs || []), ...(analysis.data_needs || [])]} empty="No integration or data signals." />
            <InsightSection title="Missing Information" icon={<HelpCircle size={18} />} items={analysis.missing_information} empty="No missing information." />
          </div>
        </div>
      )}
    </div>
  )
}

function ExtractionQuality({ analysis }: { analysis: RFPAnalysisType }) {
  const meta = analysis.raw_llm_output?.extraction_meta
  const mode = meta?.mode === 'llm_structured' ? 'LLM structured extraction' : 'Source-grounded fallback'
  const confidence = typeof meta?.confidence === 'number' ? `${Math.round(meta.confidence * 100)}%` : 'Reviewed'

  return (
    <div className="insight-card" style={{ padding: '0.9rem' }}>
      <span style={{ color: 'var(--color-text-muted)', fontSize: '0.78rem', textTransform: 'uppercase' }}>
        Extraction quality
      </span>
      <p style={{ color: 'var(--color-success)', fontWeight: 700, marginTop: '0.35rem' }}>
        {mode}
      </p>
      <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.86rem', marginTop: '0.35rem' }}>
        Confidence: {confidence}. Outputs are constrained to RFP text and marked gaps.
      </p>
      <p style={{ color: 'var(--color-text-muted)', fontSize: '0.78rem', marginTop: '0.5rem' }}>
        Sensitive RFP data is not stored in browser state beyond this session view.
      </p>
    </div>
  )
}

export function RFPAnalysis() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const [loadingStep, setLoadingStep] = useState(0)
  const analysisTriggeredRef = useRef<string | null>(null)

  const {
    data: session,
    isLoading: isSessionLoading,
    error: sessionError,
    refetch: refetchSession,
  } = useQuery({
    queryKey: ['rfpSession', sessionId],
    queryFn: () => rfpApi.getById(sessionId!),
    enabled: !!sessionId,
    refetchInterval: (query) => {
      const currentStatus = query.state.data?.status
      return currentStatus === 'uploaded' || currentStatus === 'analyzing' ? 2000 : false
    },
  })

  const { mutate: startAnalysis, isPending: isStartingAnalysis } = useMutation({
    mutationFn: () => rfpApi.triggerAnalysis(sessionId!),
    onSuccess: () => {
      toast.success('RFP analysis started.')
      refetchSession()
    },
    onError: (err) => toast.error('Failed to start analysis: ' + getErrorMessage(err)),
  })

  useEffect(() => {
    if (
      session &&
      session.status === 'uploaded' &&
      !isStartingAnalysis &&
      analysisTriggeredRef.current !== session.id
    ) {
      analysisTriggeredRef.current = session.id
      startAnalysis()
    }
  }, [session, isStartingAnalysis, startAnalysis])

  useEffect(() => {
    let interval: NodeJS.Timeout
    if (session?.status === 'uploaded' || session?.status === 'analyzing') {
      interval = setInterval(() => setLoadingStep((prev) => (prev + 1) % 4), 3000)
    }
    return () => clearInterval(interval)
  }, [session?.status])

  const isAnalyzed =
    session &&
    session.status !== 'uploaded' &&
    session.status !== 'analyzing' &&
    session.status !== 'analysis_failed'

  const { data: analysisResponse, isLoading: isAnalysisLoading } = useQuery({
    queryKey: ['rfpAnalysis', sessionId],
    queryFn: () => rfpApi.getAnalysis(sessionId!),
    enabled: !!sessionId && !!isAnalyzed,
  })

  const analysis = analysisResponse?.analysis

  if (isSessionLoading) {
    return (
      <div className="flex flex-col items-center justify-center" style={{ minHeight: '50vh' }}>
        <div className="spinner" style={{ width: 40, height: 40, borderWidth: 3, marginBottom: '1rem' }} />
        <p>Loading session details...</p>
      </div>
    )
  }

  if (sessionError || !session) {
    return (
      <div className="card-elevated text-center" style={{ maxWidth: 500, margin: '4rem auto' }}>
        <AlertTriangle size={48} color="var(--color-error)" style={{ marginBottom: '1rem' }} />
        <h2 style={{ marginBottom: '0.5rem' }}>Failed to Load Session</h2>
        <p style={{ marginBottom: '1.5rem' }}>
          {sessionError ? getErrorMessage(sessionError) : 'The requested RFP session was not found.'}
        </p>
        <button className="btn btn-primary" onClick={() => navigate('/dashboard')}>
          Back to Dashboard
        </button>
      </div>
    )
  }

  if (session.status === 'uploaded' || session.status === 'analyzing') {
    const steps = [
      'Parsing document text and removing table-of-contents noise...',
      'Extracting delivery requirements and tender constraints...',
      'Separating technical scope from commercial/compliance obligations...',
      'Preparing grounded analysis for the prep pack...',
    ]

    return (
      <div className="flex flex-col items-center justify-center text-center fade-in" style={{ minHeight: '60vh', maxWidth: 620, margin: '0 auto' }}>
        <div className="spinner" style={{ width: 56, height: 56, borderWidth: 4, marginBottom: '1.5rem' }} />
        <h2 style={{ marginBottom: '0.75rem' }}>Analyzing RFP Document</h2>
        <p style={{ color: 'var(--color-primary-light)', fontWeight: 600, marginBottom: '1.5rem', minHeight: 24 }}>
          {steps[loadingStep]}
        </p>
        <p className="readable-text">
          ProposalPilot extracts only source-grounded requirements, risks, compliance obligations, integrations, and missing information. Sensitive RFP content stays within your configured local backend and services.
        </p>
      </div>
    )
  }

  if (session.status === 'analysis_failed') {
    return (
      <div className="card-elevated text-center fade-in" style={{ maxWidth: 560, margin: '4rem auto' }}>
        <AlertTriangle size={56} color="var(--color-error)" style={{ marginBottom: '1.5rem' }} />
        <h2 style={{ marginBottom: '0.75rem' }}>Analysis Failed</h2>
        <p style={{ marginBottom: '2rem', lineHeight: 1.6 }}>
          The system could not parse or analyze this RFP. Retry after confirming the file is readable text, not a scanned image-only PDF.
        </p>
        <div className="flex justify-center gap-4">
          <button className="btn btn-secondary" onClick={() => navigate('/dashboard')}>Back</button>
          <button className="btn btn-primary" onClick={() => startAnalysis()}>
            <RotateCw size={16} />
            Retry Analysis
          </button>
        </div>
      </div>
    )
  }

  const complexityColors: Record<string, string> = {
    low: 'var(--color-success)',
    medium: 'var(--color-info)',
    high: 'var(--color-warning)',
    very_high: 'var(--color-error)',
  }

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <div className="page-title">
            <FileText size={28} color="var(--color-primary-light)" />
            <h1>{session.title}</h1>
            {getStatusBadge(session.status)}
          </div>
          <p className="page-subtitle">
            Client: <strong style={{ color: 'var(--color-text-primary)' }}>{session.client_name || 'N/A'}</strong>
            <span style={{ margin: '0 0.75rem' }}>·</span>
            File: <strong style={{ color: 'var(--color-text-primary)' }}>{session.original_filename}</strong>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button className="btn btn-secondary" onClick={() => navigate('/dashboard')}>Back</button>
          <button
            className="btn btn-secondary"
            onClick={() => startAnalysis()}
            disabled={isStartingAnalysis}
          >
            <RotateCw size={16} />
            Re-analyze
          </button>
          <button
            className="btn btn-primary"
            onClick={() => navigate(`/rfp/${sessionId}/prep-pack`)}
            disabled={isAnalysisLoading || !analysis}
          >
            Generate Prep Pack
            <ArrowRight size={16} />
          </button>
        </div>
      </div>

      {isAnalysisLoading || !analysis ? (
        <div className="flex flex-col items-center justify-center" style={{ minHeight: '30vh' }}>
          <div className="spinner" style={{ width: 32, height: 32, borderWidth: 2, marginBottom: '1rem' }} />
          <p>Retrieving extracted insights...</p>
        </div>
      ) : (
        <div className="content-stack">
          {(() => {
            const report = analysis.raw_llm_output?.executive_report as ExecutiveReport | undefined
            if (report?.ceo_brief) {
              return <ExecutiveReportView report={report} analysis={analysis as RFPAnalysisType} />
            }

            const intelligence = analysis.raw_llm_output?.executive_intelligence as ExecutiveIntelligence | undefined
            const hasIntelligence = !!intelligence?.executive_summary

            if (!hasIntelligence) {
              return null
            }

            return (
              <>
                <div className="card-elevated">
                  <div className="prep-summary">
                    <div>
                      <h3 className="section-title">
                        <Info size={20} color="var(--color-primary-light)" />
                        Executive Intelligence Brief
                      </h3>
                      <p className="readable-text" style={{ color: 'var(--color-text-primary)' }}>
                        {intelligence.executive_summary}
                      </p>
                    </div>
                    <div className="side-stack">
                      <div className="insight-card" style={{ padding: '0.9rem' }}>
                        <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>
                          Complexity
                        </span>
                        <div className="flex items-center gap-2" style={{ marginTop: '0.35rem' }}>
                          <Activity size={18} color={complexityColors[(analysis.estimated_complexity || 'medium').toLowerCase()]} />
                          <strong style={{ textTransform: 'capitalize' }}>{(analysis.estimated_complexity || 'Medium').replace('_', ' ')}</strong>
                        </div>
                      </div>
                      <ExtractionQuality analysis={analysis as RFPAnalysisType} />
                    </div>
                  </div>
                </div>

                <div className="prep-two-column">
                  <div className="insight-card">
                    <h3 className="section-title">
                      <Target size={20} color="var(--color-primary-light)" />
                      Key Insights
                    </h3>
                    <div className="flex flex-col gap-3">
                      {(intelligence.key_insights || []).map((item, index) => (
                        <ExecutiveInsightCard key={`${item.title}-${index}`} item={item} />
                      ))}
                    </div>
                  </div>
                  <div className="insight-card">
                    <h3 className="section-title">
                      <Building size={20} color="var(--color-info)" />
                      Opportunity Assessment
                    </h3>
                    <div className="flex flex-col gap-3">
                      {(intelligence.opportunity_assessment || []).map((item, index) => (
                        <ExecutiveInsightCard key={`${item.title}-${index}`} item={item} />
                      ))}
                    </div>
                  </div>
                </div>

                <div className="prep-two-column">
                  <InsightSection
                    title="Business Drivers"
                    icon={<CheckCircle size={20} color="var(--color-success)" />}
                    items={intelligence.business_drivers}
                    empty="No business drivers identified."
                  />
                  <InsightSection
                    title="Risks & Dependencies"
                    icon={<ShieldAlert size={20} color="var(--color-error)" />}
                    items={intelligence.risks_and_dependencies}
                    empty="No material risks identified."
                    accent="var(--color-error)"
                  />
                </div>

                <div className="insight-card">
                  <h3 className="section-title">
                    <HelpCircle size={20} color="var(--color-warning)" />
                    Recommendations
                  </h3>
                  <StrategicList items={intelligence.recommendations} empty="No recommendations generated." />
                </div>

                <div className="insight-card">
                  <h3 className="section-title">
                    <FileText size={20} color="var(--color-text-muted)" />
                    Supporting Extracts
                  </h3>
                  <div className="prep-two-column">
                    <InsightSection title="Delivery Signals" icon={<ListChecks size={18} />} items={analysis.functional_requirements} empty="No delivery signals." />
                    <InsightSection title="Integration/Data Signals" icon={<Database size={18} />} items={[...(analysis.integration_needs || []), ...(analysis.data_needs || [])]} empty="No integration or data signals." />
                  </div>
                </div>
              </>
            )
          })()}

          {!analysis.raw_llm_output?.executive_intelligence && (
          <>
          <div className="card-elevated">
            <div className="prep-summary">
              <div>
                <h3 className="section-title">
                  <Info size={20} color="var(--color-primary-light)" />
                  Executive Summary
                </h3>
                <p className="readable-text" style={{ color: 'var(--color-text-primary)' }}>
                  {cleanDisplayText(analysis.business_problem || 'No explicit business problem stated.')}
                </p>
              </div>
              <div className="side-stack">
                <div className="insight-card" style={{ padding: '0.9rem' }}>
                  <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>
                    Complexity
                  </span>
                  <div className="flex items-center gap-2" style={{ marginTop: '0.35rem' }}>
                    <Activity size={18} color={complexityColors[(analysis.estimated_complexity || 'medium').toLowerCase()]} />
                    <strong style={{ textTransform: 'capitalize' }}>{(analysis.estimated_complexity || 'Medium').replace('_', ' ')}</strong>
                  </div>
                </div>
                <ExtractionQuality analysis={analysis as RFPAnalysisType} />
              </div>
            </div>
          </div>

          <div className="prep-two-column">
            <InsightSection
              title="Delivery Requirements"
              icon={<ListChecks size={20} color="var(--color-primary-light)" />}
              items={analysis.functional_requirements}
              empty="No delivery requirements were confidently extracted."
            />
            <InsightSection
              title="Non-Functional Requirements"
              icon={<Activity size={20} color="var(--color-accent)" />}
              items={analysis.non_functional_requirements}
              empty="No non-functional requirements were confidently extracted."
            />
          </div>

          <div className="prep-two-column">
            <InsightSection
              title="Integration Needs"
              icon={<Building size={20} color="var(--color-info)" />}
              items={analysis.integration_needs}
              empty="No explicit integrations were identified."
            />
            <InsightSection
              title="Data & Reporting Needs"
              icon={<Database size={20} color="var(--color-success)" />}
              items={analysis.data_needs}
              empty="No explicit data or reporting requirements were identified."
            />
          </div>

          <div className="prep-two-column">
            <InsightSection
              title="Compliance & Tender Obligations"
              icon={<ShieldAlert size={20} color="var(--color-warning)" />}
              items={analysis.compliance_needs}
              empty="No explicit compliance obligations were identified."
              accent="var(--color-warning)"
            />
            <InsightSection
              title="Timeline & Commercial Risks"
              icon={<Clock size={20} color="var(--color-error)" />}
              items={analysis.timeline_risks}
              empty="No timeline or commercial risks were identified."
              accent="var(--color-error)"
            />
          </div>

          <div className="prep-two-column">
            <InsightSection
              title="Scope Boundaries"
              icon={<CheckCircle size={20} color="var(--color-success)" />}
              items={analysis.scope_boundaries}
              empty="No explicit scope boundaries were identified."
            />
            <InsightSection
              title="Missing Information"
              icon={<HelpCircle size={20} color="var(--color-warning)" />}
              items={analysis.missing_information}
              empty="No major gaps were flagged."
              accent="var(--color-warning)"
            />
          </div>
          </>
          )}
        </div>
      )}
    </div>
  )
}
