import io
import os
import time
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from google.auth import crypt, exceptions, jwt

from backend.app import app, turns
from backend.auth import auth_sessions
from backend.evidence.uploads import sources


class GoogleAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Exercise Google's real verifier using a locally generated signing key.
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        cls.public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        cls.signer = crypt.RSASigner.from_string(private)

    def setUp(self):
        storage = patch.dict(app.config, {"DATABASE_URL_OVERRIDE": ""})
        storage.start()
        self.addCleanup(storage.stop)
        auth_sessions.clear()
        sources.clear()
        turns.clear()
        self.addCleanup(auth_sessions.clear)
        self.addCleanup(sources.clear)
        self.addCleanup(turns.clear)
        env = patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "test-client.apps.googleusercontent.com"})
        env.start()
        self.addCleanup(env.stop)
        certs = patch("google.oauth2.id_token._fetch_certs", return_value={"test-key": self.public})
        certs.start()
        self.addCleanup(certs.stop)
        self.client = app.test_client()
        self.initial = self.client.get("/auth/session").get_json()

    def login(self, changes=None, client=None):
        client = client or self.client
        bootstrap = client.get("/auth/session").get_json()
        claims = {"iss": "https://accounts.google.com", "aud": os.environ["GOOGLE_CLIENT_ID"],
                  "iat": int(time.time()) - 1, "exp": int(time.time()) + 600,
                  "sub": "123456789", "email": "student@example.test", "email_verified": True,
                  "name": "Student", "nonce": bootstrap["nonce"], **(changes or {})}
        token = jwt.encode(self.signer, claims, key_id="test-key").decode()
        return client.post("/auth/google", json={"credential": token}, headers={"X-CSRF-Token": bootstrap["csrf_token"]})

    def test_study_and_provider_routes_require_authentication(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertIsNone(self.initial["user"])
        self.assertIsNone(self.initial["expires_in_seconds"])
        for path in ("/sources", "/questions", "/retrieve", "/answers", "/transcriptions"):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path).status_code, 401)
        self.assertEqual(self.client.get("/sources/current").status_code, 401)

    def test_google_signature_and_claims_create_an_opaque_session(self):
        response = self.login()
        self.assertEqual(response.status_code, 200, response.get_json())
        result = response.get_json()
        self.assertEqual(result["user"]["id"], "google:123456789")
        self.assertGreater(result["expires_in_seconds"], 0)
        self.assertLessEqual(result["expires_in_seconds"], 600)
        self.assertNotEqual(result["csrf_token"], self.initial["csrf_token"])
        self.assertNotEqual(result["nonce"], self.initial["nonce"])
        self.assertIn("HttpOnly", response.headers["Set-Cookie"])
        self.assertIn("SameSite=Lax", response.headers["Set-Cookie"])
        with self.client.session_transaction() as state:
            self.assertIn(state["auth_session_id"], auth_sessions)
            self.assertNotIn("email", state)
            self.assertNotIn("credential", state)
        restored = self.client.get("/auth/session")
        self.assertEqual(restored.get_json()["user"], result["user"])
        self.assertEqual(restored.headers["Cache-Control"], "no-store")

    def test_rejects_wrong_audience_issuer_expiry_nonce_or_identity(self):
        for change in ({"aud": "another-app"}, {"iss": "https://attacker.test"},
                       {"exp": int(time.time()) - 60}, {"nonce": "different-browser"},
                       {"nonce": None}, {"email_verified": False}, {"sub": ""}):
            with self.subTest(change=change):
                self.assertEqual(self.login(change).status_code, 401)
                self.assertFalse(auth_sessions)

    def test_forged_google_token_is_rejected(self):
        response = self.client.post("/auth/google", json={"credential": "forged.jwt.value"}, headers={"X-CSRF-Token": self.initial["csrf_token"]})
        self.assertEqual(response.status_code, 401)
        self.assertFalse(auth_sessions)

    def test_login_and_study_mutations_require_csrf(self):
        with patch("backend.auth.id_token.verify_oauth2_token") as verify:
            self.assertEqual(self.client.post("/auth/google", json={"credential": "anything"}).status_code, 403)
            verify.assert_not_called()
        result = self.login().get_json()
        self.assertEqual(self.client.post("/sources").status_code, 403)
        self.assertEqual(self.client.post("/auth/logout").status_code, 403)
        self.assertEqual(self.client.get("/sources/current").status_code, 204)
        self.assertEqual(self.client.post("/sources", headers={"X-CSRF-Token": result["csrf_token"]}).status_code, 400)

    def test_logout_revokes_even_a_replayed_old_cookie(self):
        result = self.login().get_json()
        old_cookie = self.client.get_cookie(app.config["SESSION_COOKIE_NAME"]).value
        response = self.client.post("/auth/logout", headers={"X-CSRF-Token": result["csrf_token"]})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["user"])
        self.assertFalse(auth_sessions)
        replay = app.test_client()
        replay.set_cookie(app.config["SESSION_COOKIE_NAME"], old_cookie)
        self.assertEqual(replay.get("/sources/current").status_code, 401)

    def test_expired_session_requires_a_new_google_sign_in(self):
        self.login()
        with self.client.session_transaction() as state:
            auth_sessions[state["auth_session_id"]]["expires_at"] = time.time() - 1
        self.assertEqual(self.client.post("/questions").status_code, 401)
        self.assertIsNone(self.client.get("/auth/session").get_json()["user"])

    def test_google_outage_does_not_open_a_session(self):
        with patch("backend.auth.id_token.verify_oauth2_token", side_effect=exceptions.TransportError("unreachable")):
            self.assertEqual(self.login().status_code, 503)
        self.assertFalse(auth_sessions)

    def test_unconfigured_google_is_reported_without_a_guest_bypass(self):
        with patch.dict(os.environ, {"GOOGLE_CLIENT_ID": ""}):
            self.assertIsNone(self.client.get("/auth/session").get_json()["google_client_id"])
            self.assertEqual(self.login().status_code, 503)
            self.assertEqual(self.client.get("/sources/current").status_code, 401)

    def test_ownership_uses_verified_google_subject_not_email_or_browser_owner(self):
        first = self.login().get_json()
        uploaded = self.client.post("/sources", data={"source_file": (io.BytesIO(b"Study material"), "notes.md")}, headers={"X-CSRF-Token": first["csrf_token"]})
        self.assertEqual(uploaded.status_code, 201)
        source_id = uploaded.get_json()["source_id"]
        # Same verified subject remains the owner even if its email changes.
        self.assertEqual(self.login({"email": "updated@example.test"}).status_code, 200)
        self.assertEqual(self.client.get(f"/sources/{source_id}").status_code, 200)
        self.assertEqual(self.login({"sub": "987654321"}).status_code, 200)
        with self.client.session_transaction() as state:
            state["source_owner"] = "google:123456789"
        self.assertEqual(self.client.get(f"/sources/{source_id}").status_code, 404)

    def test_production_session_cookie_can_be_secure(self):
        with patch.dict(app.config, {"SESSION_COOKIE_SECURE": True}):
            response = self.login()
            self.assertIn("Secure", response.headers["Set-Cookie"])

    def test_current_material_can_be_restored_after_signing_in_again(self):
        first = self.login().get_json()
        source = self.client.post("/sources", data={"source_file": (io.BytesIO(b"My notes"), "notes.md")}, headers={"X-CSRF-Token": first["csrf_token"]}).get_json()
        self.client.post("/auth/logout", headers={"X-CSRF-Token": first["csrf_token"]})
        self.login()
        self.assertEqual(self.client.get("/sources/current").get_json()["source_id"], source["source_id"])

    def test_malformed_and_oversized_credentials_are_rejected(self):
        headers = {"X-CSRF-Token": self.initial["csrf_token"]}
        for body in ({}, {"credential": ""}, {"credential": 42}, {"credential": "x" * 12001}):
            self.assertEqual(self.client.post("/auth/google", json=body, headers=headers).status_code, 400)
        response = self.client.post("/auth/google", json={"credential": "x" * 17000}, headers=headers)
        self.assertEqual(response.status_code, 413)
        self.assertTrue(response.is_json)
        self.assertEqual(self.client.post("/auth/google", json={}, headers={"X-CSRF-Token": "é"}).status_code, 403)


if __name__ == "__main__":
    unittest.main()
