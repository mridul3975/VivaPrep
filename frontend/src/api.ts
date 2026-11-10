export async function apiJson<T>(response: Response): Promise<T> {
  let body
  try { body = await response.json() } catch { throw new Error('The server returned an unreadable response. Please retry.') }
  if (!response.ok) throw new Error(typeof body?.error === 'string' ? body.error : 'The request failed. Please retry.')
  return body as T
}
