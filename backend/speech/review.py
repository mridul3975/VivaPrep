"""Conservative source-term review suggestions, not acoustic confidence scores."""
import re
import uuid
from difflib import SequenceMatcher
from threading import Lock
from psycopg.types.json import Jsonb
from backend.database import database_enabled, get_database, StudyConflict

receipts = {}
lock = Lock()


def suggested_checks(transcript, snippets):
    source = '\n'.join('\n'.join(item['content']) for item in snippets)[:12000]
    terms = list(dict.fromkeys(re.findall(r'\b(?:def|class|function)\s+([A-Za-z_]\w*)', source) + re.findall(r'\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+\b|\b[a-z]+[A-Z][A-Za-z0-9]*\b', source)))[:60]
    words = list(re.finditer(r'\b[\w]+\b', transcript))[:500]
    normalize = lambda value: re.sub(r'[\W_]', '', value.casefold())
    checks = []
    for term in terms:
        target = normalize(term)
        if len(target) < 5 or term in transcript:
            continue
        best = None
        for index in range(len(words)):
            for count in (1,2,3):
                end = index + count - 1
                if end >= len(words):
                    continue
                phrase = transcript[words[index].start():words[end].end()]
                compact = normalize(phrase)
                if abs(len(compact) - len(target)) > 3:
                    continue
                ratio = SequenceMatcher(None, compact, target).ratio()
                if ratio >= .8 and (best is None or ratio > best[0]):
                    best = (ratio,phrase)
        if best:
            checks.append({'heard':best[1], 'source_term':term, 'message':'Possible source-term spelling. Keep it unchanged if that is what you meant.'})
        if len(checks) == 6:
            break
    return checks


def store_review(owner, turn_id, transcript, snippets):
    record = {'receipt_id':uuid.uuid4().hex, 'original_transcript':transcript, 'checks':suggested_checks(transcript,snippets), 'reviewed':False}
    if database_enabled():
        with get_database().connection() as conn:
            if not conn.execute('SELECT id FROM repoviva.turns WHERE id=%s AND owner=%s', (turn_id,owner)).fetchone():
                raise StudyConflict('Question changed while transcribing. Record again for the current question.',409)
            conn.execute('INSERT INTO repoviva.transcript_reviews(turn_id,owner,receipt_id,transcript,checks) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(turn_id) DO UPDATE SET receipt_id=EXCLUDED.receipt_id,transcript=EXCLUDED.transcript,checks=EXCLUDED.checks', (turn_id,owner,record['receipt_id'],transcript,Jsonb(record['checks'])))
    else:
        with lock:
            if len(receipts) >= 1000:
                receipts.pop(next(iter(receipts)))
            receipts[(owner,turn_id)] = record
    return record


def resolve_review(owner, turn_id, metadata, require_confirmed=False):
    if metadata is None:
        return None
    if not isinstance(metadata,dict) or set(metadata) != {'receipt_id','reviewed'} or not isinstance(metadata['receipt_id'],str) or type(metadata['reviewed']) is not bool:
        raise StudyConflict('Invalid transcript review. Reload the draft or use a typed answer.',400)
    if database_enabled():
        with get_database().connection() as conn:
            row = conn.execute('SELECT receipt_id,transcript AS original_transcript,checks FROM repoviva.transcript_reviews WHERE turn_id=%s AND owner=%s AND receipt_id=%s', (turn_id,owner,metadata['receipt_id'])).fetchone()
    else:
        with lock:
            row = receipts.get((owner,turn_id))
            row = row if row and row['receipt_id'] == metadata['receipt_id'] else None
    if not row:
        raise StudyConflict('This transcript was replaced or is unavailable. Record again or use a typed answer.',409)
    if require_confirmed and not metadata['reviewed']:
        raise StudyConflict('Confirm the transcript matches what you meant before submitting.',400)
    return {**row,'reviewed':metadata['reviewed']}
