import { useEffect, useRef, useState } from 'react'

type AgentEvent = { agent?: string; type: string; content?: unknown; error?: string }

export function useWarRoom(sessionId: string | undefined) {
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [agentStatus, setAgentStatus] = useState<Record<string, 'pending' | 'done'>>({})
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!sessionId) return
    setEvents([])
    setAgentStatus({})
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/war-room/${sessionId}`)
    wsRef.current = ws

    ws.onmessage = (event) => {
      const data: AgentEvent = JSON.parse(event.data)
      setEvents((prev) => [...prev, data])
      if (data.agent) {
        setAgentStatus((prev) => ({ ...prev, [data.agent as string]: 'done' }))
      }
    }

    ws.onerror = () => {
      setEvents((prev) => [...prev, { type: 'error', error: 'WebSocket error' }])
    }

    return () => ws.close()
  }, [sessionId])

  return { events, agentStatus, wsRef }
}
