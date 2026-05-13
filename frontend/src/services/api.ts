import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { ApiResponse } from '@/types/api'

class ApiClient {
  private client: AxiosInstance
  private baseURL: string

  constructor(baseURL: string = '/api') {
    this.baseURL = baseURL
    this.client = axios.create({
      baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        // Add auth token if available
        const token = localStorage.getItem('auth_token')
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        return config
      },
      (error) => {
        return Promise.reject(error)
      }
    )

    // Response interceptor
    this.client.interceptors.response.use(
      (response: AxiosResponse<ApiResponse>) => {
        // Handle API response format
        if (response.data && typeof response.data === 'object' && 'success' in response.data) {
          if (!response.data.success) {
            return Promise.reject(response.data.error)
          }
          return response.data.data
        }
        return response.data
      },
      (error) => {
        // Handle network errors
        if (error.response) {
          // Server responded with error
          const apiError = error.response.data?.error || {
            code: 'HTTP_ERROR',
            message: `HTTP ${error.response.status}: ${error.response.statusText}`,
          }
          return Promise.reject(apiError)
        } else if (error.request) {
          // Request made but no response
          return Promise.reject({
            code: 'NETWORK_ERROR',
            message: 'Network error. Please check your connection.',
          })
        } else {
          // Error setting up request
          return Promise.reject({
            code: 'REQUEST_ERROR',
            message: error.message,
          })
        }
      }
    )
  }

  // Generic HTTP methods
  async get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.client.get(url, config)
  }

  async post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return this.client.post(url, data, config)
  }

  async put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return this.client.put(url, data, config)
  }

  async delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.client.delete(url, config)
  }

  async patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return this.client.patch(url, data, config)
  }

  // Session endpoints
  async createSession(title?: string, description?: string, metadata?: Record<string, any>) {
    return this.post('/v1/sessions', { title, description, metadata })
  }

  async getSessions(page = 1, pageSize = 20) {
    return this.get(`/v1/sessions?page=${page}&page_size=${pageSize}`)
  }

  async getSession(sessionId: string) {
    return this.get(`/v1/sessions/${sessionId}`)
  }

  async updateSession(sessionId: string, updates: any) {
    return this.patch(`/v1/sessions/${sessionId}`, updates)
  }

  async deleteSession(sessionId: string) {
    return this.delete(`/v1/sessions/${sessionId}`)
  }

  // Chat endpoints
  async sendMessage(sessionId: string, message: string) {
    return this.post(`/v1/chat/${sessionId}/messages`, {
      role: 'user',
      content: message,
    })
  }

  async getMessages(sessionId: string, page = 1, pageSize = 50) {
    return this.get(`/v1/chat/${sessionId}/messages?page=${page}&page_size=${pageSize}`)
  }

  // Agent endpoints
  async getAgents() {
    return this.get('/v1/agents')
  }

  async getAgent(agentId: string) {
    return this.get(`/v1/agents/${agentId}`)
  }

  async updateAgent(agentId: string, updates: any) {
    return this.put(`/v1/agents/${agentId}`, updates)
  }

  // Health check
  async healthCheck() {
    return this.get('/health')
  }
}

// Create singleton instance
const apiClient = new ApiClient(import.meta.env.VITE_API_BASE_URL || '/api')

export default apiClient