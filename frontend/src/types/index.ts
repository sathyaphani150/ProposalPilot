/**
 * ProposalPilot AI — TypeScript Type Definitions
 * Single source of truth for all shared types across the frontend.
 */

// ── RFP Types ────────────────────────────────────────────────────────────
export type RFPStatus =
  | 'uploaded'
  | 'analyzing'
  | 'analyzed'
  | 'analysis_failed'
  | 'prep_generating'
  | 'prep_ready'
  | 'war_room_running'
  | 'war_room_done'
  | 'proposal_ready'

export interface RFPSession {
  id: string
  title: string
  client_name: string | null
  status: RFPStatus
  original_filename: string
  file_size_bytes: number
  created_at: string
  updated_at: string
}

export interface RFPAnalysis {
  id: string
  session_id: string
  business_problem: string | null
  functional_requirements: string[]
  non_functional_requirements: string[]
  data_needs: string[]
  integration_needs: string[]
  compliance_needs: string[]
  timeline_risks: string[]
  missing_information: string[]
  scope_boundaries: string[]
  domain_tags: string[]
  estimated_complexity: string | null
  raw_llm_output?: {
    extraction_meta?: {
      mode?: string
      confidence?: number
      warnings?: string[]
      source_chars_used?: number
      source_line_count?: number
      candidate_unit_count?: number
    }
    rfp_intelligence?: RFPIntelligence
    [key: string]: unknown
  }
  created_at: string
}

export interface RFPSentimentAnalysis {
  overall_sentiment?: string
  summary?: string
  confidence?: string
  points?: Array<{
    title?: string
    insight?: string
    evidence?: string
    implication?: string
  }>
  recommended_posture?: string
}

export interface MustAskQuestion {
  category?: string
  question: string
  why_it_matters?: string
  assumption_to_validate?: string
}

export interface TalkingPoint {
  point: string
  client_angle?: string
  proof_needed?: string
}

export interface EvidenceItem {
  title: string
  domain?: string
  item_type?: string
  score?: number
  why_relevant?: string
  tech_stack?: string[]
  tags?: string[]
}

export interface NarrativeSection {
  title?: string
  story?: string
  how_it_helps?: string[]
  evidence_project_title?: string
  confidence?: string
}

export interface ArchitectureSection {
  summary?: string
  components?: string[]
  assumptions?: string[]
  business_view?: string[]
  technical_view?: string[]
  data_flow?: string[]
  integration_flow?: string[]
  security_operations?: string[]
  decision_points?: string[]
  call_prep_questions?: string[]
  architecture_text?: string
  mermaid?: string
  generated_by?: string
}

export interface RFPIntelligence {
  sentiment_analysis?: RFPSentimentAnalysis
  must_ask_questions?: MustAskQuestion[]
  top_risks?: Array<Record<string, unknown>>
  talking_points?: TalkingPoint[]
  narrative?: NarrativeSection
  relevant_knowledge_evidence?: EvidenceItem[]
  architecture?: ArchitectureSection
}

// ── Knowledge Base Types ─────────────────────────────────────────────────
export type KnowledgeItemType =
  | 'project'
  | 'repo'
  | 'doc'
  | 'proposal'
  | 'case_study'
  | 'architecture'

export interface KnowledgeItem {
  id: string
  item_type: KnowledgeItemType
  title: string
  description: string | null
  domain: string | null
  tech_stack: string[]
  tags: string[]
  chunk_count: number
  is_active: boolean
  created_at: string
}

export interface KnowledgeSearchResult {
  point_id: string
  score: number
  text: string
  doc_id: string
  title?: string
  domain?: string
  item_type?: string
  tech_stack?: string[]
  tags?: string[]
}

// ── War Room Types ────────────────────────────────────────────────────────
export type WarRoomStatus =
  | 'idle'
  | 'running'
  | 'paused'
  | 'awaiting_human'
  | 'complete'
  | 'failed'

export type AgentName =
  | 'architect'
  | 'cfo'
  | 'competitor'
  | 'proposal'
  | 'supervisor'

export type AgentStatus = 'idle' | 'thinking' | 'writing' | 'done' | 'error'

export interface AgentStreamEvent {
  agent: AgentName
  type: 'start' | 'token' | 'complete' | 'error' | 'human_required'
  content: string
  timestamp: string
}

export interface WarRoomSession {
  id: string
  rfp_session_id: string
  status: WarRoomStatus
  call_notes: string | null
  human_overrides: Record<string, unknown>
  agent_outputs: Record<string, unknown>
  matched_projects: SimilarProject[]
  review_loops?: number
  final_recommendations?: Record<string, unknown>
  error_message?: string | null
  discussion_log?: Array<{
    agent: string
    target_agent: string
    comment: string
    message_type?: string
    round_index?: number
    timestamp?: string
  }>
  created_at: string
  updated_at: string
}

export interface WarRoomAgentOutput {
  reasoning: string
  confidence: number
  [key: string]: unknown
}

// ── Proposal Types ────────────────────────────────────────────────────────
export type ProposalType = 'prep_pack' | 'final_proposal'

export interface PrepPackContent {
  rfp_summary: string
  client_situation_assessment?: string
  value_propositions?: string[]
  assumptions_to_validate?: string[]
  competitive_considerations?: string[]
  similar_projects: SimilarProject[]
  past_expertise_story: string
  prospect_call_narrative: string
  discovery_questions: DiscoveryQuestions
  talking_points: string[]
  risks_and_assumptions: string[]
  scope_guardrails: string[]
  proposed_architecture_direction: string
  solution_narrative?: string
  quality_note?: {
    generation_mode: string
    retrieval_warning?: string | null
    source: string
  }
}

export interface SimilarProject {
  doc_id?: string
  title: string
  match_type: 'exact' | 'partial' | 'adjacent' | 'none'
  confidence_score: number
  relevance_summary: string
  reusable_assets: string[]
  evidence?: {
    chunk_index: number
    snippet: string
  }
}

export interface DiscoveryQuestions {
  [category: string]: string[] | undefined
  business?: string[]
  data?: string[]
  integration?: string[]
  architecture?: string[]
  implementation_readiness?: string[]
  operations?: string[]
  governance?: string[]
  commercial?: string[]
}

export interface FinalProposalContent {
  executive_summary: string
  client_problem_statement: string
  proposed_solution: string
  relevant_past_experience: string
  technical_architecture: string
  technology_stack: string
  delivery_approach: string
  resource_matrix: ResourceMatrix
  cost_estimation: CostEstimation
  competitive_positioning: string
  compliance_matrix: string
  assumptions_and_exclusions: string
  risks_and_mitigation: string
}

export interface ResourceMatrix {
  roles: ResourceRole[]
  total_hours: number
  duration_weeks: number
}

export interface ResourceRole {
  role: string
  level: string
  hours: number
  rate_per_hour: number
  total_cost: number
}

export interface CostEstimation {
  minimum: number
  recommended: number
  maximum: number
  currency: string
  breakdown: Record<string, number>
}

export interface Proposal {
  id: string
  rfp_session_id: string
  war_room_session_id: string | null
  proposal_type: ProposalType
  version: number
  content: PrepPackContent | FinalProposalContent
  docx_path: string | null
  pdf_path: string | null
  is_published: boolean
  created_at: string
}

// ── UI Utility Types ─────────────────────────────────────────────────────
export interface PaginatedResponse<T> {
  items: T[]
  total: number
}

export type LoadingState = 'idle' | 'loading' | 'success' | 'error'
