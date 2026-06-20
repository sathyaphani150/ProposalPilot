import type { ReactNode } from 'react'
import { Calculator, FileText, Shield, UserRoundCog } from 'lucide-react'

import type { AgentName } from '@/types'

export const AGENT_COLOR_VAR: Record<AgentName, string> = {
  architect: 'var(--agent-architect)',
  cfo: 'var(--agent-cfo)',
  competitor: 'var(--agent-competitor)',
  proposal: 'var(--agent-proposal)',
}

export const AGENT_LABEL: Record<AgentName, string> = {
  architect: 'Tech Architect',
  cfo: 'CFO / Pricing',
  competitor: 'Competitor Strategist',
  proposal: 'Proposal Writer',
}

export const agentConfig: Array<{ key: AgentName; label: string; icon: ReactNode; color: string }> = [
  { key: 'architect', label: AGENT_LABEL.architect, icon: <UserRoundCog size={20} />, color: AGENT_COLOR_VAR.architect },
  { key: 'cfo', label: AGENT_LABEL.cfo, icon: <Calculator size={20} />, color: AGENT_COLOR_VAR.cfo },
  { key: 'competitor', label: AGENT_LABEL.competitor, icon: <Shield size={20} />, color: AGENT_COLOR_VAR.competitor },
  { key: 'proposal', label: AGENT_LABEL.proposal, icon: <FileText size={20} />, color: AGENT_COLOR_VAR.proposal },
]
