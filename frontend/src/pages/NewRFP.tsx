import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { useDropzone, type FileRejection } from 'react-dropzone'
import toast from 'react-hot-toast'
import { Upload, X, CheckCircle, AlertCircle } from 'lucide-react'
import { rfpApi } from '@/api/endpoints'
import { getErrorMessage } from '@/api/client'

const MAX_SIZE = 20 * 1024 * 1024 // 20MB

export function NewRFP() {
  const navigate = useNavigate()
  const [file, setFile] = useState<File | null>(null)
  const [clientName, setClientName] = useState('')
  const [title, setTitle] = useState('')
  const [fileError, setFileError] = useState<string | null>(null)

  const { mutate: uploadRFP, isPending } = useMutation({
    mutationFn: () => rfpApi.upload(file!, { clientName, title }),
    onSuccess: (session) => {
      toast.success('RFP uploaded successfully!')
      navigate(`/rfp/${session.id}/analysis`)
    },
    onError: (error) => {
      toast.error(getErrorMessage(error))
    },
  })

  const onDrop = useCallback((accepted: File[], rejected: FileRejection[]) => {
    setFileError(null)
    if (rejected.length > 0) {
      const err = rejected[0].errors[0]
      setFileError(err.code === 'file-too-large'
        ? 'File exceeds 20MB limit'
        : 'Invalid file type. Allowed: PDF, DOCX, TXT, MD')
      return
    }
    if (accepted.length > 0) {
      const f = accepted[0]
      setFile(f)
      if (!title) setTitle(f.name.replace(/\.[^.]+$/, ''))
    }
  }, [title])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md'],
    },
    maxSize: MAX_SIZE,
    multiple: false,
  })

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  }

  const canSubmit = !!file && !isPending

  return (
    <div className="content-stack" style={{ maxWidth: 680, margin: '0 auto' }}>
      <div>
        <h1 className="mb-2">Upload RFP Document</h1>
        <p className="text-muted">
          Upload a client RFP, requirements brief, or SOW. Our AI will extract key insights
          and prepare your prospect strategy.
        </p>
      </div>

      {/* Drop Zone */}
      <div
        {...getRootProps()}
        className={`dropzone${isDragActive ? ' drag-active' : ''}`}
        style={{ marginBottom: '1.5rem' }}
      >
        <input {...getInputProps()} />

        {file ? (
          <div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '1rem',
                padding: '1.25rem',
                background: 'rgba(16, 185, 129, 0.08)',
                borderRadius: 'var(--radius-lg)',
                border: '1px solid rgba(16, 185, 129, 0.2)',
                marginBottom: '1rem',
              }}
            >
              <CheckCircle size={24} color="var(--color-success)" />
              <div style={{ flex: 1, textAlign: 'left' }}>
                <div style={{ fontWeight: 600, marginBottom: '0.2rem' }}>{file.name}</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                  {formatSize(file.size)}
                </div>
              </div>
              <button
                className="btn btn-icon btn-ghost"
                aria-label="Remove selected file"
                onClick={(e) => { e.stopPropagation(); setFile(null); setTitle('') }}
              >
                <X size={18} />
              </button>
            </div>
            <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
              Click or drag to replace
            </p>
          </div>
        ) : (
          <>
            <Upload size={42} className="dropzone-icon" />
            <h3 style={{ marginBottom: '0.5rem' }}>
              {isDragActive ? 'Drop your RFP here' : 'Drag & drop your RFP'}
            </h3>
            <p style={{ color: 'var(--color-text-muted)', marginBottom: '1.5rem' }}>
              or click to browse files
            </p>
            <div className="flex items-center justify-center gap-2" style={{ flexWrap: 'wrap' }}>
              {['PDF', 'DOCX', 'TXT', 'MD'].map((ext) => (
                <span key={ext} className="badge badge-analyzed">{ext}</span>
              ))}
            </div>
            <p style={{ marginTop: '1rem', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
              Maximum 20MB
            </p>
          </>
        )}
      </div>

      {fileError && (
        <div className="panel flex items-center gap-2" style={{ color: 'var(--color-error)', borderColor: 'rgba(255, 107, 107, 0.28)' }}>
          <AlertCircle size={16} />
          {fileError}
        </div>
      )}

      {/* Metadata */}
      <div className="panel panel--raised">
        <h3 style={{ marginBottom: '1.25rem', fontSize: '1rem' }}>RFP Details</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="form-group">
            <label className="form-label">RFP Title *</label>
            <input
              className="input"
              placeholder="e.g., Healthcare Patient Portal RFP — Acme Corp"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Client / Company Name</label>
            <input
              className="input"
              placeholder="e.g., Acme Corporation"
              value={clientName}
              onChange={(e) => setClientName(e.target.value)}
            />
          </div>
        </div>
      </div>

      {/* Submit */}
      <div className="flex items-center gap-3" style={{ justifyContent: 'flex-end' }}>
        <button
          className="btn btn-secondary"
          onClick={() => navigate('/dashboard')}
          disabled={isPending}
        >
          Cancel
        </button>
        <button
          className="btn btn-primary btn-lg"
          onClick={() => uploadRFP()}
          disabled={!canSubmit}
        >
          {isPending ? (
            <>
              <div className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
              Uploading…
            </>
          ) : (
            <>
              <Upload size={18} />
              Upload & Analyze
            </>
          )}
        </button>
      </div>
    </div>
  )
}
