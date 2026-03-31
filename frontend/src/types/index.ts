export interface Document {
  doc_id: string
  doc_name: string
  doc_type: string
  fiscal_year: string
  chunk_count: number
  status: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'error'
  content: string
  intent?: string
  citations?: string[]
  timestamp: number
}

export interface KPIValue {
  value: string
  rawValue: number
  change?: string
  favorable?: boolean
}

export interface HealthStatus {
  status: string
  redis: boolean
  pinecone: boolean
  anthropic_key: boolean
  gemini_key: boolean
}
