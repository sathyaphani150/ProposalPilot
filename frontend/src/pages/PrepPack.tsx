import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  Brain,
  CheckCircle,
  HelpCircle,
  RefreshCw,
  ShieldAlert,
  Target,
} from 'lucide-react'
import { proposalApi, rfpApi } from '@/api/endpoints'
import { getErrorMessage } from '@/api/client'
import type { PrepPackContent, Proposal } from '@/types'

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

function BulletList({ items, empty }: { items?: string[]; empty: string }) {
  if (!items || items.length === 0) {
    return <p style={{ color: 'var(--color-text-muted)' }}>{empty}</p>
  }
  return (
    <ul className="clean-list">
      {items.map((item, index) => (
        <li key={`${item}-${index}`}>{item}</li>
      ))}
    </ul>
  )
}

export function PrepPack() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const autoGenerateAttemptedRef = useRef<string | null>(null)

  const { data: session, isLoading: isSessionLoading } = useQuery({
    queryKey: ['rfpSession', sessionId],
    queryFn: () => rfpApi.getById(sessionId!),
    enabled: !!sessionId,
  })

  const {
    data: latestResponse,
    isLoading: isPrepLoading,
    refetch: refetchPrepPack,
  } = useQuery({
    queryKey: ['latestPrepPack', sessionId],
    queryFn: () => proposalApi.getLatestPrepPack(sessionId!),
    enabled: !!sessionId,
  })

  const proposal = latestResponse?.proposal as Proposal | null | undefined
  const content = proposal?.content as PrepPackContent | undefined

  const { mutate: generatePrepPack, isPending: isGenerating } = useMutation({
    mutationFn: () => proposalApi.generate(sessionId!, 'prep_pack'),
    onSuccess: () => {
      toast.success('Prep pack generated from RFP analysis and KB evidence.')
      refetchPrepPack()
    },
    onError: (error) => {
      toast.error('Failed to generate prep pack: ' + getErrorMessage(error))
    },
  })

  useEffect(() => {
    if (
      sessionId &&
      latestResponse &&
      latestResponse.proposal === null &&
      autoGenerateAttemptedRef.current !== sessionId &&
      !isGenerating
    ) {
      autoGenerateAttemptedRef.current = sessionId
      generatePrepPack()
    }
  }, [generatePrepPack, isGenerating, latestResponse, sessionId])

  if (isSessionLoading || isPrepLoading || isGenerating) {
    return (
      <div className="flex flex-col items-center justify-center text-center" style={{ minHeight: '55vh' }}>
        <div className="spinner" style={{ width: 48, height: 48, borderWidth: 3, marginBottom: '1.5rem' }} />
        <h2 style={{ marginBottom: '0.5rem' }}>Generating Prospect Prep Pack</h2>
        <p style={{ color: 'var(--color-text-secondary)', maxWidth: 560, lineHeight: 1.6 }}>
          Matching the RFP against internal knowledge and preparing grounded discovery questions, risks, and call narrative.
        </p>
      </div>
    )
  }

  if (!session) {
    return (
      <div className="card-elevated text-center" style={{ maxWidth: 520, margin: '4rem auto' }}>
        <AlertTriangle size={48} color="var(--color-error)" style={{ marginBottom: '1rem' }} />
        <h2>Session Not Found</h2>
        <button className="btn btn-primary" style={{ marginTop: '1.5rem' }} onClick={() => navigate('/dashboard')}>
          Back to Dashboard
        </button>
      </div>
    )
  }

  if (!content) {
    return (
      <div className="card-elevated text-center" style={{ maxWidth: 620, margin: '4rem auto' }}>
        <BookOpen size={52} color="var(--color-primary-light)" style={{ marginBottom: '1rem' }} />
        <h2 style={{ marginBottom: '0.75rem' }}>No Prep Pack Yet</h2>
        <p style={{ color: 'var(--color-text-secondary)', marginBottom: '1.5rem', lineHeight: 1.6 }}>
          Run RFP analysis first, then generate a prep pack backed by knowledge-base matches.
        </p>
        <button className="btn btn-primary" onClick={() => generatePrepPack()} disabled={isGenerating}>
          Generate Prep Pack
        </button>
      </div>
    )
  }

  const questions = content.discovery_questions

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <div className="page-title">
            <BookOpen size={28} color="var(--color-primary-light)" />
            <h1>Prospect Call Prep Pack</h1>
          </div>
          <p className="page-subtitle">
            {session.title} {session.client_name ? `for ${session.client_name}` : ''}
          </p>
        </div>
        <div className="flex gap-3">
          <button className="btn btn-secondary" onClick={() => generatePrepPack()} disabled={isGenerating}>
            <RefreshCw size={16} />
            Regenerate
          </button>
          <button className="btn btn-primary" onClick={() => navigate(`/rfp/${sessionId}/war-room`)}>
            Open War Room
            <ArrowRight size={16} />
          </button>
        </div>
      </div>

      <div className="content-stack">
      <div className="card-elevated">
        <div className="prep-summary">
          <div>
            <h3 style={{ marginBottom: '0.75rem' }}>Executive Call Objective</h3>
            <p className="readable-text">{content.client_situation_assessment || content.rfp_summary}</p>
          </div>
          <div className="insight-card" style={{ padding: '0.9rem' }}>
            <span style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem', textTransform: 'uppercase' }}>
              Grounding Mode
            </span>
            <p style={{ color: 'var(--color-success)', fontWeight: 700, marginTop: '0.4rem' }}>
              Evidence-backed
            </p>
            {content.quality_note?.retrieval_warning && (
              <p style={{ color: 'var(--color-warning)', marginTop: '0.75rem', fontSize: '0.85rem' }}>
                {content.quality_note.retrieval_warning}
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="prep-two-column">
        <SectionCard title="Call Narrative" icon={<Brain size={20} color="var(--color-accent)" />}>
          <p className="readable-text">{content.prospect_call_narrative}</p>
        </SectionCard>
        <SectionCard title="Value Proposition" icon={<Target size={20} color="var(--color-primary-light)" />}>
          <BulletList items={content.value_propositions} empty="No value propositions generated." />
        </SectionCard>
      </div>

      <div className="prep-two-column">
        <SectionCard title="Discovery Questions" icon={<HelpCircle size={20} color="var(--color-warning)" />}>
          <div className="question-grid">
            {Object.entries(questions)
              .filter(([, items]) => Array.isArray(items) && items.length > 0)
              .map(([group, items]) => (
            <div key={group} className="match-card">
              <h4 style={{ textTransform: 'capitalize', marginBottom: '0.5rem' }}>{group.replaceAll('_', ' ')}</h4>
              <BulletList items={items} empty="No questions generated for this group." />
            </div>
            ))}
          </div>
        </SectionCard>

        <div className="side-stack">
          <SectionCard title="Talking Points" icon={<Target size={20} color="var(--color-info)" />}>
            <BulletList items={content.talking_points} empty="No talking points generated." />
          </SectionCard>
          <SectionCard title="Assumptions To Validate" icon={<HelpCircle size={20} color="var(--color-warning)" />}>
            <BulletList items={content.assumptions_to_validate} empty="No assumptions generated." />
          </SectionCard>
          <SectionCard title="Risks & Assumptions" icon={<ShieldAlert size={20} color="var(--color-error)" />}>
            <BulletList items={content.risks_and_assumptions} empty="No risks identified." />
          </SectionCard>
          <SectionCard title="Scope Guardrails" icon={<CheckCircle size={20} color="var(--color-success)" />}>
            <BulletList items={content.scope_guardrails} empty="No guardrails identified." />
          </SectionCard>
        </div>
      </div>

      <div className="prep-two-column">
        <SectionCard title="Solution Narrative" icon={<Brain size={20} color="var(--color-accent)" />}>
          <p className="readable-text">{content.solution_narrative || content.proposed_architecture_direction}</p>
        </SectionCard>
        <SectionCard title="Competitive Considerations" icon={<ShieldAlert size={20} color="var(--color-warning)" />}>
          <BulletList items={content.competitive_considerations} empty="No competitive considerations generated." />
        </SectionCard>
      </div>

      <SectionCard title="Relevant Knowledge Evidence" icon={<CheckCircle size={20} color="var(--color-success)" />}>
        {!content.similar_projects || content.similar_projects.length === 0 ? (
          <p style={{ color: 'var(--color-text-muted)' }}>
            No high-confidence internal match passed the relevance gate. Use the Knowledge Base to add comparable case studies, public solution patterns, architectures, and lessons learned.
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {content.similar_projects.map((project, index) => (
              <div key={`${project.title}-${index}`} className="match-card">
                <div className="flex justify-between items-center" style={{ marginBottom: '0.5rem', gap: '1rem' }}>
                  <strong>{project.title}</strong>
                  <span className="badge badge-analyzed" style={{ textTransform: 'uppercase' }}>
                    {project.match_type} - {Math.round(project.confidence_score * 100)}%
                  </span>
                </div>
                <p className="readable-text">{project.relevance_summary}</p>
                {project.reusable_assets.length > 0 && (
                  <div className="flex gap-2" style={{ flexWrap: 'wrap', marginTop: '0.75rem' }}>
                    {project.reusable_assets.map((asset) => (
                      <span key={asset} className="badge">{asset}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      <div className="card-elevated">
        <h3 style={{ marginBottom: '0.75rem' }}>Proposed Architecture Direction</h3>
        <p className="readable-text">
          {content.proposed_architecture_direction}
        </p>
      </div>
      </div>
    </div>
  )
}
