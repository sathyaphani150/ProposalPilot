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
  created_at: string
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
  agent_outputs: Record<AgentName, string | null>
  created_at: string
  updated_at: string
}

// ── Proposal Types ────────────────────────────────────────────────────────
export type ProposalType = 'prep_pack' | 'final_proposal'

export interface PrepPackContent {
  rfp_summary: string
  similar_projects: SimilarProject[]
  past_expertise_story: string
  prospect_call_narrative: string
  discovery_questions: DiscoveryQuestions
  risks_and_assumptions: string[]
  scope_guardrails: string[]
  proposed_architecture_direction: string
}

export interface SimilarProject {
  title: string
  match_type: 'exact' | 'partial' | 'adjacent' | 'none'
  confidence_score: number
  relevance_summary: string
  reusable_assets: string[]
}

export interface DiscoveryQuestions {
  business: string[]
  data: string[]
  integration: string[]
  architecture: string[]
  implementation_readiness: string[]
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
