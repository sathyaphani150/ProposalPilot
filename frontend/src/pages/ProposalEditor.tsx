import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  Download,
  FileText,
  RefreshCw,
  ShieldAlert,
  BookOpen,
  Target,
} from 'lucide-react'
import { proposalApi, rfpApi } from '@/api/endpoints'
import { getErrorMessage } from '@/api/client'
import type { FinalProposalContent, Proposal } from '@/types'

function SectionCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="insight-card">
      <h3 className="section-title">
        <FileText size={20} color="var(--color-primary-light)" />
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

export function ProposalEditor() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const [hasGenerated, setHasGenerated] = useState(false)

  const { data: analysisResponse } = useQuery({
    queryKey: ['proposalAnalysis', sessionId],
    queryFn: () => rfpApi.getAnalysis(sessionId!),
    enabled: !!sessionId,
  })

  const analysis = analysisResponse?.analysis

  const {
    data: latestResponse,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ['latestProposal', sessionId],
    queryFn: () => proposalApi.getLatestProposal(sessionId!),
    enabled: !!sessionId,
  })

  const proposal = latestResponse?.proposal as Proposal | null | undefined
  const content = proposal?.content as FinalProposalContent | undefined
  const proposalId = proposal?.id

  const { mutate: generateProposal, isPending: isGenerating } = useMutation({
    mutationFn: () => proposalApi.generateProposal(analysis!.id),
    onSuccess: () => {
      toast.success('Proposal generated from War Room outputs.')
      setHasGenerated(true)
      refetch()
    },
    onError: (error) => toast.error('Failed to generate proposal: ' + getErrorMessage(error)),
  })

  const { mutate: exportDocx, isPending: isExportingDocx } = useMutation({
    mutationFn: () => {
      if (!proposalId) throw new Error('No proposal available for export.')
      return proposalApi.exportDocx(proposalId)
    },
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'Proposal.docx'
      link.click()
      URL.revokeObjectURL(url)
    },
    onError: (error) => toast.error('Failed to export DOCX: ' + getErrorMessage(error)),
  })

  const { mutate: exportPdf, isPending: isExportingPdf } = useMutation({
    mutationFn: () => {
      if (!proposalId) throw new Error('No proposal available for export.')
      return proposalApi.exportPdf(proposalId)
    },
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'Proposal.pdf'
      link.click()
      URL.revokeObjectURL(url)
    },
    onError: (error) => toast.error('Failed to export PDF: ' + getErrorMessage(error)),
  })

  useEffect(() => {
    if (analysis && !proposal && !hasGenerated) {
      setHasGenerated(true)
      generateProposal()
    }
  }, [analysis, generateProposal, hasGenerated, proposal])

  const assumptionItems = useMemo(() => content?.assumptions || [], [content])
  const riskItems = useMemo(() => content?.risks || [], [content])

  if (isLoading || isGenerating) {
    return (
      <div className="flex flex-col items-center justify-center text-center" style={{ minHeight: '55vh' }}>
        <div className="spinner" style={{ width: 48, height: 48, borderWidth: 3, marginBottom: '1.5rem' }} />
        <h2 style={{ marginBottom: '0.5rem' }}>Generating Proposal</h2>
        <p style={{ color: 'var(--color-text-secondary)', maxWidth: 560, lineHeight: 1.6 }}>
          Building the final proposal from the RFP analysis, expertise match, architecture recommendation, and War Room outputs.
        </p>
      </div>
    )
  }

  if (!analysis) {
    return (
      <div className="card-elevated text-center" style={{ maxWidth: 520, margin: '4rem auto' }}>
        <ShieldAlert size={48} color="var(--color-error)" style={{ marginBottom: '1rem' }} />
        <h2>Analysis Not Found</h2>
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
        <h2 style={{ marginBottom: '0.75rem' }}>No Proposal Yet</h2>
        <p style={{ color: 'var(--color-text-secondary)', marginBottom: '1.5rem', lineHeight: 1.6 }}>
          Generate the final proposal from the War Room outputs, then export it as DOCX or PDF.
        </p>
        <div className="flex justify-center gap-3">
          <button className="btn btn-primary" onClick={() => generateProposal()} disabled={isGenerating || !analysis}>
            Generate Proposal
          </button>
          <button className="btn btn-secondary" onClick={() => navigate(`/rfp/${sessionId}/war-room`)}>
            Open War Room
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
            <h1>Proposal</h1>
          </div>
          <p className="page-subtitle">
            {analysis.business_problem || 'Generated proposal'} {sessionId ? `· Session ${sessionId.slice(0, 8)}` : ''}
          </p>
        </div>
        <div className="flex gap-3">
          <button className="btn btn-secondary" onClick={() => navigate(`/rfp/${sessionId}/war-room`)}>
            Back to War Room
          </button>
          <button className="btn btn-secondary" onClick={() => generateProposal()} disabled={isGenerating}>
            <RefreshCw size={16} />
            Regenerate
          </button>
          <button className="btn btn-secondary" onClick={() => exportDocx()} disabled={isExportingDocx || !proposal}>
            <Download size={16} />
            Export DOCX
          </button>
          <button className="btn btn-primary" onClick={() => exportPdf()} disabled={isExportingPdf || !proposal}>
            <Download size={16} />
            Export PDF
          </button>
        </div>
      </div>

      <div className="content-stack">
        <div className="card-elevated">
          <div className="prep-summary">
            <div>
              <h3 style={{ marginBottom: '0.75rem' }}>Executive Summary</h3>
              <p className="readable-text">{content.executive_summary}</p>
            </div>
            <div className="insight-card" style={{ padding: '0.9rem' }}>
              <span style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem', textTransform: 'uppercase' }}>
                Proposal Status
              </span>
              <p style={{ color: 'var(--color-success)', fontWeight: 700, marginTop: '0.4rem' }}>
                Ready for export
              </p>
              <p style={{ color: 'var(--color-text-secondary)', marginTop: '0.6rem', fontSize: '0.88rem' }}>
                Version {proposal?.version ?? 'N/A'}
              </p>
            </div>
          </div>
        </div>

        <div className="prep-two-column">
          <SectionCard title="Problem Statement">
            <p className="readable-text">{content.client_problem_statement}</p>
          </SectionCard>
          <SectionCard title="Proposed Solution">
            <p className="readable-text">{content.proposed_solution}</p>
          </SectionCard>
        </div>

        <div className="prep-two-column">
          <SectionCard title="Relevant Experience">
            <p className="readable-text">{content.relevant_experience}</p>
          </SectionCard>
          <SectionCard title="Technical Architecture">
            <p className="readable-text">{content.technical_architecture}</p>
            <div style={{ marginTop: '0.75rem' }}>
              <h4 style={{ marginBottom: '0.5rem' }}>Technology Stack</h4>
            <p className="readable-text">{content.technology_stack}</p>
            </div>
          </SectionCard>
        </div>

        <div className="prep-two-column">
          <SectionCard title="Delivery Approach">
            <p className="readable-text">{content.delivery_approach}</p>
            <div className="flex gap-2" style={{ marginTop: '0.75rem', flexWrap: 'wrap' }}>
              <span className="badge badge-analyzed">Proposal-led delivery</span>
              <span className="badge badge-analyzed">Guidance-aware reruns</span>
            </div>
          </SectionCard>
          <SectionCard title="Commercial Positioning">
            <p className="readable-text">{content.competitive_positioning}</p>
            <div style={{ marginTop: '0.75rem' }}>
              <Target size={18} color="var(--color-info)" />
            </div>
          </SectionCard>
        </div>

        <div className="prep-two-column">
          <SectionCard title="Resource Matrix">
            <p className="readable-text">{content.resource_matrix}</p>
          </SectionCard>
          <SectionCard title="Cost Estimate">
            <p className="readable-text">{content.cost_estimation}</p>
          </SectionCard>
        </div>

        <div className="prep-two-column">
          <SectionCard title="Compliance Matrix">
            <p className="readable-text">{content.compliance_matrix}</p>
          </SectionCard>
          <SectionCard title="Risks">
            <BulletList items={riskItems} empty="No risks generated." />
          </SectionCard>
        </div>

        <div className="prep-two-column">
          <SectionCard title="Assumptions">
            <BulletList items={assumptionItems} empty="No assumptions generated." />
          </SectionCard>
          <SectionCard title="Source Guidance">
            <p className="readable-text">
              The proposal is generated from the RFP analysis, expertise match, architecture recommendation, War Room output, and user guidance.
            </p>
          </SectionCard>
        </div>
      </div>
    </div>
  )
}
