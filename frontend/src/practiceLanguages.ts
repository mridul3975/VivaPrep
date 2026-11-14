export const practiceLanguages = {
  en: { label: 'English', lang: 'en' }, hinglish: { label: 'Hinglish (Hindi + English)', lang: 'hi-Latn' },
  hi: { label: 'Hindi · हिन्दी', lang: 'hi' }, ta: { label: 'Tamil · தமிழ்', lang: 'ta' },
  bn: { label: 'Bengali · বাংলা', lang: 'bn' }, te: { label: 'Telugu · తెలుగు', lang: 'te' },
  mr: { label: 'Marathi · मराठी', lang: 'mr' }, kn: { label: 'Kannada · ಕನ್ನಡ', lang: 'kn' },
} as const
export type PracticeLanguageCode = keyof typeof practiceLanguages
export function practiceLanguage(value: PracticeLanguageCode = 'en') { return practiceLanguages[value] ?? practiceLanguages.en }
