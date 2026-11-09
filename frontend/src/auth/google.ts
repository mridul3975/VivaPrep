interface GoogleIdentity {
  initialize: (options: {
    client_id: string
    nonce: string
    auto_select: boolean
    callback: (response: { credential: string }) => void
  }) => void
  renderButton: (
    container: HTMLElement,
    options: { theme: string; size: string; shape: string; width: number },
  ) => void
  disableAutoSelect: () => void
}

declare global {
  interface Window {
    google?: { accounts: { id: GoogleIdentity } }
  }
}

let loading: Promise<GoogleIdentity> | null = null

export function loadGoogleIdentity(): Promise<GoogleIdentity> {
  if (window.google?.accounts.id)
    return Promise.resolve(window.google.accounts.id)
  if (loading) return loading
  loading = new Promise<GoogleIdentity>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    const fail = () => {
      window.clearTimeout(timeout)
      script.remove()
      loading = null
      reject(
        new Error(
          'Google sign-in could not load. Check your connection and retry.',
        ),
      )
    }
    const timeout = window.setTimeout(fail, 12_000)
    script.onerror = fail
    script.onload = () => {
      window.clearTimeout(timeout)
      if (window.google?.accounts.id) resolve(window.google.accounts.id)
      else fail()
    }
    document.head.append(script)
  })
  return loading
}
