"""Read-only public evaluation artifacts; no provider calls or private workspace access."""
from pathlib import Path
from flask import Blueprint, abort, send_from_directory

evaluation = Blueprint('evaluation', __name__)
DIRECTORY = Path(__file__).resolve().parent.parent / 'evaluation'
PUBLIC_FILES = {'dataset.json', 'baseline.json', 'freeze.json', 'results.json', 'summary.json',
                'browser-tests.json', 'review.csv', 'report.md', 'README.md'}
PUBLIC_FILES.update(f'audio/S{number:02}.wav' for number in range(1, 9))


@evaluation.get('/evaluation')
def evaluation_report():
    return send_from_directory(DIRECTORY, 'report.html', max_age=0)


@evaluation.get('/evaluation/data/<path:filename>')
def evaluation_data(filename):
    if filename not in PUBLIC_FILES:
        abort(404)
    return send_from_directory(DIRECTORY, filename, max_age=0)
