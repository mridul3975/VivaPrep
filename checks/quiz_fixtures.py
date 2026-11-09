def fake_question_set(snippets, count=3):
    snippet = snippets[0]
    line_number, quote = next((number, line) for number, line in enumerate(snippet['content'], 1) if line.strip())
    return [{'question': f'Explain the concept in {snippet["path"]}.',
             'reference_answer': 'A hidden source-grounded reference answer.',
             'rubric': [{'id': 'c1', 'description': 'Explain the required concept.',
                         'snippet_id': str(snippet['id']), 'quote': quote, 'line_start': line_number, 'line_end': line_number}]}]


def fake_grade(package, answer, snippets):
    criterion = package['rubric'][0]
    return {'reference_answer': package['reference_answer'], 'claims': [],
            'criteria': [{**criterion, 'status': 'met', 'points': 1, 'max_points': 1,
                          'explanation': 'Correct meaning.', 'evidence': snippets[0]}],
            'score': {'earned': 1, 'possible': 1, 'percentage': 100, 'excluded_criteria': 0}}
