import assert from 'node:assert/strict'
import { identifierSuggestion } from '../src/transcript.ts'
const answer = 'is crime input 1 par True return karta hai, loop nahi rukta.'
assert.equal(identifierSuggestion(answer, 'is crime', 'is_prime'), 'is_prime input 1 par True return karta hai, loop nahi rukta.')
assert.equal(identifierSuggestion('is_prime returns False', 'prime', 'is_prime'), 'is_prime returns False')
assert.equal(identifierSuggestion('this crime is unrelated', 'is crime', 'is_prime'), 'this crime is unrelated')
assert.equal(identifierSuggestion('इस prime mein 2 hai', 'prime', 'is_prime'), 'इस is_prime mein 2 hai')
console.log('Explicit identifier edits preserve numbers, Boolean claims and negation; existing identifiers and embedded substrings are not corrupted.')
