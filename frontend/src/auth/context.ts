import { createContext, useContext } from 'react'

export interface Student {
  id: string
  name: string
  email: string
}

export interface AuthSession {
  user: Student | null
  expires_at: number | null
  expires_in_seconds?: number | null
  csrf_token: string
  nonce: string
  google_client_id: string | null
  storage_mode?: 'postgresql' | 'memory'
}

export interface AuthContextValue {
  user: Student
  storageMode: 'postgresql' | 'memory'
  apiFetch: (path: string, init?: RequestInit) => Promise<Response>
  signOut: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth() {
  const auth = useContext(AuthContext)
  if (!auth)
    throw new Error('The study workspace requires a signed-in session.')
  return auth
}
