export const KNOWLEDGE_ITEM_TYPE_OPTIONS = [
  { value: 'project', label: 'Project Profile', filterLabel: 'Projects' },
  { value: 'repo', label: 'Codebase Readme', filterLabel: 'Codebases' },
  { value: 'doc', label: 'General Guideline', filterLabel: 'Guidelines' },
  { value: 'case_study', label: 'Case Study', filterLabel: 'Case Studies' },
  { value: 'architecture', label: 'Architecture Sheet', filterLabel: 'Architectures' },
] as const

export const KNOWLEDGE_DOMAIN_OPTIONS = [
  { value: 'fintech', label: 'FinTech' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'ecommerce', label: 'E-Commerce' },
  { value: 'logistics', label: 'Logistics' },
  { value: 'aerospace', label: 'Aerospace' },
] as const
