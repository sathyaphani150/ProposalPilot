/**
 * ProposalPilot AI — API Client
 * Axios instance with interceptors for auth, error handling, and request IDs.
 */
import axios, { AxiosError, type AxiosInstance } from 'axios'

const DEV_BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://127.0.0.1:8124'
const BASE_URL = import.meta.env.DEV ? `${DEV_BACKEND_URL}/api/v1` : '/api/v1'

export const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ── Request interceptor ──────────────────────────────────────────────────
apiClient.interceptors.request.use((config) => {
  // Attach request ID for tracing
  config.headers['X-Request-ID'] = crypto.randomUUID()

  // Attach JWT if available
  const token = localStorage.getItem('pp_token')
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  }

  return config
})

// ── Response interceptor ─────────────────────────────────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<APIError>) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('pp_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// ── Type helpers ─────────────────────────────────────────────────────────
export interface APIError {
  error: string
  message: string
  detail?: unknown
  request_id?: string
}

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const axiosErr = error as AxiosError<APIError>
    return axiosErr.response?.data?.message ?? error.message
  }
  if (error instanceof Error) return error.message
  return 'An unexpected error occurred'
}
