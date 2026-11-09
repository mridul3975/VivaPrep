from checks.auth_fixtures import authenticated_client
def main():
    import argparse
    import io
    import json
    from pathlib import Path
    from backend.app import app

    parser = argparse.ArgumentParser(description='Live question generation from an uploaded file.')
    parser.add_argument('source_file')
    args = parser.parse_args()
    path = Path(args.source_file)
    with authenticated_client(app) as client:
        with path.open('rb') as stream:
            uploaded = client.post('/sources', data={'source_file': (stream, path.name)})
        if uploaded.status_code != 201:
            raise SystemExit(uploaded.get_json())
        response = client.post('/questions', json={'source_id': uploaded.get_json()['source_id']})
        print('HTTP', response.status_code)
        print(json.dumps(response.get_json(), indent=2, ensure_ascii=False))
        if response.status_code != 200:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
