import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Dashboard } from '@/pages/Dashboard'
import { NewRFP } from '@/pages/NewRFP'
import { RFPAnalysis } from '@/pages/RFPAnalysis'
import { WarRoom } from '@/pages/WarRoom'
import { ProposalEditor } from '@/pages/ProposalEditor'
import { KnowledgeBase } from '@/pages/KnowledgeBase'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="rfp/new" element={<NewRFP />} />
          <Route path="rfp/:sessionId/analysis" element={<RFPAnalysis />} />
          <Route path="rfp/:sessionId/war-room" element={<WarRoom />} />
          <Route path="rfp/:sessionId/proposal" element={<ProposalEditor />} />
          <Route path="knowledge" element={<KnowledgeBase />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
