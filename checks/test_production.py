import re
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app import app


class ProductionTests(unittest.TestCase):
    def test_built_index_assets_and_api_are_served_together(self):
        with app.test_client() as client:
            index = client.get("/")
            self.addCleanup(index.close)
            self.assertEqual(index.status_code, 200)
            self.assertIn("text/html", index.content_type)
            asset_path = re.search(r'src="(/assets/[^\"]+\.js)"', index.get_data(as_text=True)).group(1)
            asset = client.get(asset_path)
            self.addCleanup(asset.close)
            self.assertEqual(asset.status_code, 200)
            self.assertIn("immutable", asset.headers["Cache-Control"])
            self.assertEqual(client.get("/health").get_json(), {"status": "ok"})
            self.assertEqual(client.post("/answers", json={}).status_code, 400)

    def test_missing_build_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory, patch("backend.app.FRONTEND_DIST", Path(directory)):
            with app.test_client() as client:
                self.assertEqual(client.get("/").status_code, 503)

    def test_api_and_missing_assets_never_return_index_html(self):
        with app.test_client() as client:
            for path in ("/assets/missing.js", "/api/missing", "/.env", "/backend/app.py", "/assets/../index.html"):
                response = client.get(path)
                self.addCleanup(response.close)
                self.assertEqual(response.status_code, 404, path)
                self.assertTrue(response.is_json, path)
            response = client.get("/answers")
            self.assertEqual(response.status_code, 405)
            self.assertTrue(response.is_json)

    def test_production_configuration_uses_one_worker(self):
        config = runpy.run_path("gunicorn.conf.py")
        self.assertEqual(config["workers"], 1)
        self.assertFalse(config["reload"])
        self.assertFalse(app.debug)


if __name__ == "__main__":
    unittest.main()
