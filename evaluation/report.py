"""Render a public, static report from retained observations; no provider requests."""
import csv
import hashlib
import html
import json
from pathlib import Path
from evaluation.metrics import agreement, errors
from evaluation.verify import frozen_bytes

HERE = Path(__file__).resolve().parent
escape = lambda value: html.escape(str(value))


def read(name, default=None):
    path = HERE / name
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def ratio(value):
    return f"{value['agreed']}/{value['planned']} ({value['completed']} outputs; {value['errors_or_missing']} unavailable)"


def main():
    data = read('dataset.json')
    results = read('results.json', {'sections': {}})
    browser = read('browser-tests.json', {'results': []})
    cases = [case for area in ('assessment', 'repairs', 'speech', 'reliability') for case in data[area]]
    review_file = HERE / 'review.csv'
    dataset_hash = hashlib.sha256((HERE / 'dataset.json').read_bytes()).hexdigest()
    if not review_file.exists():
        with review_file.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=['id', 'dataset_sha256', 'decision', 'reviewer', 'reviewed_at', 'notes'])
            writer.writeheader()
            for case in cases:
                writer.writerow({'id': case['id'], 'dataset_sha256': dataset_hash, 'decision': 'pending'})
    with review_file.open(encoding='utf-8', newline='') as stream:
        reviews = list(csv.DictReader(stream))
    if len(reviews) != len(cases) or {r['id'] for r in reviews} != {c['id'] for c in cases} or any(r['dataset_sha256'] != dataset_hash for r in reviews):
        raise ValueError('Review sheet does not match this frozen dataset')
    approved = sum(r['decision'] == 'approve' and bool(r['reviewer'].strip()) and bool(r['reviewed_at'].strip()) for r in reviews)
    disputed = sum(r['decision'] == 'dispute' for r in reviews)
    sections = results['sections']
    # Planned cases are always included, even if a run was interrupted before an output.
    planned = {}
    for area in ('assessment', 'repairs'):
        by_id = {row['id']: row for row in sections.get(area, [])}
        planned[area] = [{**by_id.get(case['id'], {}), 'id': case['id'], 'expected': case.get('expected_label', case.get('expected')), 'expected_points': case.get('expected_points')} for case in data[area]]
    metrics = {}
    for area, positive in [('assessment', 'supported'), ('repairs', 'correct')]:
        metrics[area] = {system: {**agreement(planned[area], system, 'expected', 'label'), **errors(planned[area], system, positive)} for system in ('repoviva', 'baseline')}
    for system in ('repoviva', 'baseline'):
        metrics['assessment'][system]['exact_point_agreement'] = sum(r.get(system, {}).get('status') == 'ok' and r[system]['points'] == r['expected_points'] for r in planned['assessment'])
    for area in ('assessment', 'repairs'):
        for system in ('repoviva', 'baseline'):
            metrics[area][system]['unavailable_cases'] = [r['id'] for r in planned[area] if r.get(system, {}).get('status') != 'ok']
    rate_limited = {system: [r['id'] for r in planned['assessment'] if any(call.get('http_status') == 429 for call in r.get(system, {}).get('calls', []))] for system in ('repoviva', 'baseline')}
    rate_note = (f"Assessment comparison is inconclusive: Groq HTTP 429 errors withheld {len(rate_limited['repoviva'])} RepoViva verdicts and {len(rate_limited['baseline'])} baseline verdicts. Do not interpret differing availability as an assessment-accuracy ranking. Keep this run and use a separately named, more slowly paced replication."
                 if any(rate_limited.values()) else 'No assessment rate-limit errors were recorded in this run.')
    speech = sections.get('speech', [])
    spoken = [r for r in speech if r['status'] == 'ok']
    edits = sum(r['word_errors']['edits'] for r in spoken)
    reference_words = sum(r['word_errors']['reference_words'] for r in spoken)
    reliability = sections.get('reliability', [])
    reliable = sum(r.get('status') == 'ok' and r.get('passed') is True for r in reliability)
    browser_valid = browser.get('dataset_sha256') == dataset_hash
    test_agreement = sum(r['agrees_with_draft_label'] for r in browser['results']) if browser_valid else 0
    summary = {'human_approved': approved, 'human_disputed': disputed, 'planned_cases': len(cases), 'metrics': metrics,
        'browser_tests': {'agreed': test_agreement, 'planned': 12, 'valid_dataset_hash': browser_valid},
        'speech': {'completed': len(spoken), 'planned': 8, 'word_edits': edits, 'reference_words': reference_words,
            'wer': round(edits / reference_words, 4) if reference_words else None,
            'clips_with_missing_protected_expression': [r['id'] for r in spoken if r['missing_protected_groups']], 'real_learner_corrections': 0},
        'reliability': {'passed': reliable, 'planned': 4}, 'status': 'Provisional; independent human review pending' if approved < len(cases) or disputed else 'Review sheet approved; see reviewer identities and limitations'}
    manifest = read('freeze.json', {'files': {}})
    summary['changed_frozen_files'] = [name for name, expected in manifest['files'].items() if frozen_bytes(HERE.parent / name, expected) is None]
    summary['newline_only_differences'] = [name for name, expected in manifest['files'].items() if (original := frozen_bytes(HERE.parent / name, expected)) is not None and original != (HERE.parent / name).read_bytes()]
    (HERE / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    lines = ['# RepoViva evaluation candidate v1', '', summary['status'], '',
        f'40 planned cases: 16 assessment, 12 repair, 8 speech, 4 reliability. Human-approved: {approved}/40; disputed: {disputed}.', '',
        '| Area | RepoViva | Same-model general assistant |', '| --- | --- | --- |']
    for area in ('assessment', 'repairs'):
        lines.append(f"| {area} label agreement with draft expectations | {ratio(metrics[area]['repoviva'])} | {ratio(metrics[area]['baseline'])} |")
    lines.append(f"| Assessment exact point agreement | {metrics['assessment']['repoviva']['exact_point_agreement']}/16 | {metrics['assessment']['baseline']['exact_point_agreement']}/16 |")
    lines += ['', f'Actual browser repair test agreement: {test_agreement}/12. Reliability checks: {reliable}/4.',
        f'Synthetic speech: {len(spoken)}/8 completed; raw word edits {edits}/{reference_words}; WER {summary["speech"]["wer"]}.', '',
        'These are provisional observations against assistant-authored expectations, not human-reviewed benchmark accuracy.',
        'The baseline uses the same Groq gpt-oss-120b model and same source/requirements. This is not a ChatGPT product comparison.',
        'Sources and labels were frozen before model calls. Development examples in checks/ are excluded. No product tuning was performed against these results.',
        'Four assessment source families and four repair families are correlated cases; the sample is small and does not establish population performance.',
        'Speech is a single stock synthetic voice. Raw WER includes script and number-format differences; missing-expression checks are lexical heuristics, not semantic error rates.',
        'Human listening is pending. Proposed corrections are intended script spellings; no learner corrections have been collected.',
        'Reliability uses local PostgreSQL and injected faults except the live silence call. It does not establish deployed uptime.', '',
        rate_note, '',
        '## Incorrect acceptances, rejections and unavailable verdicts', '']
    for area in ('assessment', 'repairs'):
        for system, values in metrics[area].items():
            lines.append(f"- {area}/{system}: incorrect acceptances {values['incorrect_acceptances']} / {values['negative_cases']} negatives; incorrect rejections {values['incorrect_rejections']} / {values['positive_cases']} positives; positive cases without verdict {values['positive_cases_without_verdict']}.")
            lines.append(f"- {area}/{system}: unavailable case IDs {values['unavailable_cases']}. Unavailable cases are not successful judgments, even when no incorrect acceptance is observed.")
    (HERE / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    blocks = []
    for area, title in [('assessment', 'Assessment · 16 cases'), ('repairs', 'Repair · 12 cases'), ('speech', 'Speech · 8 synthetic clips'), ('reliability', 'Reliability · 4 cases')]:
        by_id = {r['id']: r for r in sections.get(area, [])}
        items = []
        for case in data[area]:
            row = by_id.get(case['id'], {})
            if area in ('assessment', 'repairs'):
                expected = case.get('expected_label', case.get('expected'))
                result_text = lambda system: row.get(system, {}).get('label', row.get(system, {}).get('status', 'not run'))
                detail = f'<p>Draft expectation: <strong>{escape(expected)}</strong>. RepoViva: <strong>{escape(result_text("repoviva"))}</strong>. General assistant: <strong>{escape(result_text("baseline"))}</strong>.</p>'
                if area == 'assessment':
                    source = data['sources'][case['source']]
                    detail += f'<h4>Source · {escape(source["path"])}</h4><pre>{escape(source["code"])}</pre><h4>Question</h4><p>{escape(source["question"])}</p><h4>Student answer</h4><p>{escape(case["answer"])}</p><h4>Reference and criteria</h4><p>{escape(source["reference_answer"])}</p><pre>{escape(json.dumps(source["rubric"], ensure_ascii=False, indent=2))}</pre>'
                else:
                    family = data['repair_families'][case['family']]
                    detail += f'<p>{escape(family["contract"])}</p><h4>Original implementation</h4><pre>{escape(family["reference_code"])}</pre><h4>Broken starter</h4><pre>{escape(family["starter_code"])}</pre><h4>Proposed repair</h4><pre>{escape(family[case["variant"]])}</pre>'
                    test_row = next((r for r in browser['results'] if r['id'] == case['id']), {}) if browser_valid else {}
                    detail += f'<h4>Actual browser test observations</h4><pre>{escape(json.dumps(test_row, indent=2))}</pre>'
                detail += f'<p>Draft reviewer rationale: {escape(case["rationale"])}</p>'
                for system in ('repoviva', 'baseline'):
                    feedback = row.get(system, {}).get('feedback', row.get(system, {}))
                    detail += f'<h4>{escape(system)} response</h4><pre>{escape(json.dumps(feedback, ensure_ascii=False, indent=2))}</pre>'
            elif area == 'speech':
                detail = f'<p>{escape(case["language"])} · {escape(row.get("status", "not run"))}. Stock synthetic voice; listening review pending.</p>'
                if row.get('status') == 'ok':
                    detail += f'<audio controls preload="none" src="/evaluation/data/{escape(row["audio"])}"></audio><h4>Intended spoken script</h4><p>{escape(case["reference"])}</p><h4>Actual Prisma transcript</h4><p>{escape(row["transcript"])}</p><h4>Identifier-spelling correction draft</h4><p>{escape(row["proposed_correction"])}</p><p>No learner correction has been collected. This draft is not substituted into a learner answer.</p><pre>{escape(json.dumps({key:row[key] for key in ("word_errors", "missing_protected_groups", "checks")}, ensure_ascii=False, indent=2))}</pre>'
                else: detail += f'<pre>{escape(json.dumps(row, indent=2))}</pre>'
            else:
                detail = f'<p>Expected: {escape(case["expected"])}</p><pre>{escape(json.dumps(row, ensure_ascii=False, indent=2))}</pre>'
            items.append(f'<details id="{case["id"]}"><summary>{case["id"]} · {escape(case.get("kind", case.get("variant", case.get("fault", case.get("language")))))}</summary>{detail}</details>')
        blocks.append(f'<section id="{area}"><h2>{title}</h2>{"".join(items)}</section>')
    rows = ''.join(f'<tr><th scope="row">{area.capitalize()} label agreement</th><td>{escape(ratio(metrics[area]["repoviva"]))}</td><td>{escape(ratio(metrics[area]["baseline"]))}</td></tr>' for area in ('assessment', 'repairs'))
    rows += f'<tr><th scope="row">Assessment exact point agreement</th><td>{metrics["assessment"]["repoviva"]["exact_point_agreement"]}/16</td><td>{metrics["assessment"]["baseline"]["exact_point_agreement"]}/16</td></tr>'
    failures = ''.join(f'<li>{escape(line[2:])}</li>' for line in lines if line.startswith('- '))
    css = '''@font-face{font-family:WorkSans;src:url('/fonts/debug/work-sans-regular.ttf')}*{box-sizing:border-box}body{margin:0;background:#111214;color:#f0f0f2;font:16px/1.65 WorkSans,system-ui,sans-serif}main{max-width:1040px;margin:auto;padding:44px 24px 80px}a{color:#dedee3;text-underline-offset:4px}a:focus-visible,summary:focus-visible{outline:2px solid #dedee3;outline-offset:5px}header{border-bottom:1px solid #35363b;padding-bottom:24px}h1{font-size:clamp(2rem,5vw,3.2rem);line-height:1.15;letter-spacing:-.03em;margin:28px 0 16px}h2{font-size:1.45rem;margin-top:40px}h4{font-size:1rem;margin:20px 0 8px}p,li{max-width:75ch}nav{display:flex;gap:18px;flex-wrap:wrap}aside{border-left:1px solid #dedee3;padding:2px 18px;margin:28px 0;color:#dedee3}table{border-collapse:collapse;width:100%;min-width:650px;font-size:14px;font-variant-numeric:tabular-nums}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #35363b;padding:12px}th{font-weight:600}.table-scroll{overflow-x:auto}details{border-bottom:1px solid #35363b;padding:16px 0}summary{cursor:pointer;font-weight:600;padding:4px 0}pre{background:#1a1b1e;border:1px solid #35363b;padding:16px;white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.65 ui-monospace,monospace}audio{width:100%;max-width:420px}footer{border-top:1px solid #35363b;margin-top:44px;padding-top:20px;color:#a5a6ae}.muted{color:#a5a6ae}'''
    integrity = f'<p>Changed files since freeze: {escape(summary["changed_frozen_files"])}. These results describe the frozen version; changed code needs a separate run.</p>' if summary['changed_frozen_files'] else f'<p>Frozen input content matches this checkout. Git newline-only conversions: {escape(summary["newline_only_differences"])}.</p>'
    review_note = 'Expected labels were drafted and inspected by the coding assistant. They are not independent human ground truth. Inspect each case below before using these results as evidence.' if approved < len(cases) or disputed else 'The review sheet records approval of all draft expectations. Inspect reviewer identities, notes and the small-sample limitations before using these results as evidence.'
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>RepoViva · Evaluation & limitations</title><style>{css}</style></head><body><main>
<header><a href="/">← Back to RepoViva</a><h1>What we tested.<br>What remains uncertain.</h1><p>Evaluation candidate v1 · 40 cases · English and Hinglish</p><nav aria-label="Report sections"><a href="#assessment">Assessment</a><a href="#repairs">Repair</a><a href="#speech">Speech</a><a href="#reliability">Reliability</a></nav></header>
<aside><strong>{escape(summary['status'])}</strong><p>{approved}/40 human-approved; {disputed} disputed. {review_note}</p></aside>
<h2>Observed results</h2><p>Every planned case stays in the denominator. Errors and missing outputs are shown; there are no automatic retries to replace failed observations.</p><div class="table-scroll"><table><caption>Agreement with frozen draft labels</caption><thead><tr><th>Area</th><th>RepoViva</th><th>General-assistant baseline</th></tr></thead><tbody>{rows}</tbody></table></div>
<p><strong>{escape(rate_note)}</strong></p>
<p>Actual browser repair tests: {test_agreement}/12 agree with the draft labels. Reliability checks passed: {reliable}/4. Synthetic speech clips completed: {len(spoken)}/8; raw word edits: {edits}/{reference_words}.</p>
<h2>Failures and unavailable verdicts</h2><ul>{failures}</ul><p>Speech clips with missing protected expressions: {escape(summary['speech']['clips_with_missing_protected_expression'])}. Expand the speech cases for transcripts and lexical flags. These flags do not measure technical meaning.</p>
<h2>Comparison and boundaries</h2><p>The baseline uses the same Groq model, temperature, token budget, source, requirements, references and questions. It receives a general-assistant review prompt and the same output schema. Both systems are asked to accept equivalent explanations and alternative fixes. Neither receives expected labels or repair test outputs. Case order alternates which system goes first.</p><p>This is a same-model prompt/workflow comparison, not a benchmark of the ChatGPT product. A dedicated interface alone does not demonstrate better assessment.</p><p>Four assessment source families and four repair families produce correlated cases. Only finite, self-contained JavaScript repairs are executed, in the actual browser sandbox. Passing these tests is not proof over all inputs or support for running arbitrary projects.</p><p>Speech uses one stock synthetic voice, not real learners. Raw word error rate counts number formatting and script differences as edits. Human listening and real learner corrections remain pending. Silence is a live Prisma call; other reliability faults are injected through real local Flask/PostgreSQL routes. Deployment uptime is not measured.</p><p>The dataset, prompts and production code hashes were frozen before model calls. Development smoke examples in checks/ were excluded. No product tuning was performed against these results. If any failure motivates a product change, keep this run and evaluate the change on a new held-out set.</p>{integrity}
<h2>Inspect or reproduce</h2><nav aria-label="Evaluation files"><a href="/evaluation/data/report.md">Summary</a><a href="/evaluation/data/dataset.json">All cases</a><a href="/evaluation/data/results.json">Raw prompts and responses</a><a href="/evaluation/data/browser-tests.json">Browser test observations</a><a href="/evaluation/data/freeze.json">Frozen hashes</a><a href="/evaluation/data/baseline.json">Baseline prompt</a><a href="/evaluation/data/review.csv">Human review sheet</a><a href="/evaluation/data/README.md">Reproduction & review instructions</a></nav>
{''.join(blocks)}<footer>RepoViva · Report generated from retained local observations. It makes no claim of real-learner accuracy or superiority to ChatGPT.</footer></main></body></html>'''
    (HERE / 'report.html').write_text(page, encoding='utf-8')
    print('\n'.join(lines[:14]))


if __name__ == '__main__':
    main()
