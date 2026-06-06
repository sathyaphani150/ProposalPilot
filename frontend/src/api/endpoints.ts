/**
 * ProposalPilot AI — RFP API Functions
 */
import { apiClient } from './client'
import type { RFPSession, RFPAnalysis } from '@/types'

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
  ingest: async (file: File, metadata: Record<string, unknown>) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('metadata', JSON.stringify(metadata))
    const { data } = await apiClient.post('/knowledge/ingest', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  list: async () => {
    const { data } = await apiClient.get('/knowledge/items')
    return data
  },

  search: async (query: string, filters?: Record<string, string>) => {
    const { data } = await apiClient.get('/knowledge/search', {
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
}

export const proposalApi = {
  generate: async (sessionId: string, type: 'prep_pack' | 'final_proposal') => {
    const { data } = await apiClient.post(`/proposals/${sessionId}/generate`, { type })
    return data
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
