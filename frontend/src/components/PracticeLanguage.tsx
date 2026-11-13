export type PracticeLanguageCode = 'en' | 'hinglish'
export default function PracticeLanguage({ value, disabled, onChange }: { value: PracticeLanguageCode; disabled: boolean; onChange: (value: PracticeLanguageCode) => void }) {
  return <label className="practice-language">Practice language<select aria-label="Practice language" disabled={disabled} value={value} onChange={event => onChange(event.target.value as PracticeLanguageCode)}><option value="en">English</option><option value="hinglish">Hinglish (Hindi + English)</option></select></label>
}
