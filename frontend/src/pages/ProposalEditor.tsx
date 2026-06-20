import { useNavigate } from 'react-router-dom'
import { FilePenLine, ArrowLeft } from 'lucide-react'

export function ProposalEditor() {
  const navigate = useNavigate()

  return (
    <div className="panel panel--raised empty-state">
      <div className="icon-chip" style={{ width: 58, height: 58 }}>
        <FilePenLine size={28} />
      </div>
      <div>
        <h1 className="mb-2">Proposal Editor</h1>
        <p className="text-muted max-readable">
          Final proposal editing is not available in this demo build yet. Complete analysis and War Room review first, then return here when proposal generation is enabled.
        </p>
      </div>
      <button className="btn btn-secondary" onClick={() => navigate('/dashboard')}>
        <ArrowLeft size={16} />
        Back to Dashboard
      </button>
    </div>
  )
}
