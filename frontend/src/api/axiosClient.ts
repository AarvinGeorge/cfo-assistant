/**
 * axiosClient.ts
 *
 * Pre-configured Axios instance used for all REST API calls to the FastAPI
 * backend.
 *
 * Role in project:
 *   Shared HTTP client. Imported by every Zustand store that needs to make
 *   API requests. Sets baseURL to http://localhost:8000 and default headers.
 *   Note: SSE streaming uses native fetch, not this client, because Axios
 *   does not support streaming responses.
 *
 * Main parts:
 *   - api: Axios instance with baseURL, Content-Type header, and 30s timeout.
 */
import axios from 'axios'

const axiosClient = axios.create({
  baseURL: 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
})

axiosClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

export default axiosClient
