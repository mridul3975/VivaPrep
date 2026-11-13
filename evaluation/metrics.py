"""Declared metrics shared by both systems. Never treat provider errors as correct."""
import re
import unicodedata


def assessment_outcome(result):
    criteria, claims = result.get('criteria'), result.get('claims')
    if not isinstance(criteria, list) or len(criteria) != 2 or {row.get('id') for row in criteria} != {'c1', 'c2'}:
        raise ValueError('Incomplete rubric result')
    points = {'met': 1, 'partial': .5, 'missed': 0, 'contradicted': 0, 'unverified': 0}
    if not isinstance(claims, list) or any(row.get('status') not in points for row in criteria):
        raise ValueError('Invalid result')
    earned = sum(points[row['status']] for row in criteria)
    label = ('contradicted' if any(row.get('label') == 'contradicted' for row in claims) or any(row['status'] == 'contradicted' for row in criteria)
             else 'supported' if earned == 2 else 'partial' if earned > 0 else 'unsupported')
    # Acceptance requires every criterion to be demonstrated and no contradiction.
    return {'label': label, 'points': earned, 'accepted': label == 'supported'}


def agreement(rows, system, expected_key, actual_key):
    valid = [row for row in rows if row.get(system, {}).get('status') == 'ok']
    correct = sum(row[system][actual_key] == row[expected_key] for row in valid)
    # Missing outputs, uncertain verdicts and errors remain in the planned denominator.
    return {'agreed': correct, 'planned': len(rows), 'completed': len(valid), 'errors_or_missing': len(rows) - len(valid)}


def errors(rows, system, positive_label):
    negatives = [row for row in rows if row['expected'] != positive_label]
    positives = [row for row in rows if row['expected'] == positive_label]
    false_accept = [row['id'] for row in negatives if row.get(system, {}).get('status') == 'ok' and row[system].get('label') == positive_label]
    false_reject = [row['id'] for row in positives if row.get(system, {}).get('status') == 'ok' and row[system].get('label') != positive_label]
    unavailable = [row['id'] for row in positives if row.get(system, {}).get('status') != 'ok']
    return {'incorrect_acceptances': false_accept, 'negative_cases': len(negatives), 'incorrect_rejections': false_reject,
            'positive_cases': len(positives), 'positive_cases_without_verdict': unavailable}


def words(text):
    # Keep Devanagari combining marks. WER deliberately does not transliterate or map numbers.
    return ''.join(' ' if unicodedata.category(char)[0] in {'P', 'S'} else char for char in text.casefold()).split()


def word_errors(reference, hypothesis):
    ref, hyp = words(reference), words(hypothesis)
    previous = list(range(len(hyp) + 1))
    for i, left in enumerate(ref, 1):
        current = [i]
        for j, right in enumerate(hyp, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (left != right)))
        previous = current
    return {'edits': previous[-1], 'reference_words': len(ref), 'wer': round(previous[-1] / len(ref), 4) if ref else None}
