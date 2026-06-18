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
    executive_intelligence?: ExecutiveIntelligence
    executive_report?: ExecutiveReport
    [key: string]: unknown
  }
  created_at: string
}

export interface ExecutiveInsight {
  title: string
  insight: string
  evidence: string
  source: 'explicit_in_rfp' | 'inferred_from_rfp' | 'derived_from_industry_knowledge' | string
  confidence: number
  recommendation: string
}

export interface ExecutiveIntelligence {
  executive_summary: string
  key_insights: ExecutiveInsight[]
  opportunity_assessment: ExecutiveInsight[]
  business_drivers: string[]
  risks_and_dependencies: string[]
  recommendations: string[]
  evidence_mode?: string
}

export interface ExecutiveReport {
  leadership_snapshot?: {
    recommendation?: string
    overall_score?: number
    one_line_opportunity?: string
    top_3_reasons_to_bid?: string[]
    top_3_risks?: string[]
    top_5_questions_for_client_call?: string[]
    confidence?: string
    leadership_ready?: boolean
    warning?: string
    [key: string]: unknown
  }
  ceo_brief: string
  bid_recommendation: {
    decision: string
    overall_score: number
    rationale: string
    score_breakdown?: Record<string, number>
    [key: string]: unknown
  }
  business_problem: Record<string, unknown>
  solution_scope: Array<Record<string, unknown>>
  excluded_noise: Array<Record<string, unknown>>
  missing_information: Array<{ category: string; questions: string[] }>
  risk_assessment: Array<Record<string, unknown>>
  delivery_complexity: Record<string, unknown>
  architecture_recommendation: Record<string, unknown>
  commercial_intelligence: Record<string, unknown>
  competitor_intelligence: Array<Record<string, unknown>>
  win_strategy: string[]
  prospect_call_prep: Record<string, unknown>
  past_expertise_match: Record<string, unknown>
  proposal_outline: string[]
  quality_checks: Record<string, unknown>
  excluded_noise_summary?: Record<string, unknown>
  document_section_summary?: Record<string, number>
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
  vector_score?: number
  rerank_score?: number
  confidence?: number
  text: string
  doc_id: string
  project_name?: string
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
  created_at: string
  updated_at: string
}

export interface ArchitectAgentResult {
  agent_name: 'architect' | string
  summary: string
  recommendations: string[]
  risks: string[]
  solution_design: string
  technology_stack: string[]
  architecture_summary: string
  assumptions: string[]
}

export interface CFOAgentResult {
  agent_name: 'cfo' | string
  summary: string
  recommendations: string[]
  risks: string[]
  team_size: number
  effort_months: number
  estimated_cost: string
  cost_risks: string[]
  delivery_model: string
}

export interface CompetitorAgentResult {
  agent_name: 'competitor' | string
  summary: string
  recommendations: string[]
  risks: string[]
  competitors: string[]
  differentiators: string[]
  win_strategy: string[]
}

export interface ProposalDraft {
  agent_name: 'proposal' | string
  summary: string
  recommendations: string[]
  risks: string[]
  executive_summary: string
  solution_overview: string
  differentiators: string[]
}

export interface WarRoomResult {
  architect: ArchitectAgentResult
  cfo: CFOAgentResult
  competitor: CompetitorAgentResult
  proposal: ProposalDraft
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
  business_questions?: string[]
  data_questions?: string[]
  integration_questions?: string[]
  architecture_questions?: string[]
  implementation_questions?: string[]
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
  confidence?: number
  relevance_summary: string
  reusable_assets: string[]
  evidence?: {
    chunk_index: number
    snippet: string
  }
}

export interface ExpertiseMatch {
  match_type: 'Exact Match' | 'Partial Match' | 'Adjacent Match' | 'No Match' | string
  confidence: number
  reasoning: string
  matched_projects: string[]
}

export interface ArchitectureRecommendation {
  architecture: string
  reusable_components: string[]
  assumptions: string[]
  validation_questions: string[]
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
  relevant_experience: string
  technical_architecture: string
  technology_stack: string
  delivery_approach: string
  resource_matrix: string
  cost_estimation: string
  competitive_positioning: string
  compliance_matrix: string
  assumptions: string[]
  risks: string[]
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
