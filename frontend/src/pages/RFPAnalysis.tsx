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
  GitBranch,
  HelpCircle,
  LockKeyhole,
  MessageSquare,
  MonitorCog,
  Network,
  RefreshCw,
  ShieldAlert,
  Swords,
  Target,
  UserRound,
} from 'lucide-react'
import { rfpApi } from '@/api/endpoints'
import { getErrorMessage } from '@/api/client'
import type {
  ArchitectureDiagramNode,
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
    war_room_running: 'War Room Active',
    war_room_done: 'War Room Complete',
    proposal_ready: 'Proposal Ready',
  }
  const classes: Record<RFPStatus, string> = {
    uploaded: 'badge-uploaded',
    analyzing: 'badge-analyzing',
    analyzed: 'badge-analyzed',
    analysis_failed: 'badge-danger',
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
      summary: 'Deploy the solution around the RFP scope that has been confirmed, with clear ownership for users, data, integrations, controls, environments, and acceptance evidence.',
      business_view: ['Confirm the operating outcome, owner, success metric, and acceptance authority before finalizing the design.'],
      technical_view: ['Separate user experience, workflow services, integration adapters, data responsibilities, controls, and observability.'],
      decision_points: ['Validate integration readiness, data ownership, control evidence, release scope, and support responsibilities before pricing.'],
      call_prep_questions: ['Which owner can confirm the success metric, source systems, security gates, and acceptance evidence?'],
      diagram: {
        title: 'Deployment readiness view for modular RFP delivery',
        notation: 'Deployment flow / C4 container model',
        view: 'Deployment readiness',
        nodes: [
          { id: 'executiveSponsor', label: 'Executive sponsor / business owner', kind: 'person', group: 'Stakeholders', description: 'Owns business outcomes, acceptance authority, and trade-offs.' },
          { id: 'clientUsers', label: 'Client users and operators', kind: 'person', group: 'Stakeholders', description: 'Use the release-one workflows and provide acceptance feedback.' },
          { id: 'experience', label: 'Client channels / user interface', kind: 'container', group: 'Channels', description: 'Presents intake, review, dashboards, and operational screens.', technology: 'Web/mobile application' },
          { id: 'workflow', label: 'Application workflow services', kind: 'container', group: 'Solution Core', description: 'Coordinates workflow state, business rules, and acceptance evidence.', technology: 'Application services' },
          { id: 'integrationAdapters', label: 'Integration/API adapter layer', kind: 'container', group: 'Data & Integrations', description: 'Keeps external interfaces behind contracts, owners, and release gates.', technology: 'API / batch adapters' },
          { id: 'dataStore', label: 'Data layer', kind: 'container', group: 'Data & Integrations', description: 'Stores records, reporting data, audit evidence, and migration outputs.', technology: 'Governed data store' },
          { id: 'controlPlane', label: 'Security and audit logging', kind: 'container', group: 'Controls & Operations', description: 'Handles access, audit, encryption, and approval evidence.', technology: 'Security controls' },
          { id: 'observability', label: 'Monitoring and operations', kind: 'container', group: 'Controls & Operations', description: 'Tracks health, failures, support readiness, and release status.', technology: 'Monitoring and support' },
        ],
        edges: [
          { from: 'executiveSponsor', to: 'experience', label: 'sets outcomes and acceptance criteria' },
          { from: 'clientUsers', to: 'experience', label: 'use release-one workflows' },
          { from: 'experience', to: 'workflow', label: 'submits work, decisions, and evidence' },
          { from: 'workflow', to: 'integrationAdapters', label: 'requests confirmed client interfaces' },
          { from: 'workflow', to: 'dataStore', label: 'reads, validates, writes, and reports data' },
          { from: 'workflow', to: 'controlPlane', label: 'enforces access, audit, and sign-off gates' },
          { from: 'workflow', to: 'observability', label: 'emits health, defects, and support signals' },
        ],
      },
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
    value?.architecture?.summary ||
    value?.architecture?.diagram?.nodes?.length ||
    value?.architecture?.business_view?.length ||
    value?.architecture?.technical_view?.length ||
    value?.architecture?.security_operations?.length
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

const architectureGroupOrder = [
  'Stakeholders',
  'Current State',
  'Channels',
  'Search Channels',
  'Mobile Channels',
  'Solution Core',
  'NLP & Search Core',
  'Content & Engagement Core',
  'Migration Core',
  'Target Runtime',
  'Testing & Release',
  'Data & Integrations',
  'Enterprise Integrations',
  'Authority Integrations',
  'Marketplace Integrations',
  'Data Management',
  'Data & Reporting',
  'Data & Model Evidence',
  'Data & Compliance',
  'Insights & Reporting',
  'Controls & Operations',
]

function ArchitectureNodeIcon({ node }: { node: ArchitectureDiagramNode }) {
  const kind = (node.kind || '').toLowerCase()
  const group = (node.group || '').toLowerCase()
  if (kind.includes('person')) return <UserRound size={17} />
  if (group.includes('integration')) return <Network size={17} />
  if (node.id.toLowerCase().includes('data') || group.includes('data')) return <Database size={17} />
  if (group.includes('control')) return <LockKeyhole size={17} />
  if (node.id.toLowerCase().includes('observability') || group.includes('operation')) return <MonitorCog size={17} />
  return <GitBranch size={17} />
}

function ArchitectureDiagramView({ architecture }: { architecture: NonNullable<RFPIntelligence['architecture']> }) {
  const diagram = architecture.diagram
  const nodes = diagram?.nodes || []
  const edges = diagram?.edges || []
  if (!nodes.length) return null

  const nodeById = new Map(nodes.map((node) => [node.id, node]))
  const nodeLabels = new Map(nodes.map((node) => [node.id, node.label]))
  const fallbackLanes = [
    ...architectureGroupOrder.filter((group) => nodes.some((node) => node.group === group)),
    ...Array.from(new Set(nodes.map((node) => node.group).filter(Boolean))).filter(
      (group) => !architectureGroupOrder.includes(group),
    ),
  ].map((group) => ({
    id: group.replace(/[^a-z0-9]+/gi, '-').toLowerCase(),
    title: group,
    description: '',
    node_ids: nodes.filter((node) => node.group === group).map((node) => node.id),
  }))
  const lanes = (diagram?.lanes?.length ? diagram.lanes : fallbackLanes)
    .map((lane) => ({
      ...lane,
      node_ids: (lane.node_ids || []).filter((nodeId) => nodeById.has(nodeId)),
    }))
    .filter((lane) => lane.node_ids.length)
  const visibleEdges = (diagram?.primary_flow?.length ? diagram.primary_flow : edges).filter(
    (edge) => nodeById.has(edge.from) && nodeById.has(edge.to),
  )
  const summaryItems = diagram?.executive_summary?.length
    ? diagram.executive_summary
    : [
        'Read left to right: users, deployed capability, data and integrations, then release controls.',
        'Each connection shows what must be confirmed before proposal scope, pricing, and go-live approval.',
      ]

  return (
    <div className="architecture-diagram">
      <div className="architecture-diagram-header">
        <div>
          <h4>{diagram?.title || 'Deployment readiness view'}</h4>
          <p>{diagram?.notation || 'Deployment flow / C4 container model'}{diagram?.view ? ` - ${diagram.view}` : ''}</p>
        </div>
      </div>

      <div className="architecture-executive-strip">
        {summaryItems.map((item, index) => (
          <div className="architecture-executive-item" key={`${item}-${index}`}>
            <span>{index + 1}</span>
            <p>{item}</p>
          </div>
        ))}
      </div>

      <div className="architecture-map">
        {lanes.map((lane, index) => (
          <section className="architecture-lane" key={lane.id}>
            <div className="architecture-lane-header">
              <h5>{lane.title}</h5>
              {lane.description ? <p>{lane.description}</p> : null}
            </div>
            <div className="architecture-node-stack">
              {lane.node_ids.map((nodeId) => {
                const node = nodeById.get(nodeId)
                if (!node) return null
                return (
                  <div className={`architecture-node architecture-node-${(node.kind || 'container').replace(/[^a-z0-9]+/gi, '-').toLowerCase()}`} key={node.id}>
                    <div className="architecture-node-title">
                      <ArchitectureNodeIcon node={node} />
                      <span>{node.label}</span>
                    </div>
                    {node.description ? <p>{node.description}</p> : null}
                    <div className="architecture-node-footer">
                      <span>{node.group}</span>
                      {node.technology ? <strong>{node.technology}</strong> : null}
                    </div>
                  </div>
                )
              })}
            </div>
            {index < lanes.length - 1 ? <div className="architecture-lane-arrow" aria-hidden="true" /> : null}
          </section>
        ))}
      </div>

      {visibleEdges.length ? (
        <div className="architecture-path">
          <div className="architecture-path-header">
            <h5>Deployment Flow</h5>
            <p>Every arrow is an implementation or governance dependency to confirm for this RFP.</p>
          </div>
          {visibleEdges.map((edge, index) => (
            <div className="architecture-path-step" key={`${edge.from}-${edge.to}-${index}`}>
              <span className="architecture-flow-index">{index + 1}</span>
              <span>{nodeLabels.get(edge.from) || edge.from}</span>
              <strong>{edge.label}</strong>
              <span>{nodeLabels.get(edge.to) || edge.to}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function firstMatchingLabel(values: string[], keywords: string[], fallback: string) {
  const match = values.find((value) => keywords.some((keyword) => value.toLowerCase().includes(keyword)))
  return match || fallback
}

function withArchitectureFallbackDiagram(
  architecture: NonNullable<RFPIntelligence['architecture']>,
  analysis?: RFPAnalysisType,
) {
  if (architecture.diagram?.nodes?.length) return architecture
  const values = [
    ...(analysis?.functional_requirements || []),
    ...(analysis?.integration_needs || []),
    ...(analysis?.data_needs || []),
    ...(analysis?.non_functional_requirements || []),
    ...(analysis?.compliance_needs || []),
    ...(analysis?.scope_boundaries || []),
    ...(analysis?.domain_tags || []),
    analysis?.business_problem || '',
  ].map(cleanDisplayText).filter(Boolean)
  const text = values.join(' ').toLowerCase()
  const isSearch = ['search', 'query', 'solr', 'nlp', 'lemmatization', 'stemming', 'tokenization', 'relevance'].some((term) => text.includes(term))
  const isMigration = ['aws', 'migration', 'dedicated host', 'test environment', 'upgrade process', 'release process'].some((term) => text.includes(term))
  const isMobile = ['mobile', 'push notification', 'learning module', 'quiz', 'multilingual'].some((term) => text.includes(term))
  const isWorkflow = ['workflow', 'approval', 'case', 'routing', 'review'].some((term) => text.includes(term))

  if (isSearch) {
    return {
      ...architecture,
      diagram: {
        title: 'Search and NLP deployment view',
        notation: 'Deployment flow / C4 container model',
        view: 'Deployment readiness',
        nodes: [
          { id: 'executiveSponsor', label: 'Executive sponsor / business owner', kind: 'person', group: 'Stakeholders', description: 'Owns search-quality outcomes and acceptance thresholds.' },
          { id: 'clientUsers', label: 'Marketplace search users and catalog teams', kind: 'person', group: 'Stakeholders', description: 'Submit queries, review relevance, and validate catalog/category outcomes.' },
          { id: 'searchExperience', label: firstMatchingLabel(values, ['search', 'query'], 'Marketplace search experience'), kind: 'container', group: 'Search Channels', description: 'Captures search terms and returns ranked results.', technology: 'Search UI / API' },
          { id: 'queryUnderstanding', label: firstMatchingLabel(values, ['string', 'query intent', 'stemming', 'lemmatization', 'tokenization'], 'Query understanding and normalization service'), kind: 'container', group: 'NLP & Search Core', description: 'Normalizes queries and derives intent signals.', technology: 'NLP pipeline' },
          { id: 'categoryClassifier', label: firstMatchingLabel(values, ['category', 'classification', 'catalog'], 'Catalog category classification service'), kind: 'container', group: 'NLP & Search Core', description: 'Classifies category intent and supports seller/product suggestions.', technology: 'ML classification' },
          { id: 'solrSearch', label: firstMatchingLabel(values, ['solr'], 'Existing Apache Solr search platform'), kind: 'external_system', group: 'Marketplace Integrations', description: 'Existing search platform that must remain operational during integration.' },
          { id: 'modelEvidence', label: firstMatchingLabel(values, ['training', 'validation', 'metric'], 'Training and relevance evaluation store'), kind: 'container', group: 'Data & Model Evidence', description: 'Stores validation data, relevance metrics, and error-review evidence.', technology: 'Evaluation data store' },
          { id: 'searchMonitoring', label: 'Search quality monitoring', kind: 'container', group: 'Controls & Operations', description: 'Tracks relevance, query failures, drift, and tuning triggers.', technology: 'Search observability' },
        ],
        edges: [
          { from: 'clientUsers', to: 'searchExperience', label: 'submit marketplace queries' },
          { from: 'searchExperience', to: 'queryUnderstanding', label: 'sends raw search terms' },
          { from: 'queryUnderstanding', to: 'categoryClassifier', label: 'derives catalog intent' },
          { from: 'queryUnderstanding', to: 'solrSearch', label: 'executes normalized retrieval' },
          { from: 'modelEvidence', to: 'categoryClassifier', label: 'provides validation evidence' },
          { from: 'queryUnderstanding', to: 'searchMonitoring', label: 'emits relevance and failure metrics' },
        ],
      },
    } satisfies NonNullable<RFPIntelligence['architecture']>
  }

  if (isMigration) {
    return {
      ...architecture,
      diagram: {
        title: 'Cloud migration deployment view',
        notation: 'Deployment flow / C4 container model',
        view: 'Deployment readiness',
        nodes: [
          { id: 'executiveSponsor', label: 'Executive sponsor / business owner', kind: 'person', group: 'Stakeholders', description: 'Owns migration risk posture and production acceptance.' },
          { id: 'clientUsers', label: 'Application users, testers, and release owners', kind: 'person', group: 'Stakeholders', description: 'Validate migrated behavior, UAT evidence, and release readiness.' },
          { id: 'currentApplication', label: firstMatchingLabel(values, ['etrm', 'application'], 'Current application baseline'), kind: 'external_system', group: 'Current State', description: 'Existing application and environment to reproduce or migrate.' },
          { id: 'migrationRunbook', label: 'Migration and cutover runbook', kind: 'container', group: 'Migration Core', description: 'Coordinates migration steps, rollback criteria, and acceptance evidence.', technology: 'Migration workstream' },
          { id: 'targetRuntime', label: firstMatchingLabel(values, ['aws', 'dedicated host'], 'Target cloud runtime'), kind: 'container', group: 'Target Runtime', description: 'Hosts the migrated application in the approved target environment.', technology: 'Cloud host' },
          { id: 'testEnvironment', label: firstMatchingLabel(values, ['test environment', 'uat', 'validation'], 'Test and validation environment'), kind: 'container', group: 'Testing & Release', description: 'Runs regression, UAT, defect triage, and sign-off evidence.', technology: 'Test environment' },
          { id: 'releaseProcess', label: firstMatchingLabel(values, ['upgrade', 'release'], 'Formal release and upgrade process'), kind: 'container', group: 'Testing & Release', description: 'Controls promotion, rollback, and future version releases.', technology: 'Release governance' },
          { id: 'securityReview', label: firstMatchingLabel(values, ['security', 'confidential', 'cpra'], 'Security and confidentiality review'), kind: 'container', group: 'Controls & Operations', description: 'Confirms evidence, access controls, remediation, and go-live approval.', technology: 'Security compliance' },
        ],
        edges: [
          { from: 'currentApplication', to: 'migrationRunbook', label: 'provides source baseline' },
          { from: 'migrationRunbook', to: 'targetRuntime', label: 'rehosts and validates runtime' },
          { from: 'targetRuntime', to: 'testEnvironment', label: 'is tested before go-live' },
          { from: 'testEnvironment', to: 'releaseProcess', label: 'feeds release evidence' },
          { from: 'securityReview', to: 'targetRuntime', label: 'gates production readiness' },
        ],
      },
    } satisfies NonNullable<RFPIntelligence['architecture']>
  }

  if (isMobile) {
    return {
      ...architecture,
      diagram: {
        title: 'Mobile application deployment view',
        notation: 'Deployment flow / C4 container model',
        view: 'Deployment readiness',
        nodes: [
          { id: 'executiveSponsor', label: 'Executive sponsor / business owner', kind: 'person', group: 'Stakeholders', description: 'Owns adoption outcomes and release acceptance.' },
          { id: 'clientUsers', label: 'Mobile users and content teams', kind: 'person', group: 'Stakeholders', description: 'Use app content and validate published experiences.' },
          { id: 'mobileApp', label: firstMatchingLabel(values, ['mobile'], 'Mobile application'), kind: 'container', group: 'Mobile Channels', description: 'Delivers mobile journeys, content, feedback, and notifications.', technology: 'Mobile app' },
          { id: 'contentAdmin', label: firstMatchingLabel(values, ['content', 'back-office', 'learning', 'quiz'], 'Back-office content management module'), kind: 'container', group: 'Content & Engagement Core', description: 'Manages content, events, quizzes, publishing, and administration.', technology: 'CMS / admin module' },
          { id: 'authorityApis', label: firstMatchingLabel(values, ['api', 'statistical'], 'Client-provided mobile/statistical APIs'), kind: 'external_system', group: 'Authority Integrations', description: 'Confirmed client APIs for credentials, payloads, cadence, and test access.' },
          { id: 'reporting', label: firstMatchingLabel(values, ['dashboard', 'report'], 'Initiative dashboards and reporting'), kind: 'container', group: 'Data & Reporting', description: 'Publishes initiative dashboards and management reports.', technology: 'Analytics/reporting' },
          { id: 'securityAudit', label: firstMatchingLabel(values, ['security', 'audit', 'uat'], 'Security audit and acceptance closure'), kind: 'container', group: 'Controls & Operations', description: 'Tracks audit findings, remediation evidence, UAT closure, and go-live approval.', technology: 'Security/UAT gate' },
        ],
        edges: [
          { from: 'clientUsers', to: 'mobileApp', label: 'consume content and submit feedback' },
          { from: 'contentAdmin', to: 'mobileApp', label: 'publishes approved content' },
          { from: 'mobileApp', to: 'authorityApis', label: 'requests client data' },
          { from: 'authorityApis', to: 'reporting', label: 'feeds dashboards' },
          { from: 'securityAudit', to: 'mobileApp', label: 'gates release readiness' },
        ],
      },
    } satisfies NonNullable<RFPIntelligence['architecture']>
  }

  return {
    ...architecture,
    diagram: {
      title: isWorkflow ? 'Workflow platform deployment view' : 'Application deployment view',
      notation: 'Deployment flow / C4 container model',
      view: 'Deployment readiness',
      nodes: [
        { id: 'executiveSponsor', label: 'Executive sponsor / business owner', kind: 'person', group: 'Stakeholders', description: 'Owns business outcomes, acceptance authority, and delivery trade-offs.' },
        { id: 'clientUsers', label: 'Client users and operators', kind: 'person', group: 'Stakeholders', description: 'Use the delivered capability and provide release-one feedback.' },
        { id: 'experience', label: firstMatchingLabel(values, ['portal', 'dashboard', 'application', 'workflow'], 'Client experience'), kind: 'container', group: 'Channels', description: 'Primary user-facing channel or workflow surface.', technology: 'Application UI' },
        { id: 'workflow', label: firstMatchingLabel(values, ['workflow', 'approval', 'routing', 'review'], architecture.summary || 'Application workflow services'), kind: 'container', group: 'Solution Core', description: 'Coordinates workflow state, business rules, and acceptance evidence.', technology: 'Application services' },
        { id: 'integrationAdapters', label: firstMatchingLabel(values, ['api', 'integration', 'identity', 'finance', 'repository'], 'Enterprise integration adapters'), kind: 'container', group: 'Data & Integrations', description: 'Separates client-owned systems behind explicit interface contracts.', technology: 'API / batch adapters' },
        { id: 'dataStore', label: firstMatchingLabel(values, ['data', 'record', 'report', 'database'], 'Governed data store'), kind: 'container', group: 'Data & Integrations', description: 'Stores operational records, migrated data, reports, and audit evidence.', technology: 'Data store' },
        { id: 'controlPlane', label: firstMatchingLabel(values, ['security', 'audit', 'access', 'compliance'], 'Security and audit controls'), kind: 'container', group: 'Controls & Operations', description: 'Handles access, audit, security evidence, and approval gates.', technology: 'Security controls' },
        { id: 'observability', label: firstMatchingLabel(values, ['monitoring', 'support', 'maintenance'], 'Monitoring and support operations'), kind: 'container', group: 'Controls & Operations', description: 'Tracks workflow health, integration failures, support readiness, and release status.', technology: 'Monitoring and support' },
      ],
      edges: [
        { from: 'executiveSponsor', to: 'experience', label: 'sets outcomes and acceptance criteria' },
        { from: 'clientUsers', to: 'experience', label: 'use release-one workflows' },
        { from: 'experience', to: 'workflow', label: 'submits work, decisions, and evidence' },
        { from: 'workflow', to: 'integrationAdapters', label: 'requests confirmed client interfaces' },
        { from: 'workflow', to: 'dataStore', label: 'reads, validates, writes, and reports data' },
        { from: 'workflow', to: 'controlPlane', label: 'enforces access, audit, and sign-off gates' },
        { from: 'workflow', to: 'observability', label: 'emits health, defects, and support signals' },
      ],
    },
  } satisfies NonNullable<RFPIntelligence['architecture']>
}

function ArchitectureView({ architecture, analysis }: { architecture?: RFPIntelligence['architecture']; analysis?: RFPAnalysisType }) {
  if (!architecture) return <p className="readable-text">No architecture recommendation was generated.</p>
  const displayArchitecture = withArchitectureFallbackDiagram(architecture, analysis)
  const hasDetails = Boolean(
    displayArchitecture.business_view?.length ||
    displayArchitecture.technical_view?.length ||
    displayArchitecture.data_flow?.length ||
    displayArchitecture.integration_flow?.length ||
    displayArchitecture.security_operations?.length ||
    displayArchitecture.decision_points?.length ||
    displayArchitecture.call_prep_questions?.length
  )
  return (
    <div className="content-stack">
      {displayArchitecture.summary ? <p className="readable-text">{displayArchitecture.summary}</p> : null}
      <ArchitectureDiagramView architecture={displayArchitecture} />
      {displayArchitecture.structurizr_dsl ? (
        <details className="architecture-dsl">
          <summary>Structurizr DSL</summary>
          <pre>{displayArchitecture.structurizr_dsl}</pre>
        </details>
      ) : null}
      {hasDetails ? (
        <>
          <ArchitectureSubsection title="Business View" items={displayArchitecture.business_view} empty="No business architecture view generated." />
          <ArchitectureSubsection title="Technical Blueprint" items={displayArchitecture.technical_view} empty="No technical blueprint generated." />
          <div className="prep-two-column">
            <ArchitectureSubsection title="Data Flow" items={displayArchitecture.data_flow} empty="No data flow generated." />
            <ArchitectureSubsection title="Integration Flow" items={displayArchitecture.integration_flow} empty="No integration flow generated." />
          </div>
          <ArchitectureSubsection title="Security and Operations" items={displayArchitecture.security_operations} empty="No security or operations detail generated." />
          <div className="prep-two-column">
            <ArchitectureSubsection title="Decision Points" items={displayArchitecture.decision_points} empty="No design decisions generated." />
            <ArchitectureSubsection title="Call Prep Questions" items={displayArchitecture.call_prep_questions} empty="No architecture call questions generated." />
          </div>
        </>
      ) : null}
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
              <ArchitectureView architecture={intelligence.architecture} analysis={analysis} />
            </SectionCard>
          ) : null}
        </div>
      )}
    </div>
  )
}
