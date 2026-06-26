import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { ArrowLeft, FileText, RefreshCw } from 'lucide-react'

import { getErrorMessage } from '@/api/client'
import { proposalApi, rfpApi } from '@/api/endpoints'
import { capitalizeSentenceStarts } from '@/utils/text'

const SECTION_LABELS: Record<string, string> = {
  executive_summary: 'Executive Summary',
  client_problem_statement: 'Client Problem Statement',
  proposed_solution: 'Proposed Solution',
  technical_architecture: 'Technical Architecture',
  technology_stack: 'Technology Stack',
  delivery_approach: 'Delivery Approach',
  commercial_summary: 'Commercial Summary',
  resource_and_effort: 'Resource and Effort',
  competitive_positioning: 'Competitive Positioning',
  compliance_matrix: 'Compliance Matrix',
  risks: 'Risks and Mitigation',
  assumptions: 'Assumptions',
  exclusions: 'Exclusions',
  consistency_flags: 'Consistency Review',
}

function formatLabel(value: string) {
  return SECTION_LABELS[value] || value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function formatNumberText(value: string) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return value
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(numeric)
}

function formatDictString(value: string) {
  const text = value.trim()
  if (!text.startsWith('{') || !text.endsWith('}') || !text.includes(':')) return null

  const entries = text
    .slice(1, -1)
    .split(',')
    .map((part) => part.trim())
    .map((part) => {
      const separatorIndex = part.indexOf(':')
      if (separatorIndex === -1) return null
      const rawKey = part.slice(0, separatorIndex).trim().replace(/^['"]|['"]$/g, '')
      const rawValue = part.slice(separatorIndex + 1).trim().replace(/^['"]|['"]$/g, '')
      if (!rawKey) return null
      const valueText = rawKey === 'currency' || rawKey.includes('pct') ? rawValue : formatNumberText(rawValue)
      return { label: formatLabel(rawKey), value: valueText }
    })
    .filter((entry): entry is { label: string; value: string } => Boolean(entry))

  return entries.length ? entries : null
}

function ProposalValue({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === '') return <p className="text-muted">Not specified.</p>
  if (Array.isArray(value)) {
    if (!value.length) return <p className="text-muted">No items identified.</p>
    return (
      <ul className="proposal-list">
        {value.map((item, index) => (
          <li key={index}><ProposalValue value={item} /></li>
        ))}
      </ul>
    )
  }
  if (typeof value === 'object') {
    return (
      <div className="proposal-detail-grid">
        {Object.entries(value as Record<string, unknown>).map(([key, nestedValue]) => (
          <div className="proposal-detail" key={key}>
            <span className="proposal-detail-title">{formatLabel(key)}</span>
            <ProposalValue value={nestedValue} />
          </div>
        ))}
      </div>
    )
  }
  if (typeof value === 'string') {
    const dictEntries = formatDictString(value)
    if (dictEntries) {
      return (
        <div className="proposal-detail-grid proposal-detail-grid--compact">
          {dictEntries.map((entry) => (
            <div className="proposal-detail" key={entry.label}>
              <span className="proposal-detail-title">{entry.label}</span>
              <p className="readable-text">{capitalizeSentenceStarts(entry.value)}</p>
            </div>
          ))}
        </div>
      )
    }
  }
  return <p className="readable-text">{capitalizeSentenceStarts(String(value))}</p>
}

export function ProposalEditor() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: session } = useQuery({
    queryKey: ['rfpSession', sessionId],
    queryFn: () => rfpApi.getById(sessionId!),
    enabled: !!sessionId,
  })
  const { data: proposal, isLoading, isError, error } = useQuery({
    queryKey: ['finalProposal', sessionId],
    queryFn: () => proposalApi.getLatestFinal(sessionId!),
    enabled: !!sessionId,
  })
  const { mutate: generate, isPending } = useMutation({
    mutationFn: () => proposalApi.generate(sessionId!),
    onSuccess: async (generated) => {
      queryClient.setQueryData(['finalProposal', sessionId], generated)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['rfpSession', sessionId] }),
        queryClient.invalidateQueries({ queryKey: ['rfp-sessions'] }),
      ])
      toast.success('Detailed proposal generated.')
    },
    onError: (generationError) => toast.error(getErrorMessage(generationError)),
  })

  useEffect(() => {
    if (isError && error) toast.error(getErrorMessage(error))
  }, [isError, error])

  return (
    <div className="content-stack">
      <div className="page-header">
        <div>
          <div className="page-title">
            <FileText size={28} color="var(--color-accent)" />
            <h1>Detailed Proposal</h1>
          </div>
          <p className="page-subtitle">{session?.title || 'RFP Session'} - structured final response</p>
        </div>
        <div className="flex gap-3">
          <button className="btn btn-secondary" onClick={() => navigate(`/rfp/${sessionId}/war-room`)}>
            <ArrowLeft size={16} />
            Back to War Room
          </button>
          <button className="btn btn-primary" onClick={() => generate()} disabled={isPending}>
            {isPending ? <span className="spinner" style={{ width: 14, height: 14 }} /> : <RefreshCw size={16} />}
            {proposal ? 'Regenerate Proposal' : 'Generate Proposal'}
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="panel panel--raised skeleton" style={{ minHeight: 320 }} />
      ) : !proposal ? (
        <div className="panel panel--raised empty-state">
          <FileText size={46} color="var(--color-accent)" />
          <h2>Ready to Build the Proposal</h2>
          <p className="page-subtitle max-readable">
            Generate a structured proposal from the completed Architect, CFO, Competitor, and Proposal Writer outputs.
          </p>
          <button className="btn btn-primary btn-lg" onClick={() => generate()} disabled={isPending}>
            Generate Detailed Proposal
          </button>
        </div>
      ) : (
        <>
          <div className="panel proposal-meta">
            <span className="badge badge-done">Proposal Ready</span>
            <span className="text-sm text-secondary">Version {proposal.version}</span>
            <span className="text-sm text-muted">Generated {new Date(proposal.created_at).toLocaleString()}</span>
          </div>
          <div className="proposal-document">
            {Object.entries(proposal.content).map(([key, value]) => (
              <section className="proposal-section" key={key}>
                <h2>{formatLabel(key)}</h2>
                <ProposalValue value={value} />
              </section>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
