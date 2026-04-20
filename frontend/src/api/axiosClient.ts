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
 *   Also maintains the connectionStore's backendUnreachable flag: any
 *   successful response (even 4xx/5xx) clears it; network-level errors
 *   (ERR_NETWORK / "Network Error") set it so the BackendUnreachableModal
 *   can show a blocking dialog.
 *
 * Main parts:
 *   - axiosClient: Axios instance with baseURL and Content-Type header.
 *   - Request interceptor: reads workspaceId from sessionStore and injects
 *     X-Workspace-ID header on every outbound request.
 *   - Response interceptor: bidirectionally updates useConnectionStore.
 */
import axios from 'axios'
import { useConnectionStore } from '../stores/connectionStore'
import { useSessionStore } from '../stores/sessionStore'

const axiosClient = axios.create({
  baseURL: 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
})

axiosClient.interceptors.request.use((config) => {
  const workspaceId = useSessionStore.getState().workspaceId || 'wks_default'
  config.headers['X-Workspace-ID'] = workspaceId
  return config
})

axiosClient.interceptors.response.use(
  (response) => {
    // Any HTTP response (2xx) proves the backend is reachable.
    useConnectionStore.getState().setBackendUnreachable(false)
    return response
  },
  (error) => {
    // Distinguish "backend down" (no response object) from "backend returned
    // an HTTP error" (response exists with 4xx/5xx).
    const isNetworkError =
      error.code === 'ERR_NETWORK' ||
      error.message === 'Network Error' ||
      !error.response
    if (isNetworkError) {
      useConnectionStore.getState().setBackendUnreachable(true)
    } else {
      // HTTP-level error means backend IS reachable — clear the flag.
      useConnectionStore.getState().setBackendUnreachable(false)
    }
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

export default axiosClient
