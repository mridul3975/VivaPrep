"""Keep migration traffic direct and integration fixtures off hosted databases."""
import os
import unittest
from unittest.mock import patch

from flask import Flask
from backend.database import DatabaseUnavailable, get_database


class DatabaseConfigTests(unittest.TestCase):
    def setUp(self):
        self.pooled = "postgresql://user:fixture@ep-test-pooler.example.test/db"
        self.direct = "postgresql://user:fixture@ep-test.example.test/db"
        environment = patch.dict(os.environ, {
            "DATABASE_URL": self.pooled, "DATABASE_URL_UNPOOLED": self.direct,
        })
        environment.start()
        self.addCleanup(environment.stop)

    def test_application_and_migrations_use_their_respective_endpoints(self):
        with patch("backend.database._store") as store:
            get_database()
            store.assert_called_with(self.pooled)
            get_database(migration=True)
            store.assert_called_with(self.direct)

    def test_local_database_needs_only_one_url(self):
        with patch.dict(os.environ, {"DATABASE_URL_UNPOOLED": ""}), patch("backend.database._store") as store:
            get_database(migration=True)
            store.assert_called_once_with(self.pooled)

    def test_explicit_test_override_never_uses_hosted_migration_url(self):
        test_app = Flask(__name__)
        test_app.config["DATABASE_URL_OVERRIDE"] = "postgresql://localhost/repoviva_test"
        with test_app.app_context(), patch("backend.database._store") as store:
            get_database(migration=True)
            store.assert_called_once_with(test_app.config["DATABASE_URL_OVERRIDE"])
            test_app.config["DATABASE_URL_OVERRIDE"] = ""
            with self.assertRaises(DatabaseUnavailable):
                get_database(migration=True)
