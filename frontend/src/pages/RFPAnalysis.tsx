import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  AlertTriangle,
  ArrowRight,
  Clock,
  Database,
  ShieldAlert,
  ListChecks,
  Building,
  HelpCircle,
  Activity,
  RotateCw,
  Info,
  CheckCircle,
} from 'lucide-react'
import { rfpApi } from '@/api/endpoints'
import { getErrorMessage } from '@/api/client'
import type { RFPStatus } from '@/types'

export function RFPAnalysis() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const [loadingStep, setLoadingStep] = useState(0)

  // 1. Fetch Session Info & Poll while analyzing
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
      if (currentStatus === 'uploaded' || currentStatus === 'analyzing') {
        return 2000 // Poll every 2 seconds
      }
      return false
    },
  })

  // 2. Trigger Analysis Mutation
  const { mutate: startAnalysis, isPending: isStartingAnalysis } = useMutation({
    mutationFn: () => rfpApi.triggerAnalysis(sessionId!),
    onSuccess: () => {
      toast.success('RFP analysis started.')
      refetchSession()
    },
    onError: (err) => {
      toast.error('Failed to start analysis: ' + getErrorMessage(err))
    },
  })

  // Auto-trigger analysis if status is 'uploaded'
  useEffect(() => {
    if (session && session.status === 'uploaded' && !isStartingAnalysis) {
      startAnalysis()
    }
  }, [session, isStartingAnalysis, startAnalysis])

  // Simple loading steps animation
  useEffect(() => {
    let interval: NodeJS.Timeout
    if (session?.status === 'uploaded' || session?.status === 'analyzing') {
      interval = setInterval(() => {
        setLoadingStep((prev) => (prev + 1) % 4)
      }, 3000)
    }
    return () => clearInterval(interval)
  }, [session?.status])

  // 3. Fetch Analysis Data when analyzed
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
        <p style={{ color: 'var(--color-text-secondary)' }}>Loading session details...</p>
      </div>
    )
  }

  if (sessionError || !session) {
    return (
      <div className="card-elevated text-center" style={{ maxWidth: 500, margin: '4rem auto' }}>
        <AlertTriangle size={48} color="var(--color-error)" style={{ marginBottom: '1rem' }} />
        <h2 style={{ marginBottom: '0.5rem' }}>Failed to Load Session</h2>
        <p style={{ color: 'var(--color-text-secondary)', marginBottom: '1.5rem' }}>
          {sessionError ? getErrorMessage(sessionError) : 'The requested RFP session was not found.'}
        </p>
        <button className="btn btn-primary" onClick={() => navigate('/dashboard')}>
          Back to Dashboard
        </button>
      </div>
    )
  }

  // State: Uploaded or Analyzing
  if (session.status === 'uploaded' || session.status === 'analyzing') {
    const steps = [
      'Reading and parsing document contents...',
      'Running AI Pre-Sales Understanding Engine...',
      'Extracting functional and compliance matrices...',
      'Classifying integration needs and scoping boundaries...',
    ]

    return (
      <div className="flex flex-col items-center justify-center text-center fade-in" style={{ minHeight: '60vh', maxWidth: 600, margin: '0 auto' }}>
        <div
          className="spinner"
          style={{
            width: 60,
            height: 60,
            borderWidth: 4,
            borderColor: 'var(--color-primary-glow)',
            borderTopColor: 'var(--color-primary)',
            marginBottom: '2rem',
          }}
        />
        <h2 style={{ marginBottom: '0.75rem' }}>Analyzing RFP Document</h2>
        <p style={{ color: 'var(--color-primary-light)', fontWeight: 500, marginBottom: '2rem', minHeight: '24px' }}>
          {steps[loadingStep]}
        </p>
        <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem', lineHeight: 1.6 }}>
          We are analyzing the uploaded RFP file. This process extracts functional requirements, compliance regulations, integrations, and potential timeline risks.
        </p>

        {/* Skeleton Preview */}
        <div className="w-full card" style={{ marginTop: '3rem', opacity: 0.3, pointerEvents: 'none' }}>
          <div className="skeleton" style={{ height: 24, width: '40%', marginBottom: '1rem' }} />
          <div className="skeleton" style={{ height: 80, width: '100%', marginBottom: '1.5rem' }} />
          <div className="grid-2">
            <div className="skeleton" style={{ height: 120 }} />
            <div className="skeleton" style={{ height: 120 }} />
          </div>
        </div>
      </div>
    )
  }

  // State: Analysis Failed
  if (session.status === 'analysis_failed') {
    return (
      <div className="card-elevated text-center fade-in" style={{ maxWidth: 550, margin: '4rem auto' }}>
        <AlertTriangle size={56} color="var(--color-error)" style={{ marginBottom: '1.5rem' }} />
        <h2 style={{ marginBottom: '0.75rem' }}>Analysis Failed</h2>
        <p style={{ color: 'var(--color-text-secondary)', marginBottom: '2rem', lineHeight: 1.6 }}>
          The AI engine encountered an unexpected error while reading or analyzing the RFP text. This might be due to a complex document structure or API connection limits.
        </p>
        <div className="flex justify-center gap-4">
          <button className="btn btn-secondary" onClick={() => navigate('/dashboard')}>
            Back to Dashboard
          </button>
          <button className="btn btn-primary" onClick={() => startAnalysis()}>
            <RotateCw size={16} />
            Retry Analysis
          </button>
        </div>
      </div>
    )
  }

  // State: Analyzed (Ready)
  const complexityColors: Record<string, string> = {
    low: 'var(--color-success)',
    medium: 'var(--color-info)',
    high: 'var(--color-warning)',
    very_high: 'var(--color-error)',
  }

  const getStatusBadge = (status: RFPStatus) => {
    const labels: Record<RFPStatus, string> = {
      uploaded: 'Uploaded',
      analyzing: 'Analyzing...',
      analyzed: 'Analyzed',
      analysis_failed: 'Failed',
      prep_generating: 'Generating Prep...',
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

  return (
    <div className="fade-in">
      {/* Header Info */}
      <div className="flex justify-between items-center" style={{ marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div className="flex items-center gap-3" style={{ marginBottom: '0.5rem' }}>
            <h1>{session.title}</h1>
            {getStatusBadge(session.status)}
          </div>
          <p style={{ color: 'var(--color-text-secondary)' }}>
            Client: <span style={{ color: 'var(--color-text-primary)', fontWeight: 500 }}>{session.client_name || 'N/A'}</span>
            <span style={{ margin: '0 0.75rem' }}>•</span>
            Original File: <span style={{ color: 'var(--color-text-primary)' }}>{session.original_filename}</span>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button className="btn btn-secondary" onClick={() => navigate('/dashboard')}>
            Back
          </button>
          <button
            className="btn btn-primary"
            onClick={() => navigate(`/rfp/${sessionId}/prep-pack`)}
            disabled={isAnalysisLoading || !analysis}
          >
            Generate Call Prep Pack
            <ArrowRight size={16} />
          </button>
        </div>
      </div>

      {isAnalysisLoading || !analysis ? (
        <div className="flex flex-col items-center justify-center" style={{ minHeight: '30vh' }}>
          <div className="spinner" style={{ width: 32, height: 32, borderWidth: 2, marginBottom: '1rem' }} />
          <p style={{ color: 'var(--color-text-secondary)' }}>Retrieving extracted insights...</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Top Summary Card */}
          <div className="card-elevated" style={{ padding: '1.75rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '2rem', alignItems: 'center' }}>
              <div>
                <h3 style={{ marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Info size={20} color="var(--color-primary-light)" />
                  Executive Business Problem
                </h3>
                <p style={{ fontSize: '1rem', color: 'var(--color-text-primary)', lineHeight: 1.6 }}>
                  {analysis.business_problem || 'No specific business problem stated.'}
                </p>
              </div>
              <div
                style={{
                  borderLeft: '1px solid var(--color-border)',
                  paddingLeft: '2rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '1rem',
                }}
              >
                <div>
                  <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Estimated Complexity
                  </span>
                  <div className="flex items-center gap-2" style={{ marginTop: '0.25rem' }}>
                    <Activity size={18} color={complexityColors[(analysis.estimated_complexity || 'medium').toLowerCase()]} />
                    <span style={{ fontSize: '1.25rem', fontWeight: 700, textTransform: 'capitalize' }}>
                      {(analysis.estimated_complexity || 'Medium').replace('_', ' ')}
                    </span>
                  </div>
                </div>
                <div>
                  <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Domain Focus
                  </span>
                  <div className="flex gap-2" style={{ flexWrap: 'wrap', marginTop: '0.35rem' }}>
                    {analysis.domain_tags && analysis.domain_tags.length > 0 ? (
                      analysis.domain_tags.map((tag: string) => (
                        <span key={tag} className="badge badge-uploaded" style={{ textTransform: 'uppercase', fontSize: '0.65rem' }}>
                          {tag}
                        </span>
                      ))
                    ) : (
                      <span style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem' }}>N/A</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Grid Layout of Cards */}
          <div className="grid-2">
            {/* Functional Requirements */}
            <div className="card">
              <h3 style={{ marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <ListChecks size={20} color="var(--color-primary-light)" />
                Functional Requirements ({analysis.functional_requirements?.length || 0})
              </h3>
              <ul style={{ paddingLeft: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {analysis.functional_requirements && analysis.functional_requirements.length > 0 ? (
                  analysis.functional_requirements.map((req: string, idx: number) => (
                    <li key={idx} style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem' }}>
                      {req}
                    </li>
                  ))
                ) : (
                  <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>No explicit requirements detected.</p>
                )}
              </ul>
            </div>

            {/* Non-Functional Requirements */}
            <div className="card">
              <h3 style={{ marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Activity size={20} color="var(--color-accent)" />
                Non-Functional Requirements ({analysis.non_functional_requirements?.length || 0})
              </h3>
              <ul style={{ paddingLeft: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {analysis.non_functional_requirements && analysis.non_functional_requirements.length > 0 ? (
                  analysis.non_functional_requirements.map((req: string, idx: number) => (
                    <li key={idx} style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem' }}>
                      {req}
                    </li>
                  ))
                ) : (
                  <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>No non-functional requirements detected.</p>
                )}
              </ul>
            </div>
          </div>

          <div className="grid-2">
            {/* Integration Needs */}
            <div className="card">
              <h3 style={{ marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Building size={20} color="var(--color-info)" />
                System Integration Needs
              </h3>
              <ul style={{ paddingLeft: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {analysis.integration_needs && analysis.integration_needs.length > 0 ? (
                  analysis.integration_needs.map((item: string, idx: number) => (
                    <li key={idx} style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem' }}>
                      {item}
                    </li>
                  ))
                ) : (
                  <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>No explicit integrations mentioned.</p>
                )}
              </ul>
            </div>

            {/* Data Needs */}
            <div className="card">
              <h3 style={{ marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Database size={20} color="var(--color-success)" />
                Data & Storage Needs
              </h3>
              <ul style={{ paddingLeft: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {analysis.data_needs && analysis.data_needs.length > 0 ? (
                  analysis.data_needs.map((item: string, idx: number) => (
                    <li key={idx} style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem' }}>
                      {item}
                    </li>
                  ))
                ) : (
                  <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>No explicit data specifications mentioned.</p>
                )}
              </ul>
            </div>
          </div>

          <div className="grid-2">
            {/* Compliance Needs */}
            <div className="card">
              <h3 style={{ marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <ShieldAlert size={20} color="var(--color-warning)" />
                Compliance & Regulations
              </h3>
              <ul style={{ paddingLeft: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {analysis.compliance_needs && analysis.compliance_needs.length > 0 ? (
                  analysis.compliance_needs.map((item: string, idx: number) => (
                    <li key={idx} style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem' }}>
                      {item}
                    </li>
                  ))
                ) : (
                  <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>No special compliance rules noted.</p>
                )}
              </ul>
            </div>

            {/* Timeline Risks */}
            <div className="card">
              <h3 style={{ marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Clock size={20} color="var(--color-error)" />
                Timeline Constraints & Risks
              </h3>
              <ul style={{ paddingLeft: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {analysis.timeline_risks && analysis.timeline_risks.length > 0 ? (
                  analysis.timeline_risks.map((item: string, idx: number) => (
                    <li key={idx} style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem' }}>
                      {item}
                    </li>
                  ))
                ) : (
                  <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>No major constraints identified.</p>
                )}
              </ul>
            </div>
          </div>

          <div className="grid-2">
            {/* Scope Boundaries */}
            <div className="card">
              <h3 style={{ marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <CheckCircle size={20} color="var(--color-primary-light)" />
                Scope Boundaries (In / Out)
              </h3>
              <ul style={{ paddingLeft: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {analysis.scope_boundaries && analysis.scope_boundaries.length > 0 ? (
                  analysis.scope_boundaries.map((item: string, idx: number) => (
                    <li key={idx} style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem' }}>
                      {item}
                    </li>
                  ))
                ) : (
                  <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>No boundary rules described.</p>
                )}
              </ul>
            </div>

            {/* Missing Information & Gaps */}
            <div
              className="card"
              style={{
                background: 'rgba(245, 158, 11, 0.03)',
                borderColor: 'rgba(245, 158, 11, 0.15)',
              }}
            >
              <h3 style={{ marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--color-warning)' }}>
                <HelpCircle size={20} color="var(--color-warning)" />
                Missing Information & Critical Gaps
              </h3>
              <ul style={{ paddingLeft: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {analysis.missing_information && analysis.missing_information.length > 0 ? (
                  analysis.missing_information.map((item: string, idx: number) => (
                    <li key={idx} style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem' }}>
                      {item}
                    </li>
                  ))
                ) : (
                  <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>No major information gaps flagged.</p>
                )}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

