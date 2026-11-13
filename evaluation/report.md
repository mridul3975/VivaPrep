# RepoViva evaluation candidate v1

Provisional; independent human review pending

40 planned cases: 16 assessment, 12 repair, 8 speech, 4 reliability. Human-approved: 0/40; disputed: 0.

| Area | RepoViva | Same-model general assistant |
| --- | --- | --- |
| assessment label agreement with draft expectations | 4/16 (4 outputs; 12 unavailable) | 9/16 (9 outputs; 7 unavailable) |
| repairs label agreement with draft expectations | 12/12 (12 outputs; 0 unavailable) | 12/12 (12 outputs; 0 unavailable) |
| Assessment exact point agreement | 4/16 | 9/16 |

Actual browser repair test agreement: 12/12. Reliability checks: 4/4.
Synthetic speech: 8/8 completed; raw word edits 16/136; WER 0.1176.

These are provisional observations against assistant-authored expectations, not human-reviewed benchmark accuracy.
The baseline uses the same Groq gpt-oss-120b model and same source/requirements. This is not a ChatGPT product comparison.
Sources and labels were frozen before model calls. Development examples in checks/ are excluded. No product tuning was performed against these results.
Four assessment source families and four repair families are correlated cases; the sample is small and does not establish population performance.
Speech is a single stock synthetic voice. Raw WER includes script and number-format differences; missing-expression checks are lexical heuristics, not semantic error rates.
Human listening is pending. Proposed corrections are intended script spellings; no learner corrections have been collected.
Reliability uses local PostgreSQL and injected faults except the live silence call. It does not establish deployed uptime.

Assessment comparison is inconclusive: Groq HTTP 429 errors withheld 12 RepoViva verdicts and 7 baseline verdicts. Do not interpret differing availability as an assessment-accuracy ranking. Keep this run and use a separately named, more slowly paced replication.

## Incorrect acceptances, rejections and unavailable verdicts

- assessment/repoviva: incorrect acceptances [] / 12 negatives; incorrect rejections [] / 4 positives; positive cases without verdict ['A05', 'A09', 'A13'].
- assessment/repoviva: unavailable case IDs ['A04', 'A05', 'A06', 'A08', 'A09', 'A10', 'A11', 'A12', 'A13', 'A14', 'A15', 'A16']. Unavailable cases are not successful judgments, even when no incorrect acceptance is observed.
- assessment/baseline: incorrect acceptances [] / 12 negatives; incorrect rejections [] / 4 positives; positive cases without verdict ['A13'].
- assessment/baseline: unavailable case IDs ['A04', 'A06', 'A08', 'A10', 'A12', 'A13', 'A16']. Unavailable cases are not successful judgments, even when no incorrect acceptance is observed.
- repairs/repoviva: incorrect acceptances [] / 8 negatives; incorrect rejections [] / 4 positives; positive cases without verdict [].
- repairs/repoviva: unavailable case IDs []. Unavailable cases are not successful judgments, even when no incorrect acceptance is observed.
- repairs/baseline: incorrect acceptances [] / 8 negatives; incorrect rejections [] / 4 positives; positive cases without verdict [].
- repairs/baseline: unavailable case IDs []. Unavailable cases are not successful judgments, even when no incorrect acceptance is observed.
