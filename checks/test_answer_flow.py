import json
import os
import unittest
from unittest.mock import Mock, patch

from backend.app import app, turns, TURN_TTL_SECONDS
from backend.interview.evaluator import EvaluationError, evaluate_answer


class AnswerFlowTests(unittest.TestCase):
    def setUp(self):
        turns.clear()
        self.client = app.test_client()

    def test_answer_uses_server_stored_question_and_evidence(self):
        with patch("backend.app.generate_question", return_value="What is the chunk size?"):
            question = self.client.post("/questions").get_json()
        claims = [{"claim": "Chunks hold up to 40 lines.", "label": "supported",
                   "explanation": "The slice takes at most 40 lines.",
                   "quote": "snippet = lines[start:start+40]"}]
        with patch("backend.app.evaluate_answer", return_value=claims) as evaluate:
            response = self.client.post("/answers", json={
                "turn_id": question["turn_id"], "answer": "40 lines", "question": "tampered"
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["claims"], claims)
        self.assertEqual(evaluate.call_args.args[0], "What is the chunk size?")
        self.assertEqual(evaluate.call_args.args[2], question["evidence"]["snippet"] | {"id": tuple(question["evidence"]["snippet"]["id"])})

    def test_unknown_turn_and_provider_failure(self):
        self.assertEqual(self.client.post("/answers", json={"turn_id": "unknown", "answer": "x"}).status_code, 404)
        with patch("backend.app.generate_question", return_value="Question?"):
            turn_id = self.client.post("/questions").get_json()["turn_id"]
        with patch("backend.app.evaluate_answer", side_effect=EvaluationError("private provider detail")):
            response = self.client.post("/answers", json={"turn_id": turn_id, "answer": "x"})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private provider detail", response.get_data(as_text=True))
        self.assertFalse(turns[turn_id]["busy"])

    def test_invalid_request_inputs_are_rejected_before_evaluation(self):
        invalid_payloads = [None, [], "answer", {}, {"answer": "x"},
                            {"turn_id": "id"}, {"turn_id": 123, "answer": "x"},
                            {"turn_id": "", "answer": "x"},
                            {"turn_id": "   ", "answer": "x"},
                            {"turn_id": "id", "answer": 123},
                            {"turn_id": "id", "answer": ""},
                            {"turn_id": "id", "answer": "   "},
                            {"turn_id": "id", "answer": "x" * 4001}]
        with patch("backend.app.evaluate_answer") as evaluate:
            for payload in invalid_payloads:
                with self.subTest(payload=payload):
                    self.assertEqual(self.client.post("/answers", json=payload).status_code, 400)
            malformed = self.client.post("/answers", data="{", content_type="application/json")
            self.assertEqual(malformed.status_code, 400)
            evaluate.assert_not_called()

    def test_expired_turn_is_rejected(self):
        with patch("backend.app.generate_question", return_value="Question?"):
            turn_id = self.client.post("/questions").get_json()["turn_id"]
        turns[turn_id]["created"] -= TURN_TTL_SECONDS
        with patch("backend.app.evaluate_answer") as evaluate:
            response = self.client.post("/answers", json={"turn_id": turn_id, "answer": "40"})
            self.assertEqual(response.status_code, 404)
            self.assertNotIn(turn_id, turns)
            evaluate.assert_not_called()

    def test_busy_turn_does_not_start_another_evaluation(self):
        with patch("backend.app.generate_question", return_value="Question?"):
            turn_id = self.client.post("/questions").get_json()["turn_id"]
        turns[turn_id]["busy"] = True
        with patch("backend.app.evaluate_answer") as evaluate:
            response = self.client.post("/answers", json={"turn_id": turn_id, "answer": "40"})
            self.assertEqual(response.status_code, 409)
            evaluate.assert_not_called()

    def test_evaluator_rejects_nonverbatim_quote(self):
        snippet = {"path": "sample.py", "start_line": 1, "end_line": 3,
                   "content": ["if ready:", "    first()", "    second()"]}
        claim = {"claim": "c", "label": "supported", "explanation": "e",
                 "quote": "first()\nsecond()"}
        response = Mock(ok=True)
        response.json.return_value = {"choices": [{"message": {"content": json.dumps([claim])}}]}
        with patch.dict(os.environ, {"GROQ_API_KEY": "test"}), patch("backend.interview.evaluator.requests.post", return_value=response):
            with self.assertRaises(EvaluationError):
                evaluate_answer("q", "a", snippet)


if __name__ == "__main__":
    unittest.main()
