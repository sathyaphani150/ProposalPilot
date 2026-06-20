import { useEffect, useRef, useState } from 'react'
import type { AgentName, AgentStatus } from '@/types'

type AgentEvent = { agent?: string; type: string; content?: unknown; error?: string }

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
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/war-room/${warRoomId}`)
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
