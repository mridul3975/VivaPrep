def main():
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))

    try:
        from dotenv import load_dotenv
        load_dotenv(project_root / ".env")
    except ImportError:
        import os
        env_file = project_root / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    from backend.interview.evaluator import EvaluationError, evaluate_answer
    from backend.evidence.read import read

    sample_path = project_root / "samples" / "read.py"
    records = read(str(sample_path))

    snippet = records[0]
    question = "How does the program split files into snippets?"

    test_cases = [
        {
            "name": "1. Correct (Supported)",
            "answer": "The program reads the lines of the file and slices them into chunks of 40 lines each.",
        },
        {
            "name": "2. Incorrect limit (Contradicted)",
            "answer": "The file is split into chunks of 100 lines each.",
        },
        {
            "name": "3. Outside evidence (Unverified)",
            "answer": "The program connects to a PostgreSQL database to save each snippet record.",
        },
    ]

    print("=== Running Answer Evaluation Tests ===\n")
    for case in test_cases:
        print(f"--- {case['name']} ---")
        print(f"Answer: {case['answer']}")
        try:
            claims = evaluate_answer(question, case["answer"], snippet)
            for c in claims:
                print(f"  Claim: {c.get('claim')}")
                print(f"  Label: {c.get('label')}")
                print(f"  Quote: {c.get('quote')}")
                print(f"  Explanation: {c.get('explanation')}")
        except EvaluationError as e:
            print(f"  [ERROR] Evaluation failed: {e}")
        print()

    print("=== Testing Invalid Quote Rejection (Simulation) ===")
    # Test that a supported/contradicted claim with a fake quote raises EvaluationError
    import unittest.mock as mock

    fake_provider_response = {
        "choices": [
            {
                "message": {
                    "content": """[
                        {
                            "claim": "The program splits files into 100 lines.",
                            "label": "contradicted",
                            "explanation": "The file uses 40 lines, not 100.",
                            "quote": "this quote definitely does not exist in read.py"
                        }
                    ]"""
                }
            }
        ]
    }

    with mock.patch("requests.post") as mock_post:
        mock_post.return_value.ok = True
        mock_post.return_value.json.return_value = fake_provider_response

        try:
            evaluate_answer(question, "Simulated answer", snippet)
            print("FAIL: Expected EvaluationError was not raised for invalid quote.")
        except EvaluationError as e:
            print(f"SUCCESS: EvaluationError caught as expected: {e}")


if __name__ == "__main__":
    main()
