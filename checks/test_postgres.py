"""Real PostgreSQL integration checks, restricted to a dedicated test database."""
import io
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import uuid

from backend.app import app, turns
from backend.auth import auth_sessions
from backend.database import PostgresStore, DatabaseUnavailable, StudyConflict, close_pools
from backend.evidence.uploads import sources
from backend.interview.evaluator import EvaluationError
from checks.auth_fixtures import authenticated_client
from checks.quiz_fixtures import fake_question_set, fake_grade

TEST_URL = os.getenv("TEST_DATABASE_URL", "")


@unittest.skipUnless(TEST_URL, "Set TEST_DATABASE_URL to an isolated repoviva_test database.")
class PostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        store = PostgresStore(TEST_URL)
        with store.connection() as conn:
            if conn.execute("SELECT current_database() AS name").fetchone()["name"] != "repoviva_test":
                raise RuntimeError("Integration tests require a dedicated database named repoviva_test.")
        store.migrate()
        store.pool.close()

    @classmethod
    def tearDownClass(cls):
        close_pools()

    def setUp(self):
        override = patch.dict(app.config, {"DATABASE_URL_OVERRIDE": TEST_URL})
        override.start()
        self.addCleanup(override.stop)
        self.store = PostgresStore(TEST_URL)
        self.addCleanup(self.store.pool.close)
        with self.store.connection() as conn:
            conn.execute("TRUNCATE repoviva.users CASCADE")
        self.client = authenticated_client(app, "google:db-one")
        self.other = authenticated_client(app, "google:db-two")

    def upload(self, text=b"Photosynthesis uses light energy.", name="notes.md"):
        response = self.client.post("/sources", data={"source_file": (io.BytesIO(text), name)})
        self.addCleanup(response.close)
        self.addCleanup(response.request.environ["wsgi.input"].close)
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def question(self, source_id):
        with patch("backend.app.generate_question_set", side_effect=fake_question_set):
            response = self.client.post("/questions", json={"source_id": source_id})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertNotIn("reference_answer", response.get_data(as_text=True))
        return response.get_json()["questions"][0]

    def answer(self, turn_id, text="Light energy."):
        with patch("backend.app.grade_answer", side_effect=fake_grade):
            response = self.client.post("/answers", json={"turn_id": turn_id, "answer": text})
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def test_migration_is_idempotent_and_uses_real_postgresql(self):
        self.store.migrate()
        self.store.check()
        with self.store.connection() as conn:
            self.assertIn("PostgreSQL", conn.execute("SELECT version() AS version").fetchone()["version"])
            self.assertEqual(conn.execute("SELECT count(*) AS count FROM repoviva.schema_migrations").fetchone()["count"], 1)

    def test_material_questions_answers_and_scores_survive_new_python_process(self):
        source = self.upload()
        question = self.question(source["source_id"])
        feedback = self.answer(question["turn_id"])
        sources.clear()
        turns.clear()
        auth_sessions.clear()
        close_pools()
        env = {**os.environ, "DATABASE_URL": TEST_URL,
               "TEST_SESSION_COOKIE": self.client.get_cookie(app.config["SESSION_COOKIE_NAME"]).value}
        code = """import os,json
from backend.app import app
with app.test_client() as client:
 client.set_cookie(app.config['SESSION_COOKIE_NAME'],os.environ['TEST_SESSION_COOKIE'])
 user=client.get('/auth/session').get_json()['user']
 source=client.get('/sources/current').get_json()
 history=client.get('/history').get_json()['attempts']
 print(json.dumps({'signed_in':bool(user),'source_id':source['source_id'],'turn_id':source['saved_practice']['questions'][0]['turn_id'],'percentage':history[0]['percentage']}))
"""
        child = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(child.returncode, 0, "Fresh process failed to restore persistent study state.")
        restored = json.loads(child.stdout)
        self.assertTrue(restored["signed_in"])
        self.assertEqual(restored["source_id"], source["source_id"])
        self.assertEqual(restored["turn_id"], question["turn_id"])
        self.assertEqual(restored["percentage"], feedback["score"]["percentage"])

    def test_unsubmitted_reference_is_hidden_and_submitted_feedback_restores(self):
        source = self.upload()
        question = self.question(source["source_id"])
        response = self.client.get("/sources/current")
        self.assertNotIn("reference_answer", response.get_data(as_text=True))
        self.assertIsNone(response.get_json()["expires_in_seconds"])
        answer = self.answer(question["turn_id"])
        restored = self.client.get("/sources/current").get_json()["saved_practice"]
        self.assertEqual(restored["results"][question["turn_id"]], answer)
        self.assertEqual(restored["answers"][question["turn_id"]], "Light energy.")

    def test_other_student_cannot_read_delete_answer_or_view_history(self):
        source = self.upload()
        question = self.question(source["source_id"])
        self.answer(question["turn_id"])
        self.assertEqual(self.other.get("/sources/" + source["source_id"]).status_code, 404)
        self.assertEqual(self.other.delete("/sources/" + source["source_id"]).status_code, 404)
        with patch("backend.app.grade_answer") as grade:
            self.assertEqual(self.other.post("/answers", json={"turn_id": question["turn_id"], "answer": "x"}).status_code, 404)
            grade.assert_not_called()
        self.assertEqual(self.other.get("/sources/current").status_code, 204)
        self.assertEqual(self.other.get("/history").get_json()["attempts"], [])

    def test_replacing_material_keeps_prior_turns_grounded_in_their_snapshot(self):
        old = self.upload()
        question = self.question(old["source_id"])
        new = self.upload(b"The treaty was signed in 1919.", "history.md")
        self.assertEqual(self.client.get("/sources/" + old["source_id"]).status_code, 404)
        feedback = self.answer(question["turn_id"])
        self.assertEqual(feedback["evidence"]["path"], "notes.md")
        current = self.client.get("/sources/current").get_json()
        self.assertEqual(current["source_id"], new["source_id"])
        self.assertIsNone(current["saved_practice"])
        self.assertEqual(self.client.get("/history").get_json()["attempts"][0]["filename"], "notes.md")

    def test_removing_material_cascades_its_questions_and_attempts(self):
        source = self.upload()
        question = self.question(source["source_id"])
        self.answer(question["turn_id"])
        self.assertEqual(self.client.delete("/sources/" + source["source_id"]).status_code, 204)
        self.assertEqual(self.client.get("/sources/current").status_code, 204)
        self.assertEqual(self.client.get("/history").get_json()["attempts"], [])
        self.assertEqual(self.client.post("/answers", json={"turn_id": question["turn_id"], "answer": "x"}).status_code, 404)

    def test_failed_transaction_preserves_previous_active_material(self):
        source = self.upload()
        # Duplicate primary key fails after deactivation inside the transaction.
        with self.assertRaises(DatabaseUnavailable):
            self.store.replace_source("google:db-one", source)
        self.assertEqual(self.client.get("/sources/current").get_json()["source_id"], source["source_id"])

    def test_evaluation_lease_prevents_duplicates_and_recovers_after_crash(self):
        question = self.question(self.upload()["source_id"])
        _, first_lease = self.store.claim_turn("google:db-one", question["turn_id"])
        with self.assertRaises(StudyConflict):
            self.store.claim_turn("google:db-one", question["turn_id"])
        with self.store.connection() as conn:
            conn.execute("UPDATE repoviva.turns SET busy_until=now()-interval '1 second' WHERE id=%s", (question["turn_id"],))
        turn, second_lease = self.store.claim_turn("google:db-one", question["turn_id"])
        self.assertNotEqual(first_lease, second_lease)
        self.store.release_turn("google:db-one", question["turn_id"], first_lease)
        with self.assertRaises(StudyConflict):
            self.store.claim_turn("google:db-one", question["turn_id"])
        self.store.release_turn("google:db-one", question["turn_id"], second_lease)
        self.assertEqual(turn["question"], question["question"])

    def test_provider_failure_saves_no_attempt_and_allows_retry(self):
        question = self.question(self.upload()["source_id"])
        with patch("backend.app.grade_answer", side_effect=EvaluationError("unavailable")):
            self.assertEqual(self.client.post("/answers", json={"turn_id": question["turn_id"], "answer": "x"}).status_code, 502)
        self.assertEqual(self.client.get("/history").get_json()["attempts"], [])
        self.answer(question["turn_id"])
        self.assertEqual(len(self.client.get("/history").get_json()["attempts"]), 1)

    def test_database_failure_does_not_silently_use_memory(self):
        source = self.upload()
        with patch("backend.database.PostgresStore.identity", side_effect=DatabaseUnavailable("private connection details")):
            response = self.client.get("/sources/current")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error_code"], "database_unavailable")
        self.assertNotIn("private", response.get_data(as_text=True))
        self.assertEqual(self.client.get("/sources/current").get_json()["source_id"], source["source_id"])

    def test_replacement_does_not_block_an_inflight_owner_foreign_key(self):
        source = self.upload()
        separator = "&" if "?" in TEST_URL else "?"
        store = PostgresStore(TEST_URL + separator + "options=-c%20lock_timeout%3D1000")
        self.addCleanup(store.pool.close)
        replacement = {**source, "source_id": uuid.uuid4().hex}
        # An in-flight question insert holds FK KEY SHARE on its owner/source.
        with self.store.connection() as pending:
            pending.execute("INSERT INTO repoviva.practice_sets(id,owner,source_id) VALUES (%s,%s,%s)", (uuid.uuid4().hex, "google:db-one", source["source_id"]))
            with ThreadPoolExecutor(max_workers=1) as executor:
                saved = executor.submit(store.replace_source, "google:db-one", replacement).result(timeout=5)
        self.assertEqual(saved["source_id"], replacement["source_id"])

    def test_committed_feedback_does_not_need_a_second_release_request(self):
        question = self.question(self.upload()["source_id"])
        with patch("backend.database.PostgresStore.release_turn", side_effect=DatabaseUnavailable("unexpected second write")) as release:
            self.answer(question["turn_id"])
        release.assert_not_called()
        self.assertEqual(len(self.client.get("/history").get_json()["attempts"]), 1)


if __name__ == "__main__":
    unittest.main()
