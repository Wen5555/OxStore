export function getSafeInternalPath(value: unknown): string | undefined {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//') || value.includes('\\')) {
    return undefined
  }

  const target = new URL(value, window.location.origin)
  if (target.origin !== window.location.origin) return undefined
  return `${target.pathname}${target.search}${target.hash}`
}

export function getReturnPath(state: unknown, search: string, fallback: string) {
  const statePath = state && typeof state === 'object' && 'from' in state ? state.from : undefined
  const queryPath = new URLSearchParams(search).get('returnTo')
  return getSafeInternalPath(statePath) ?? getSafeInternalPath(queryPath) ?? fallback
}

export function consumeAuthRedirectMessage() {
  const text = sessionStorage.getItem('auth_redirect_message')
  if (text) sessionStorage.removeItem('auth_redirect_message')
  return text
}
