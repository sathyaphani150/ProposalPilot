import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  Search,
  Plus,
  Trash2,
  BookOpen,
  Database,
  Cpu,
  Tag,
  X,
  UploadCloud,
} from 'lucide-react'
import { knowledgeApi } from '@/api/endpoints'
import { getErrorMessage } from '@/api/client'
import { KNOWLEDGE_DOMAIN_OPTIONS, KNOWLEDGE_ITEM_TYPE_OPTIONS } from '@/config/knowledgeOptions'
import type { KnowledgeItem, KnowledgeItemType, KnowledgeSearchResult } from '@/types'

export function KnowledgeBase() {
  const [searchTerm, setSearchTerm] = useState('')
  const [filterDomain, setFilterDomain] = useState('')
  const [filterType, setFilterType] = useState('')
  
  const [isIngestOpen, setIsIngestOpen] = useState(false)
  const [selectedItem, setSelectedItem] = useState<KnowledgeItem | null>(null)

  // Ingest form state
  const [title, setTitle] = useState('')
  const [itemType, setItemType] = useState('project')
  const [domain, setDomain] = useState('')
  const [description, setDescription] = useState('')
  const [techStackInput, setTechStackInput] = useState('')
  const [tagsInput, setTagsInput] = useState('')
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)

  // ── Queries ──────────────────────────────────────────────────────────────
  
  // List all knowledge items
  const {
    data: listResponse,
    isLoading: isListLoading,
    refetch: refetchItems,
  } = useQuery({
    queryKey: ['knowledgeItems'],
    queryFn: () => knowledgeApi.list(),
  })

  // Search knowledge items if search term is provided
  const {
    data: searchResponse,
    isLoading: isSearchLoading,
  } = useQuery({
    queryKey: ['knowledgeSearch', searchTerm, filterDomain, filterType],
    queryFn: () => {
      const filters: Record<string, string> = {}
      if (filterDomain) filters.domain = filterDomain
      if (filterType) filters.item_type = filterType
      return knowledgeApi.search(searchTerm, filters)
    },
    enabled: searchTerm.trim().length > 0,
  })

  // ── Mutations ────────────────────────────────────────────────────────────
  
  // Ingest new knowledge item
  const { mutate: ingestItem, isPending: isIngesting } = useMutation({
    mutationFn: () => {
      const techStack = techStackInput
        ? techStackInput.split(',').map((t) => t.trim()).filter((t) => t.length > 0)
        : []
      const tags = tagsInput
        ? tagsInput.split(',').map((t) => t.trim()).filter((t) => t.length > 0)
        : []

      return knowledgeApi.ingest(uploadedFile, {
        item_type: itemType,
        title,
        description,
        domain,
        tech_stack: techStack,
        tags,
      })
    },
    onSuccess: () => {
      toast.success('Knowledge item added. background indexing started.')
      refetchItems()
      setIsIngestOpen(false)
      // Reset form
      setTitle('')
      setItemType('project')
      setDomain('')
      setDescription('')
      setTechStackInput('')
      setTagsInput('')
      setUploadedFile(null)
    },
    onError: (err) => {
      toast.error('Failed to ingest knowledge: ' + getErrorMessage(err))
    },
  })

  // Delete knowledge item
  const { mutate: deleteItem } = useMutation({
    mutationFn: (itemId: string) => knowledgeApi.delete(itemId),
    onSuccess: () => {
      toast.success('Knowledge item deleted.')
      refetchItems()
      if (selectedItem?.id) setSelectedItem(null)
    },
    onError: (err) => {
      toast.error('Failed to delete item: ' + getErrorMessage(err))
    },
  })

  // ── Handlers ─────────────────────────────────────────────────────────────
  
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setUploadedFile(e.target.files[0])
      if (!title) {
        // Auto-fill title with filename without extension
        const name = e.target.files[0].name.replace(/\.[^/.]+$/, "")
        setTitle(name)
      }
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!title) {
      toast.error('Please provide a title.')
      return
    }
    ingestItem()
  }

  const handleDelete = (itemId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (confirm('Are you sure you want to delete this knowledge item and its vector index?')) {
      deleteItem(itemId)
    }
  }

  const items = listResponse?.items || []
  const searchResults = searchResponse || []
  const hasSearch = searchTerm.trim().length > 0

  return (
    <div className="fade-in">
      {/* Header */}
      <div className="flex justify-between items-center" style={{ marginBottom: '2rem' }}>
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <BookOpen size={28} color="var(--color-primary-light)" />
            Internal Knowledge Base
          </h1>
          <p style={{ color: 'var(--color-text-secondary)', marginTop: '0.25rem' }}>
            Ingest and manage past projects, architectures, and guidelines for RFP context matching.
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setIsIngestOpen(true)}>
          <Plus size={16} />
          Ingest Knowledge
        </button>
      </div>

      {/* Main Layout Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: selectedItem ? '1.5fr 1fr' : '1fr', gap: '1.5rem', transition: 'all 0.3s ease' }}>
        
        {/* Left Side: Search + Items List */}
        <div className="flex flex-col gap-4">
          
          {/* Search bar & filter controls */}
          <div className="card flex gap-4 items-center flex-wrap" style={{ padding: '1rem' }}>
            <div className="relative flex-1" style={{ minWidth: '250px' }}>
              <Search
                size={18}
                color="var(--color-text-muted)"
                style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }}
              />
              <input
                type="text"
                className="input"
                placeholder="Search knowledge by keywords or technology stack..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{ paddingLeft: '2.5rem' }}
              />
              {hasSearch && (
                <button
                  onClick={() => setSearchTerm('')}
                  style={{
                    position: 'absolute',
                    right: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    color: 'var(--color-text-muted)',
                    cursor: 'pointer',
                  }}
                >
                  <X size={16} />
                </button>
              )}
            </div>

            <div className="flex gap-2">
              <select
                className="select"
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                style={{ width: '150px' }}
              >
                <option value="">All Types</option>
                {KNOWLEDGE_ITEM_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.filterLabel}</option>
                ))}
              </select>

              <select
                className="select"
                value={filterDomain}
                onChange={(e) => setFilterDomain(e.target.value)}
                style={{ width: '150px' }}
              >
                <option value="">All Domains</option>
                {KNOWLEDGE_DOMAIN_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Ingestion status bar */}
          {isListLoading ? (
            <div className="flex justify-center items-center" style={{ minHeight: '200px' }}>
              <div className="spinner" style={{ width: 32, height: 32 }} />
            </div>
          ) : (
            <div>
              {/* Display Search Results vs Listing All */}
              {hasSearch ? (
                <div>
                  <h3 style={{ marginBottom: '1rem', color: 'var(--color-primary-light)' }}>
                    Search Results ({searchResults.length})
                  </h3>
                  {isSearchLoading ? (
                    <div className="flex justify-center items-center" style={{ minHeight: '100px' }}>
                      <div className="spinner" />
                    </div>
                  ) : searchResults.length === 0 ? (
                    <div className="card text-center" style={{ padding: '3rem' }}>
                      <p style={{ color: 'var(--color-text-muted)' }}>No matches found for "{searchTerm}". Try general terms.</p>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3">
                      {searchResults.map((result: KnowledgeSearchResult) => (
                        <div
                          key={result.point_id}
                          className="card fade-in"
                          style={{ cursor: 'pointer', padding: '1.25rem' }}
                          onClick={() => {
                            // Find corresponding item details from listing
                            const item = items.find((i: KnowledgeItem) => i.id === result.doc_id)
                            if (item) {
                              setSelectedItem(item)
                            } else {
                              // Build a partial KnowledgeItem if not fully in memory
                              setSelectedItem({
                                id: result.doc_id,
                                title: result.title || 'Result details',
                                item_type: (result.item_type || 'project') as KnowledgeItemType,
                                domain: result.domain || null,
                                description: result.text,
                                tech_stack: result.tech_stack || [],
                                tags: result.tags || [],
                                chunk_count: 1,
                                is_active: true,
                                created_at: new Date().toISOString(),
                              })
                            }
                          }}
                        >
                          <div className="flex justify-between items-start" style={{ marginBottom: '0.5rem' }}>
                            <div>
                              <span
                                className="badge badge-uploaded"
                                style={{ marginRight: '0.5rem', textTransform: 'uppercase', fontSize: '0.65rem' }}
                              >
                                {result.item_type || 'project'}
                              </span>
                              <span style={{ fontWeight: 600, fontSize: '1.05rem' }}>{result.title || 'Internal Knowledge'}</span>
                            </div>
                            <span style={{ fontSize: '0.8rem', color: 'var(--color-primary-light)', fontWeight: 650 }}>
                              Match: {Math.round(result.score * 100)}%
                            </span>
                          </div>
                          <p
                            className="text-secondary text-sm"
                            style={{
                              lineHeight: 1.5,
                              display: '-webkit-box',
                              WebkitLineClamp: 3,
                              WebkitBoxOrient: 'vertical',
                              overflow: 'hidden',
                              marginBottom: '0.75rem',
                              fontFamily: 'var(--font-sans)',
                            }}
                          >
                            {result.text}
                          </p>
                          <div className="flex justify-between items-center">
                            <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
                              {result.tech_stack?.slice(0, 3).map((tech: string) => (
                                <span key={tech} className="badge" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--color-border)' }}>
                                  {tech}
                                </span>
                              ))}
                            </div>
                            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                              Domain: {result.domain || 'N/A'}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  <h3 style={{ marginBottom: '1rem' }}>Ingested Documents ({items.length})</h3>
                  {items.length === 0 ? (
                    <div className="card text-center" style={{ padding: '4rem' }}>
                      <Database size={48} color="var(--color-text-muted)" style={{ margin: '0 auto 1rem auto' }} />
                      <h4 style={{ marginBottom: '0.5rem' }}>Knowledge Base is Empty</h4>
                      <p style={{ color: 'var(--color-text-secondary)', marginBottom: '1.5rem', maxWidth: '400px', margin: '0 auto 1.5rem auto' }}>
                        Seed past project sheets, design architectures, or guidelines so ProposalPilot can write accurate responses.
                      </p>
                      <button className="btn btn-secondary" onClick={() => setIsIngestOpen(true)}>
                        <Plus size={16} />
                        Add First Document
                      </button>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3">
                      {items.map((item: KnowledgeItem) => (
                        <div
                          key={item.id}
                          className={`card fade-in ${selectedItem?.id === item.id ? 'agent-active' : ''}`}
                          style={{ cursor: 'pointer', padding: '1.25rem' }}
                          onClick={() => setSelectedItem(item)}
                        >
                          <div className="flex justify-between items-start">
                            <div>
                              <div className="flex items-center gap-2" style={{ marginBottom: '0.5rem' }}>
                                <span className="badge badge-uploaded" style={{ textTransform: 'uppercase', fontSize: '0.65rem' }}>
                                  {item.item_type}
                                </span>
                                {item.domain && (
                                  <span className="badge badge-analyzed" style={{ textTransform: 'uppercase', fontSize: '0.65rem' }}>
                                    {item.domain}
                                  </span>
                                )}
                              </div>
                              <h4 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                                {item.title}
                              </h4>
                            </div>
                            <div className="flex items-center gap-2">
                              <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                                {item.chunk_count} {item.chunk_count === 1 ? 'chunk' : 'chunks'}
                              </span>
                              <button
                                className="btn-ghost"
                                style={{ padding: '0.25rem', borderRadius: '4px', color: 'var(--color-error)' }}
                                onClick={(e) => handleDelete(item.id, e)}
                              >
                                <Trash2 size={15} />
                              </button>
                            </div>
                          </div>

                          {item.description && (
                            <p
                              style={{
                                fontSize: '0.875rem',
                                color: 'var(--color-text-secondary)',
                                marginTop: '0.75rem',
                                display: '-webkit-box',
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: 'vertical',
                                overflow: 'hidden',
                              }}
                            >
                              {item.description}
                            </p>
                          )}

                          {item.tech_stack && item.tech_stack.length > 0 && (
                            <div className="flex gap-2" style={{ flexWrap: 'wrap', marginTop: '1rem' }}>
                              {item.tech_stack.map((tech) => (
                                <span key={tech} className="badge text-xs" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--color-border)' }}>
                                  {tech}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Side: Selected Item Details Panel */}
        {selectedItem && (
          <div className="flex flex-col gap-4 fade-in">
            <div className="card-elevated" style={{ padding: '1.5rem', position: 'sticky', top: '80px' }}>
              <div className="flex justify-between items-start" style={{ marginBottom: '1.5rem' }}>
                <h3>Document Details</h3>
                <button
                  className="btn btn-ghost btn-icon"
                  style={{ padding: '0.25rem' }}
                  onClick={() => setSelectedItem(null)}
                >
                  <X size={18} />
                </button>
              </div>

              <div className="flex flex-col gap-4">
                <div>
                  <label className="form-label" style={{ fontSize: '0.75rem', textTransform: 'uppercase' }}>
                    Title
                  </label>
                  <div style={{ fontSize: '1.2rem', fontWeight: 650, color: 'var(--color-text-primary)' }}>
                    {selectedItem.title}
                  </div>
                </div>

                <div className="grid-2">
                  <div>
                    <label className="form-label" style={{ fontSize: '0.75rem', textTransform: 'uppercase' }}>
                      Type
                    </label>
                    <span className="badge badge-uploaded" style={{ textTransform: 'uppercase', fontSize: '0.7rem' }}>
                      {selectedItem.item_type}
                    </span>
                  </div>
                  <div>
                    <label className="form-label" style={{ fontSize: '0.75rem', textTransform: 'uppercase' }}>
                      Domain
                    </label>
                    <span className="badge badge-analyzed" style={{ textTransform: 'uppercase', fontSize: '0.7rem' }}>
                      {selectedItem.domain || 'N/A'}
                    </span>
                  </div>
                </div>

                {selectedItem.tech_stack && selectedItem.tech_stack.length > 0 && (
                  <div>
                    <label className="form-label" style={{ fontSize: '0.75rem', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      <Cpu size={12} />
                      Technology Stack
                    </label>
                    <div className="flex gap-2" style={{ flexWrap: 'wrap', marginTop: '0.25rem' }}>
                      {selectedItem.tech_stack.map((t) => (
                        <span key={t} className="badge" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--color-border)' }}>
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {selectedItem.tags && selectedItem.tags.length > 0 && (
                  <div>
                    <label className="form-label" style={{ fontSize: '0.75rem', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      <Tag size={12} />
                      Tags
                    </label>
                    <div className="flex gap-2" style={{ flexWrap: 'wrap', marginTop: '0.25rem' }}>
                      {selectedItem.tags.map((t) => (
                        <span key={t} className="badge" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--color-border)', borderRadius: '4px', fontSize: '0.7rem' }}>
                          #{t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div className="divider" style={{ margin: '0.5rem 0' }} />

                <div>
                  <label className="form-label" style={{ fontSize: '0.75rem', textTransform: 'uppercase' }}>
                    Content / Description
                  </label>
                  <p
                    style={{
                      fontSize: '0.9rem',
                      lineHeight: 1.6,
                      color: 'var(--color-text-secondary)',
                      whiteSpace: 'pre-wrap',
                      maxHeight: '300px',
                      overflowY: 'auto',
                      paddingRight: '0.5rem',
                    }}
                  >
                    {selectedItem.description || 'No description provided.'}
                  </p>
                </div>

                <div className="flex gap-2 justify-end" style={{ marginTop: '1rem' }}>
                  <button
                    className="btn btn-danger btn-sm"
                    onClick={(e) => handleDelete(selectedItem.id, e)}
                  >
                    Delete Item
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Slide-over Overlay Panel: Ingest Knowledge Form */}
      {isIngestOpen && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            bottom: 0,
            left: 0,
            right: 0,
            background: 'rgba(0,0,0,0.65)',
            backdropFilter: 'blur(4px)',
            zIndex: 1000,
            display: 'flex',
            justifyContent: 'flex-end',
          }}
          onClick={() => setIsIngestOpen(false)}
        >
          <div
            className="fade-in"
            style={{
              width: '100%',
              maxWidth: '550px',
              background: 'var(--color-bg-card)',
              borderLeft: '1px solid var(--color-border)',
              padding: '2rem',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-center" style={{ marginBottom: '2rem' }}>
              <h2>Ingest Knowledge</h2>
              <button
                className="btn btn-ghost btn-icon"
                style={{ padding: '0.25rem' }}
                onClick={() => setIsIngestOpen(false)}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="flex flex-col gap-5">
              {/* File Upload Zone */}
              <div className="form-group">
                <span className="form-label">Upload Reference Document (Optional)</span>
                <div
                  className="dropzone"
                  style={{ padding: '1.5rem', borderStyle: 'dashed' }}
                  onClick={() => document.getElementById('kb-file-upload')?.click()}
                >
                  <UploadCloud size={32} color="var(--color-primary-light)" style={{ margin: '0 auto 0.5rem auto' }} />
                  <p style={{ fontSize: '0.85rem', marginBottom: '0.25rem' }}>
                    {uploadedFile ? uploadedFile.name : 'Drag & drop file or click to browse'}
                  </p>
                  <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                    Supports PDF, DOCX, TXT, MD up to 20MB
                  </span>
                  <input
                    id="kb-file-upload"
                    type="file"
                    style={{ display: 'none' }}
                    accept=".pdf,.docx,.txt,.md"
                    onChange={handleFileChange}
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Title *</label>
                <input
                  type="text"
                  className="input"
                  placeholder="e.g. HealthLink Integration Architecture Spec"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                />
              </div>

              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">Item Type</label>
                  <select
                    className="select"
                    value={itemType}
                    onChange={(e) => setItemType(e.target.value)}
                  >
                    {KNOWLEDGE_ITEM_TYPE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Domain Focus</label>
                  <select
                    className="select"
                    value={domain}
                    onChange={(e) => setDomain(e.target.value)}
                  >
                    <option value="">No Domain</option>
                    {KNOWLEDGE_DOMAIN_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Tech Stack (comma-separated tags)</label>
                <input
                  type="text"
                  className="input"
                  placeholder="e.g. React, Node.js, Python, PostgreSQL, AWS"
                  value={techStackInput}
                  onChange={(e) => setTechStackInput(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Custom Tags (comma-separated)</label>
                <input
                  type="text"
                  className="input"
                  placeholder="e.g. HIPAA, PCI-DSS, RAG, WebSockets"
                  value={tagsInput}
                  onChange={(e) => setTagsInput(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Description / Core Summary</label>
                <textarea
                  className="textarea"
                  placeholder="Summarize the core details of this project, architecture assumptions, or guidelines. This summary will be matched via vector index."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  style={{ minHeight: '120px' }}
                />
              </div>

              <div className="flex gap-3 justify-end" style={{ marginTop: '1.5rem' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsIngestOpen(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={isIngesting}
                >
                  {isIngesting ? (
                    <>
                      <div className="spinner" style={{ width: 14, height: 14 }} />
                      Ingesting...
                    </>
                  ) : (
                    'Start Ingestion'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
