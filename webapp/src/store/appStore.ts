import { create } from 'zustand'

type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error'

interface AppStore {
  project_id: string | null
  setProjectId: (id: string) => void
  connection: { state: ConnectionState; lastError?: string }
  setConnection: (s: ConnectionState, e?: string) => void
  ui: { toasts: { id: string; message: string }[] }
  pushToast: (message: string) => void
  popToast: (id: string) => void
}

export const useAppStore = create<AppStore>((set) => ({
  project_id: null,
  setProjectId: (id) => set({ project_id: id }),
  connection: { state: 'disconnected' },
  setConnection: (state, lastError) => set({ connection: { state, lastError } }),
  ui: { toasts: [] },
  pushToast: (message) => set((st) => ({ ui: { toasts: [...st.ui.toasts, { id: crypto.randomUUID(), message }] } })),
  popToast: (id) => set((st) => ({ ui: { toasts: st.ui.toasts.filter(t => t.id !== id) } })),
}))

