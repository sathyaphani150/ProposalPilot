/**
 * ProposalPilot AI — RFP API Functions
 */
import { apiClient } from './client'
import type {
  ArchitectureRecommendation,
  WarRoomResult,
  ExpertiseMatch,
  KnowledgeItem,
  KnowledgeSearchResult,
  RFPSession,
  RFPAnalysis,
  SimilarProject,
} from '@/types'

export const rfpApi = {
  upload: async (
    file: File,
    metadata: { clientName?: string; title?: string }
  ): Promise<RFPSession> => {
    const formData = new FormData()
    formData.append('file', file)
    if (metadata.clientName) formData.append('client_name', metadata.clientName)
    if (metadata.title) formData.append('title', metadata.title)

    const { data } = await apiClient.post<RFPSession>('/rfp/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  list: async (params?: { skip?: number; limit?: number }) => {
    const { data } = await apiClient.get<{ items: RFPSession[]; total: number }>(
      '/rfp',
      { params }
    )
    return data
  },

  getById: async (sessionId: string): Promise<RFPSession> => {
    const { data } = await apiClient.get<RFPSession>(`/rfp/${sessionId}`)
    return data
  },

  triggerAnalysis: async (sessionId: string): Promise<{ task_id: string }> => {
    const { data } = await apiClient.post<{ task_id: string }>(
      `/rfp/${sessionId}/analyze`
    )
    return data
  },

  getAnalysis: async (
    sessionId: string
  ): Promise<{ status: string; analysis: RFPAnalysis | null; error_message?: string | null }> => {
    const { data } = await apiClient.get<{ status: string; analysis: RFPAnalysis | null; error_message?: string | null }>(
      `/rfp/${sessionId}/analysis`
    )
    return data
  },

  delete: async (sessionId: string): Promise<void> => {
    await apiClient.delete(`/rfp/${sessionId}`)
  },
}

export const knowledgeApi = {
  ingest: async (
    file: File | null,
    fields: {
      item_type: string
      title: string
      description?: string
      domain?: string
      tech_stack?: string[]
      tags?: string[]
      extra_metadata?: Record<string, unknown>
    }
  ) => {
    const formData = new FormData()
    if (file) formData.append('file', file)
    formData.append('item_type', fields.item_type)
    formData.append('title', fields.title)
    if (fields.description) formData.append('description', fields.description)
    if (fields.domain) formData.append('domain', fields.domain)
    if (fields.tech_stack) formData.append('tech_stack', JSON.stringify(fields.tech_stack))
    if (fields.tags) formData.append('tags', JSON.stringify(fields.tags))
    if (fields.extra_metadata) {
      formData.append('extra_metadata', JSON.stringify(fields.extra_metadata))
    }

    const { data } = await apiClient.post('/knowledge/ingest', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  list: async (): Promise<{ items: KnowledgeItem[]; total: number }> => {
    const { data } = await apiClient.get<{ items: KnowledgeItem[]; total: number }>('/knowledge/items')
    return data
  },

  search: async (query: string, filters?: Record<string, string>): Promise<KnowledgeSearchResult[]> => {
    const { data } = await apiClient.get<KnowledgeSearchResult[]>('/knowledge/search', {
      params: { q: query, ...filters },
    })
    return data
  },

  delete: async (itemId: string): Promise<void> => {
    await apiClient.delete(`/knowledge/${itemId}`)
  },
}

export const expertiseApi = {
  match: async (payload: { rfp_summary: string; similar_projects: SimilarProject[] }): Promise<ExpertiseMatch> => {
    const { data } = await apiClient.post<ExpertiseMatch>('/expertise/match', payload)
    return data
  },
}

export const architectureApi = {
  recommend: async (payload: {
    rfp_summary: string
    expertise_match: ExpertiseMatch
    similar_projects: SimilarProject[]
  }): Promise<ArchitectureRecommendation> => {
    const { data } = await apiClient.post<ArchitectureRecommendation>('/architecture/recommend', payload)
    return data
  },
}

export const warRoomApi = {
  start: async (sessionId: string, callNotes?: string) => {
    const { data } = await apiClient.post(`/war-room/${sessionId}/start`, {
      call_notes: callNotes,
    })
    return data
  },

  override: async (sessionId: string, overrides: Record<string, unknown>) => {
    const { data } = await apiClient.post(`/war-room/${sessionId}/override`, overrides)
    return data
  },

  getStatus: async (sessionId: string) => {
    const { data } = await apiClient.get(`/war-room/${sessionId}/status`)
    return data
  },

  run: async (analysisId: string): Promise<WarRoomResult> => {
    const { data } = await apiClient.post<WarRoomResult>('/warroom/run', { analysis_id: analysisId })
    return data
  },

  rerun: async (analysisId: string, guidance: string[]): Promise<WarRoomResult> => {
    const { data } = await apiClient.post<WarRoomResult>('/warroom/rerun', {
      analysis_id: analysisId,
      guidance,
    })
    return data
  },
}

export const proposalApi = {
  generate: async (sessionId: string, type: 'prep_pack' | 'final_proposal') => {
    const { data } = await apiClient.post(`/proposals/${sessionId}/generate`, { type })
    return data
  },

  generateProposal: async (analysisId: string, guidance: string[] = []) => {
    const { data } = await apiClient.post('/proposal/generate', {
      analysis_id: analysisId,
      guidance,
    })
    return data
  },

  getById: async (proposalId: string) => {
    const { data } = await apiClient.get(`/proposals/${proposalId}`)
    return data
  },

  getLatestPrepPack: async (sessionId: string) => {
    const { data } = await apiClient.get(`/proposals/session/${sessionId}/prep-pack`)
    return data
  },

  getLatestProposal: async (sessionId: string) => {
    const { data } = await apiClient.get(`/proposal/session/${sessionId}/latest`)
    return data
  },

  export: async (proposalId: string, format: 'docx' | 'pdf') => {
    const response = await apiClient.post(
      `/proposal/export/${format}`,
      { proposal_id: proposalId },
      { responseType: 'blob' }
    )
    return response.data as Blob
  },

  exportDocx: async (proposalId: string) => {
    const response = await apiClient.post(
      '/proposal/export/docx',
      { proposal_id: proposalId },
      { responseType: 'blob' }
    )
    return response.data as Blob
  },

  exportPdf: async (proposalId: string) => {
    const response = await apiClient.post(
      '/proposal/export/pdf',
      { proposal_id: proposalId },
      { responseType: 'blob' }
    )
    return response.data as Blob
  },
}
