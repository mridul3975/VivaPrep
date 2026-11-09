def main():
    import argparse
    import json
    from pathlib import Path
    from backend.app import app

    parser = argparse.ArgumentParser(description='Live source -> AI question/reference -> scored answer.')
    parser.add_argument('source_file')
    parser.add_argument('--answer', required=True)
    args = parser.parse_args()
    path = Path(args.source_file)
    with app.test_client() as client:
        with path.open('rb') as stream:
            uploaded = client.post('/sources', data={'source_file': (stream, path.name)})
        if uploaded.status_code != 201:
            raise SystemExit(uploaded.get_json())
        generated = client.post('/questions', json={'source_id': uploaded.get_json()['source_id'], 'count': 1})
        if generated.status_code != 200:
            raise SystemExit(generated.get_json())
        question = generated.get_json()['questions'][0]
        print('Generated question:', question['question'])
        response = client.post('/answers', json={'turn_id': question['turn_id'], 'answer': args.answer})
        print('HTTP', response.status_code)
        print(json.dumps(response.get_json(), indent=2, ensure_ascii=False))
        if response.status_code != 200:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
