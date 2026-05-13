export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  error?: {
    code: string
    message: string
    details?: any
  }
  timestamp: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface HealthCheckResponse {
  status: 'healthy' | 'unhealthy'
  components: {
    database: boolean
    redis: boolean
    milvus: boolean
    llm_providers: Record<string, boolean>
  }
  timestamp: string
  version: string
}