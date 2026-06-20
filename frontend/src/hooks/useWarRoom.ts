import { useEffect, useRef, useState } from 'react'
import type { AgentName, AgentStatus } from '@/types'

type AgentEvent = { agent?: string; type: string; content?: unknown; error?: string }

function getWarRoomWebSocketUrl(warRoomId: string) {
  const configuredUrl = import.meta.env.VITE_WS_BASE_URL || import.meta.env.VITE_API_BASE_URL
  if (configuredUrl) {
    const baseUrl = configuredUrl
      .replace(/^http:/, 'ws:')
      .replace(/^https:/, 'wss:')
      .replace(/\/api\/v1\/?$/, '')
      .replace(/\/$/, '')
    return `${baseUrl}/ws/war-room/${warRoomId}`
  }

  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${protocol}://${window.location.host}/ws/war-room/${warRoomId}`
}

export function useWarRoom(warRoomId: string | undefined) {
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [agentStatus, setAgentStatus] = useState<Partial<Record<AgentName, AgentStatus>>>({})
  const wsRef = useRef<WebSocket | null>(null)
  const [prevWarRoomId, setPrevWarRoomId] = useState<string | undefined>(warRoomId)

  if (warRoomId !== prevWarRoomId) {
    setPrevWarRoomId(warRoomId)
    setEvents([])
    setAgentStatus({})
  }

  useEffect(() => {
    if (!warRoomId) return
    const ws = new WebSocket(getWarRoomWebSocketUrl(warRoomId))
    wsRef.current = ws

    ws.onmessage = (event) => {
      const data: AgentEvent = JSON.parse(event.data)
      setEvents((prev) => [...prev, data])
      if (data.agent) {
        const nextStatus: AgentStatus =
          data.type === 'start' ? 'thinking' :
          data.type === 'token' ? 'writing' :
          data.type === 'complete' ? 'done' :
          data.type === 'error' ? 'error' :
          data.type === 'human_required' ? 'idle' :
          'idle'
        setAgentStatus((prev) => ({ ...prev, [data.agent as AgentName]: nextStatus }))
      }
    }

    ws.onerror = () => {
      setEvents((prev) => [...prev, { type: 'error', error: 'WebSocket error' }])
    }

    return () => ws.close()
  }, [warRoomId])

  return { events, agentStatus, wsRef }
}
