from copy import deepcopy
import unittest
from unittest.mock import patch

from backend.interview.provider import ProviderError, resolve_line_citation, source_packet
from backend.interview.question_generator import QuestionGenerationError, generate_question_set
from backend.interview.grading import grade_answer
from backend.interview.evaluator import EvaluationError


SOURCE = {"id": "upload:2", "path": "code.py", "citation_type": "lines",
          "start_line": 41, "end_line": 44,
          "content": ["if ready:", "    first()", "", "    second()"]}
PACKAGE = {"question": "Explain what happens when ready is true and why the calls run in that order.",
           "reference_answer": "Both functions run in order.",
           "rubric": [{"id": "c1", "description": "Both functions run.",
                       "snippet_id": "upload:2", "line_start": 2, "line_end": 4}]}


class CitationRangeTests(unittest.TestCase):
    def test_citations_copy_indentation_and_blank_lines_from_original(self):
        quote, evidence = resolve_line_citation("upload:2", 2, 4, [SOURCE])
        self.assertEqual(quote, "    first()\n\n    second()")
        self.assertEqual((evidence["start_line"], evidence["end_line"]), (42, 44))
        self.assertEqual(evidence["content"], SOURCE["content"][1:])
        self.assertEqual(SOURCE["start_line"], 41)
        self.assertIn("[L2]     first()", source_packet([SOURCE]))

    def test_pdf_citations_keep_original_page(self):
        source = {**SOURCE, "path": "guide.pdf", "citation_type": "page", "page": 3,
                  "start_line": None, "end_line": None}
        quote, evidence = resolve_line_citation("upload:2", 2, 4, [source])
        self.assertEqual(quote, "    first()\n\n    second()")
        self.assertEqual(evidence["page"], 3)
        self.assertIsNone(evidence["start_line"])
        self.assertIsNone(evidence["end_line"])

    def test_unknown_out_of_bounds_reversed_noninteger_and_blank_ranges_fail(self):
        cases = [("other", 1, 1), ("upload:2", 0, 1), ("upload:2", 1, 5),
                 ("upload:2", 4, 2), ("upload:2", True, 2),
                 ("upload:2", "1", 2), ("upload:2", 3, 3)]
        for arguments in cases:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                resolve_line_citation(*arguments, [SOURCE])

    def test_question_quotes_are_copied_locally_even_if_model_supplies_bad_quote(self):
        package = deepcopy(PACKAGE)
        package["rubric"][0]["quote"] = "invented quote"
        with patch("backend.interview.question_generator.json_completion", return_value={"questions": [package]}) as provider:
            result = generate_question_set([SOURCE], count=1)
        self.assertEqual(result[0]["rubric"][0]["quote"], "    first()\n\n    second()")
        citation_schema = provider.call_args.args[2]["properties"]["questions"]["items"]["properties"]["rubric"]["items"]["properties"]
        self.assertNotIn("quote", citation_schema)
        self.assertEqual(citation_schema["snippet_id"]["enum"], ["upload:2"])

    def test_invalid_range_gets_one_repair_attempt_then_succeeds(self):
        invalid = deepcopy(PACKAGE)
        invalid["rubric"][0]["line_end"] = 99
        with patch("backend.interview.question_generator.json_completion", side_effect=[{"questions": [invalid]}, {"questions": [PACKAGE]}]) as provider:
            result = generate_question_set([SOURCE], count=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(provider.call_count, 2)
        self.assertIn("available lines are 1 to 4", provider.call_args.args[1])

    def test_repeated_invalid_range_stops_after_two_attempts(self):
        invalid = deepcopy(PACKAGE)
        invalid["rubric"][0]["line_end"] = 99
        with patch("backend.interview.question_generator.json_completion", return_value={"questions": [invalid]}) as provider:
            with self.assertRaises(QuestionGenerationError) as failure:
                generate_question_set([SOURCE])
        self.assertEqual(provider.call_count, 2)
        self.assertEqual(failure.exception.code, "invalid_evidence")

    def test_provider_rate_limit_is_explicit_and_not_immediately_retried(self):
        with patch("backend.interview.question_generator.json_completion", side_effect=ProviderError("Groq returned HTTP 429.", 429)) as provider:
            with self.assertRaises(QuestionGenerationError) as failure:
                generate_question_set([SOURCE])
        self.assertEqual(provider.call_count, 1)
        self.assertEqual((failure.exception.code, failure.exception.http_status), ("provider_rate_limit", 503))
        with patch("backend.interview.grading.json_completion", side_effect=ProviderError("Groq returned HTTP 429.", 429)):
            with self.assertRaises(EvaluationError) as failure:
                grade_answer(PACKAGE, "Both run.", [SOURCE])
        self.assertEqual((failure.exception.code, failure.exception.http_status), ("provider_rate_limit", 503))

    def test_supported_and_contradicted_claims_use_original_source_ranges(self):
        for label in ("supported", "contradicted"):
            response = {"criteria": [{"id": "c1", "status": "met", "explanation": "Both calls identified."}],
                        "claims": [{"claim": "The functions run.", "label": label, "explanation": "Source comparison.",
                                    "snippet_id": "upload:2", "line_start": 2, "line_end": 4}]}
            with self.subTest(label=label), patch("backend.interview.grading.json_completion", return_value=response):
                result = grade_answer(PACKAGE, "Both run.", [SOURCE])
            self.assertEqual(result["claims"][0]["quote"], "    first()\n\n    second()")
            self.assertEqual(result["claims"][0]["evidence"]["start_line"], 42)


if __name__ == "__main__":
    unittest.main()
