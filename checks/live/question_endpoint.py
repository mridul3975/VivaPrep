def main():
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))

    from backend.app import app

    def test_question_endpoint():
        client = app.test_client()
        response = client.post("/questions")

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.get_json()

        assert "question" in data, "Response missing 'question' key"
        assert isinstance(data["question"], str) and data["question"].strip(), "Empty question returned"
        assert "evidence" in data, "Response missing 'evidence' key"
        assert data["evidence"]["start_line"] == 1
        assert data["evidence"]["end_line"] == 40

        print("SUCCESS: Question endpoint returned 200 with valid question and evidence.")
        print("Generated question:", data["question"])

    if __name__ == "__main__":
        test_question_endpoint()


if __name__ == "__main__":
    main()
