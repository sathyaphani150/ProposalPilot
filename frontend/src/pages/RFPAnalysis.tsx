import { useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  Activity,
  AlertTriangle,
  BookOpen,
  CircuitBoard,
  Database,
  FileText,
  HelpCircle,
  MessageSquare,
  RefreshCw,
  ShieldAlert,
  Swords,
  Target,
} from 'lucide-react'
import { rfpApi } from '@/api/endpoints'
import { getErrorMessage } from '@/api/client'
import type {
  EvidenceItem,
  MustAskQuestion,
  RFPAnalysis as RFPAnalysisType,
  RFPIntelligence,
  RFPStatus,
  TalkingPoint,
} from '@/types'

const tabs = [
  'Must-Ask Questions',
  'Top Risks',
  'Talking Points',
  'Narrative',
  'Relevant Knowledge Evidence',
  'Architecture',
] as const

type TabName = (typeof tabs)[number]

function getStatusBadge(status: RFPStatus) {
  const labels: Record<RFPStatus, string> = {
    uploaded: 'Uploaded',
    analyzing: 'Analyzing',
    analyzed: 'Analyzed',
    analysis_failed: 'Failed',
    prep_generating: 'Generating',
    prep_ready: 'Ready',
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

function asText(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (Array.isArray(value)) return value.map(asText).filter(Boolean).join(', ')
  if (typeof value === 'object') return ''
  return cleanDisplayText(String(value))
}

function fallbackIntelligence(analysis: RFPAnalysisType): RFPIntelligence {
  return {
    sentiment_analysis: {
      overall_sentiment: 'Qualification needed',
      summary:
        analysis.business_problem ||
        'The RFP needs source-grounded clarification before leadership commits scope, timeline, or commercial assumptions.',
      confidence: 'medium',
      points: [
        {
          title: 'Opportunity intent',
          insight: analysis.business_problem || 'The RFP needs source-grounded clarification.',
          evidence: analysis.functional_requirements?.[0] || analysis.business_problem || '',
          implication: 'Validate the business outcome and success metric before discussing delivery commitment.',
        },
        {
          title: 'Assumption load',
          insight: 'Several assumptions need client confirmation before scope, price, timeline, and architecture are committed.',
          evidence: analysis.missing_information?.slice(0, 2).join('; ') || '',
          implication: 'Use the call to convert unknowns into assumptions, exclusions, dependencies, or discovery actions.',
        },
      ],
      recommended_posture:
        'Use the first client call to validate business outcomes, dependencies, acceptance criteria, and risk ownership.',
    },
    must_ask_questions:
      analysis.missing_information.map((question) => ({
        question,
        why_it_matters: 'This affects delivery confidence, pricing, timeline, architecture, or acceptance risk.',
        assumption_to_validate: 'The client can clarify this before proposal commitment.',
      })),
    top_risks: analysis.timeline_risks.map((risk) => ({ risk_title: risk })),
    talking_points: [
      { point: 'Confirm the business outcome and measurable success criteria.' },
      { point: 'Validate client-owned data, integration, security, and approval dependencies.' },
      { point: 'Separate mandatory first-release scope from optional or future-phase work.' },
    ],
    narrative: {
      title: 'Evidence-led client narrative',
      story:
        'No relevant internal project evidence was attached to this analysis yet. Keep the client narrative grounded in RFP facts until a verified project match is available.',
      confidence: 'low',
    },
    relevant_knowledge_evidence: [],
    architecture: {
      summary: 'Use a modular architecture based on confirmed RFP scope, integrations, data, security, and operating requirements.',
      components: ['Client channels / user interface', 'Application workflow services', 'Data layer', 'Integration/API adapter layer', 'Security and audit logging', 'Monitoring and operations'],
      assumptions: ['Final design depends on confirmed source systems, hosting model, security controls, and acceptance criteria.'],
      business_view: ['Confirm the operating outcome, owner, success metric, and acceptance authority before finalizing the design.'],
      technical_view: ['Separate user experience, workflow services, integration adapters, data responsibilities, controls, and observability.'],
      decision_points: ['Validate integration readiness, data ownership, control evidence, release scope, and support responsibilities before pricing.'],
      call_prep_questions: ['Which owner can confirm the success metric, source systems, security gates, and acceptance evidence?'],
    },
  }
}

function hasUsableIntelligence(value?: RFPIntelligence) {
  return !!(
    value?.sentiment_analysis?.summary ||
    value?.sentiment_analysis?.points?.length ||
    value?.must_ask_questions?.length ||
    value?.top_risks?.length ||
    value?.talking_points?.length ||
    value?.architecture?.components?.length
  )
}

function SectionCard({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <div className="panel">
      <h3 className="section-title">
        {icon}
        {title}
      </h3>
      {children}
    </div>
  )
}

function TextList({ items, empty }: { items?: string[]; empty: string }) {
  const displayItems = (items || []).map(cleanDisplayText).filter(Boolean)
  if (!displayItems.length) {
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

function QuestionCards({ questions }: { questions?: MustAskQuestion[] }) {
  if (!questions?.length) return <p className="readable-text">No clarification questions were generated.</p>
  return (
    <div className="content-stack">
      {questions.map((item, index) => (
        <div className="match-card" key={`${item.question}-${index}`}>
          <div className="flex justify-between items-center gap-3" style={{ marginBottom: '0.5rem' }}>
            <h4 style={{ margin: 0 }}>{item.question}</h4>
            {item.category ? <span className="badge badge-analyzed">{item.category}</span> : null}
          </div>
          {item.why_it_matters ? <p className="readable-text"><strong>Why it matters:</strong> {item.why_it_matters}</p> : null}
          {item.assumption_to_validate ? (
            <p className="readable-text"><strong>Assumption:</strong> {item.assumption_to_validate}</p>
          ) : null}
        </div>
      ))}
    </div>
  )
}

function RiskCards({ risks }: { risks?: Array<Record<string, unknown>> }) {
  if (!risks?.length) return <p className="readable-text">No risk assessment was generated.</p>
  return (
    <div className="content-stack">
      {risks.map((item, index) => (
        <div className="match-card" key={`${asText(item.risk_title) || asText(item.risk_name)}-${index}`}>
          <div className="flex justify-between items-center gap-3" style={{ marginBottom: '0.5rem' }}>
            <h4 style={{ margin: 0 }}>{asText(item.risk_title) || asText(item.risk_name) || asText(item.risk) || 'Risk'}</h4>
            <span className="badge badge-danger">{asText(item.severity) || 'Medium'}</span>
          </div>
          {asText(item.impact) ? <p className="readable-text"><strong>Impact:</strong> {asText(item.impact)}</p> : null}
          {asText(item.mitigation) ? <p className="readable-text"><strong>Mitigation:</strong> {asText(item.mitigation)}</p> : null}
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.86rem', marginTop: '0.5rem' }}>
            Probability: {asText(item.probability) || 'Medium'} | Owner: {asText(item.owner) || 'Joint'}
          </p>
        </div>
      ))}
    </div>
  )
}

function TalkingPointCards({ points }: { points?: TalkingPoint[] }) {
  if (!points?.length) return <p className="readable-text">No talking points were generated.</p>
  return (
    <div className="content-stack">
      {points.map((item, index) => (
        <div className="match-card" key={`${item.point}-${index}`}>
          <h4>{item.point}</h4>
          {item.client_angle ? <p className="readable-text"><strong>Client angle:</strong> {item.client_angle}</p> : null}
          {item.proof_needed ? <p className="readable-text"><strong>Proof needed:</strong> {item.proof_needed}</p> : null}
        </div>
      ))}
    </div>
  )
}

function EvidenceCards({ evidence }: { evidence?: EvidenceItem[] }) {
  if (!evidence?.length) {
    return (
      <p className="readable-text">
        No relevant knowledge-base evidence was retrieved. Seed or ingest internal case studies, architecture docs, and project writeups to improve this section.
      </p>
    )
  }
  return (
    <div className="content-stack">
      {evidence.map((item, index) => (
        <div className="match-card" key={`${item.title}-${index}`}>
          <div className="flex justify-between items-center gap-3" style={{ marginBottom: '0.5rem' }}>
            <h4 style={{ margin: 0 }}>{item.title}</h4>
            <span className="badge badge-analyzed mono-data">{Math.round((item.score || 0) * 100)}%</span>
          </div>
          <div className="relevance-track mb-3">
            <div className="relevance-fill" style={{ width: `${Math.round((item.score || 0) * 100)}%` }} />
          </div>
          <p className="readable-text">{item.why_relevant}</p>
          <div className="flex gap-2" style={{ marginTop: '0.75rem', flexWrap: 'wrap' }}>
            {[...(item.tech_stack || []), ...(item.tags || [])].slice(0, 10).map((tag) => (
              <span className="badge badge-uploaded" key={tag}>{tag}</span>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function ArchitectureFlow({ architecture }: { architecture?: RFPIntelligence['architecture'] }) {
  const nodes = (architecture?.components || []).filter(Boolean).slice(0, 10)
  if (!nodes.length) return null
  return (
    <div>
      <h4 className="section-title" style={{ marginTop: 0 }}>
        <CircuitBoard size={18} />
        Architecture Flow
      </h4>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.55rem' }}>
        {nodes.map((node, index) => (
          <div key={`${node}-${index}`} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%' }}>
            <div
              style={{
                width: 'min(100%, 760px)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-md)',
                background: 'rgba(96, 165, 250, 0.08)',
                padding: '0.85rem 1rem',
                textAlign: 'center',
                fontWeight: 700,
                color: 'var(--color-text-primary)',
              }}
            >
              {node}
            </div>
            {index < nodes.length - 1 ? (
              <div style={{ color: 'var(--color-primary-light)', fontSize: '1.4rem', lineHeight: 1.15, padding: '0.15rem 0' }}>&darr;</div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  )
}

function SentimentPointCards({ points }: { points?: NonNullable<RFPIntelligence['sentiment_analysis']>['points'] }) {
  if (!points?.length) return <p className="readable-text">No point-wise sentiment analysis was generated.</p>
  return (
    <div className="content-stack" style={{ marginTop: '1rem' }}>
      {points.map((item, index) => (
        <div className="match-card" key={`${item.title || 'point'}-${index}`}>
          <h4>{item.title || 'RFP insight'}</h4>
          {item.insight ? <p className="readable-text">{item.insight}</p> : null}
          {item.evidence ? (
            <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem', marginTop: '0.65rem' }}>
              <strong>Evidence:</strong> {item.evidence}
            </p>
          ) : null}
          {item.implication ? (
            <p style={{ color: 'var(--color-primary-light)', fontSize: '0.92rem', marginTop: '0.65rem', lineHeight: 1.55 }}>
              <strong>Implication:</strong> {item.implication}
            </p>
          ) : null}
        </div>
      ))}
    </div>
  )
}

function ArchitectureView({ architecture }: { architecture?: RFPIntelligence['architecture'] }) {
  if (!architecture) return <p className="readable-text">No architecture recommendation was generated.</p>
  const hasDetails = Boolean(
    architecture.business_view?.length ||
    architecture.technical_view?.length ||
    architecture.data_flow?.length ||
    architecture.integration_flow?.length ||
    architecture.security_operations?.length ||
    architecture.decision_points?.length ||
    architecture.call_prep_questions?.length
  )
  return (
    <div className="content-stack">
      {architecture.summary ? <p className="readable-text">{architecture.summary}</p> : null}
      <ArchitectureFlow architecture={architecture} />
      {hasDetails ? (
        <>
          <ArchitectureSubsection title="Business View" items={architecture.business_view} empty="No business architecture view generated." />
          <ArchitectureSubsection title="Technical Blueprint" items={architecture.technical_view} empty="No technical blueprint generated." />
          <div className="prep-two-column">
            <ArchitectureSubsection title="Data Flow" items={architecture.data_flow} empty="No data flow generated." />
            <ArchitectureSubsection title="Integration Flow" items={architecture.integration_flow} empty="No integration flow generated." />
          </div>
          <ArchitectureSubsection title="Security and Operations" items={architecture.security_operations} empty="No security or operations detail generated." />
          <div className="prep-two-column">
            <ArchitectureSubsection title="Decision Points" items={architecture.decision_points} empty="No design decisions generated." />
            <ArchitectureSubsection title="Call Prep Questions" items={architecture.call_prep_questions} empty="No architecture call questions generated." />
          </div>
        </>
      ) : null}
      <div className="prep-two-column">
        <div>
          <h4 className="section-title">
            <Database size={18} />
            Components
          </h4>
          <TextList items={architecture.components} empty="No components generated." />
        </div>
        <div>
          <h4 className="section-title">
            <HelpCircle size={18} />
            Assumptions
          </h4>
          <TextList items={architecture.assumptions} empty="No assumptions generated." />
        </div>
      </div>
    </div>
  )
}

function ArchitectureSubsection({ title, items, empty }: { title: string; items?: string[]; empty: string }) {
  return (
    <div>
      <h4 style={{ marginBottom: '0.65rem' }}>{title}</h4>
      <TextList items={items} empty={empty} />
    </div>
  )
}

export function RFPAnalysis() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [loadingStep, setLoadingStep] = useState(0)
  const [activeTab, setActiveTab] = useState<TabName>('Must-Ask Questions')
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
    onSuccess: async () => {
      toast.success('RFP analysis started.')
      await queryClient.invalidateQueries({ queryKey: ['rfpAnalysis', sessionId] })
      await Promise.all([
        refetchSession(),
        queryClient.refetchQueries({ queryKey: ['rfpAnalysis', sessionId] }),
      ])
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

  const shouldFetchAnalysis =
    !!session &&
    session.status !== 'analysis_failed'

  const { data: analysisResponse, isLoading: isAnalysisLoading } = useQuery({
    queryKey: ['rfpAnalysis', sessionId, session?.updated_at],
    queryFn: () => rfpApi.getAnalysis(sessionId!),
    enabled: !!sessionId && shouldFetchAnalysis,
    refetchInterval: (query) => {
      const hasAnalysis = !!query.state.data?.analysis
      return (session?.status === 'uploaded' || session?.status === 'analyzing') && !hasAnalysis ? 3000 : false
    },
  })

  const analysis = analysisResponse?.analysis
  const intelligence = useMemo(() => {
    if (!analysis) return undefined
    const generated = analysis.raw_llm_output?.rfp_intelligence
    return hasUsableIntelligence(generated) ? generated : fallbackIntelligence(analysis)
  }, [analysis])
  const extractionMeta = analysis?.raw_llm_output?.extraction_meta
  const isFallbackAnalysis =
    extractionMeta?.mode === 'deterministic_source_text' ||
    extractionMeta?.warnings?.some((warning) => warning.toLowerCase().includes('llm'))

  useEffect(() => {
    if (analysis && session?.status === 'analyzing') {
      refetchSession()
    }
  }, [analysis, session?.status, refetchSession])

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
        <button className="btn btn-primary" onClick={() => navigate('/dashboard')}>Back to Dashboard</button>
      </div>
    )
  }

  if ((session.status === 'uploaded' || session.status === 'analyzing') && !analysis) {
    const steps = [
      'Parsing document text and removing tender boilerplate...',
      'Extracting source-grounded requirements, gaps, and risks...',
      'Retrieving relevant internal knowledge evidence...',
      'Building executive call strategy and architecture...',
    ]

    return (
      <div className="flex flex-col items-center justify-center text-center fade-in" style={{ minHeight: '60vh', maxWidth: 660, margin: '0 auto' }}>
        <div className="spinner" style={{ width: 56, height: 56, borderWidth: 4, marginBottom: '1.5rem' }} />
        <h2 style={{ marginBottom: '0.75rem' }}>Analyzing RFP Document</h2>
        <p style={{ color: 'var(--color-primary-light)', fontWeight: 600, marginBottom: '1.5rem', minHeight: 24 }}>
          {steps[loadingStep]}
        </p>
        <p className="readable-text">
          ProposalPilot is preparing one leadership-ready analysis page with sentiment, assumptions, risks, talking points, evidence, and architecture.
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
          <button className="btn btn-primary" onClick={() => startAnalysis()} disabled={isStartingAnalysis}>
            <RefreshCw size={16} />
            Retry Analysis
          </button>
        </div>
      </div>
    )
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
            <span style={{ margin: '0 0.75rem' }}>|</span>
            File: <strong style={{ color: 'var(--color-text-primary)' }}>{session.original_filename}</strong>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button className="btn btn-secondary" onClick={() => navigate('/dashboard')}>Back</button>
          <button className="btn btn-secondary" onClick={() => startAnalysis()} disabled={isStartingAnalysis}>
            {isStartingAnalysis ? <div className="spinner" style={{ width: 14, height: 14 }} /> : <RefreshCw size={16} />}
            Regenerate
          </button>
          <button className="btn btn-primary" onClick={() => navigate(`/rfp/${sessionId}/war-room`)} disabled={isAnalysisLoading || !analysis}>
            <Swords size={16} />
            Open War Room
          </button>
        </div>
      </div>

      {isAnalysisLoading || !analysis || !intelligence ? (
        <div className="flex flex-col items-center justify-center" style={{ minHeight: '30vh' }}>
          <div className="spinner" style={{ width: 32, height: 32, borderWidth: 2, marginBottom: '1rem' }} />
          <p>Retrieving extracted insights...</p>
        </div>
      ) : (
        <div className="content-stack">
          {isFallbackAnalysis ? (
            <div className="panel" style={{ borderColor: 'rgba(255, 180, 84, 0.55)', background: 'rgba(255, 180, 84, 0.08)' }}>
              <h3 className="section-title">
                <AlertTriangle size={20} color="var(--color-warning)" />
                Model Analysis Unavailable
              </h3>
              <p className="readable-text" style={{ marginBottom: 0 }}>
                Showing source-extracted fallback content because the configured LLM call did not complete. Update the LLM API key, restart the backend worker, and regenerate this RFP for model-authored executive insights.
              </p>
            </div>
          ) : null}

          <div className="panel panel--raised">
            <h3 className="section-title">
              <Activity size={20} color="var(--color-primary-light)" />
              Sentiment Analysis
              {intelligence.sentiment_analysis?.confidence ? (
                <span className="badge badge-analyzed mono-data">{intelligence.sentiment_analysis.confidence}</span>
              ) : null}
            </h3>
            <p className="readable-text" style={{ color: 'var(--color-text-primary)' }}>
              {intelligence.sentiment_analysis?.summary || 'No sentiment summary was generated.'}
            </p>
            <SentimentPointCards points={intelligence.sentiment_analysis?.points} />
          </div>

          <div className="panel" style={{ display: 'flex', gap: '0.5rem', overflowX: 'auto', padding: '0.65rem' }}>
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

          {activeTab === 'Must-Ask Questions' ? (
            <SectionCard title="Must-Ask Questions" icon={<HelpCircle size={20} />}>
              <QuestionCards questions={intelligence.must_ask_questions} />
            </SectionCard>
          ) : null}

          {activeTab === 'Top Risks' ? (
            <SectionCard title="Top Risks" icon={<ShieldAlert size={20} />}>
              <RiskCards risks={intelligence.top_risks} />
            </SectionCard>
          ) : null}

          {activeTab === 'Talking Points' ? (
            <SectionCard title="Talking Points" icon={<MessageSquare size={20} />}>
              <TalkingPointCards points={intelligence.talking_points} />
            </SectionCard>
          ) : null}

          {activeTab === 'Narrative' ? (
            <SectionCard title={intelligence.narrative?.title || 'Narrative'} icon={<BookOpen size={20} />}>
              <p className="readable-text">{intelligence.narrative?.story || 'No narrative was generated.'}</p>
              <TextList items={intelligence.narrative?.how_it_helps} empty="No supporting narrative points were generated." />
            </SectionCard>
          ) : null}

          {activeTab === 'Relevant Knowledge Evidence' ? (
            <SectionCard title="Relevant Knowledge Evidence" icon={<Target size={20} />}>
              <EvidenceCards evidence={intelligence.relevant_knowledge_evidence} />
            </SectionCard>
          ) : null}

          {activeTab === 'Architecture' ? (
            <SectionCard title="Architecture" icon={<CircuitBoard size={20} />}>
              <ArchitectureView architecture={intelligence.architecture} />
            </SectionCard>
          ) : null}
        </div>
      )}
    </div>
  )
}
