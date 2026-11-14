import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuRadioGroup, DropdownMenuRadioItem } from './ui/dropdown-menu'
import Icon from './Icon'
import { practiceLanguages, practiceLanguage, type PracticeLanguageCode } from '../practiceLanguages'
export type { PracticeLanguageCode } from '../practiceLanguages'
export default function PracticeLanguage({ value, disabled, onChange }: { value: PracticeLanguageCode; disabled: boolean; onChange: (value: PracticeLanguageCode) => void }) {
  return <div className="practice-language"><span>Practice language</span><DropdownMenu><DropdownMenuTrigger className="practice-language-trigger" aria-label={`Practice language: ${practiceLanguage(value).label}`} disabled={disabled}>{practiceLanguage(value).label}<Icon name="chevron" size={14} className="rotate-90" /></DropdownMenuTrigger><DropdownMenuContent aria-label="Practice language"><DropdownMenuRadioGroup value={value} onValueChange={next => { if (typeof next === 'string' && next in practiceLanguages) onChange(next as PracticeLanguageCode) }}>{Object.entries(practiceLanguages).map(([code, item]) => <DropdownMenuRadioItem key={code} value={code}>{item.label}</DropdownMenuRadioItem>)}</DropdownMenuRadioGroup></DropdownMenuContent></DropdownMenu></div>
}
