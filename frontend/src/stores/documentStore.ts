/**
 * documentStore.ts
 *
 * Zustand store managing the list of ingested documents and document
 * lifecycle operations (fetch, upload, delete).
 *
 * Role in project:
 *   Document feature state. Owned by LeftPanel (renders the doc list, upload
 *   dialog). fetchDocuments() is called once on mount from App.tsx to
 *   populate the list without redundant calls from individual panels.
 *
 * Main parts:
 *   - DocumentState: documents array, loading flag, uploadLoading flag, error.
 *   - fetchDocuments(): GET /documents/ and populates the store.
 *   - uploadDocument(): multipart POST /documents/upload with file, doc_type,
 *     and fiscal_year, then refetches the list.
 *   - deleteDocument(): DELETE /documents/{doc_id} then refetches the list.
 */
import { create } from 'zustand'
import axiosClient from '../api/axiosClient'
import { Document } from '../types'

interface DocumentState {
  documents: Document[]
  loading: boolean
  uploading: boolean
  fetchDocuments: () => Promise<void>
  uploadDocument: (file: File, docType: string, fiscalYear: string) => Promise<void>
  deleteDocument: (docId: string) => Promise<void>
}

export const useDocumentStore = create<DocumentState>((set, get) => ({
  documents: [],
  loading: false,
  uploading: false,

  fetchDocuments: async () => {
    set({ loading: true })
    try {
      const res = await axiosClient.get('/documents/')
      set({ documents: res.data, loading: false })
    } catch {
      set({ documents: [], loading: false })
    }
  },

  uploadDocument: async (file: File, docType: string, fiscalYear: string) => {
    set({ uploading: true })
    const formData = new FormData()
    formData.append('file', file)
    formData.append('doc_type', docType)
    formData.append('fiscal_year', fiscalYear)
    try {
      await axiosClient.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      await get().fetchDocuments()
    } finally {
      set({ uploading: false })
    }
  },

  deleteDocument: async (docId: string) => {
    await axiosClient.delete(`/documents/${docId}`)
    await get().fetchDocuments()
  },
}))
