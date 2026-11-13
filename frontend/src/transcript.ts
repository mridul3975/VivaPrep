export function identifierSuggestion(answer: string, heard: string, identifier: string) {
  if (!heard) return answer
  const escaped = heard.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const phrase = new RegExp(`(^|[^\\p{L}\\p{N}_])${escaped}(?=$|[^\\p{L}\\p{N}_])`, 'u')
  return answer.replace(phrase, (_match, prefix: string) => prefix + identifier)
}
