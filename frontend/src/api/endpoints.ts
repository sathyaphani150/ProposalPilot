/**
 * ProposalPilot AI — RFP API Functions
 */
import { apiClient } from './client'
import axios from 'axios'
import type { KnowledgeItem, KnowledgeSearchResult, Proposal, RFPSession, RFPAnalysis } from '@/types'

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
    const { data } = await apiClient.get<{ items: RFPSession[]; total: number; status_counts?: Partial<Record<RFPSession['status'], number>> }>(
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

  getAnalysis: async (sessionId: string): Promise<{ status: string; analysis: RFPAnalysis | null }> => {
    const { data } = await apiClient.get<{ status: string; analysis: RFPAnalysis | null }>(
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

export const warRoomApi = {
  start: async (sessionId: string, callNotes?: string) => {
    const { data } = await apiClient.post('/war-room/run', {
      session_id: sessionId,
      call_notes: callNotes,
    })
    return data
  },

  override: async (sessionId: string, overrides: Record<string, unknown>) => {
    const { data } = await apiClient.post('/war-room/override', {
      session_id: sessionId,
      override: overrides,
    })
    return data
  },

  getStatus: async (sessionId: string) => {
    const { data } = await apiClient.get(`/war-room/${sessionId}/status`)
    return data
  },
}

export const proposalApi = {
  generate: async (sessionId: string): Promise<Proposal> => {
    const { data } = await apiClient.post<{ proposal: Proposal }>(`/proposals/${sessionId}/generate`, {
      type: 'final_proposal',
    })
    return data.proposal
  },

  getLatestFinal: async (sessionId: string): Promise<Proposal | null> => {
    try {
      const { data } = await apiClient.get<{ proposal: Proposal | null }>(`/proposals/session/${sessionId}/final`)
      return data.proposal
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) return null
      throw error
    }
  },

  getById: async (proposalId: string) => {
    const { data } = await apiClient.get(`/proposals/${proposalId}`)
    return data
  },

  export: async (proposalId: string, format: 'docx' | 'pdf') => {
    const response = await apiClient.post(
      `/proposals/${proposalId}/export`,
      { format },
      { responseType: 'blob' }
    )
    return response.data as Blob
  },
}
