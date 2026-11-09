"""Migrate configured PostgreSQL before starting the production server."""
import os
from pathlib import Path

from dotenv import load_dotenv

from backend.database import database_enabled, get_database, close_pools, DatabaseUnavailable


def main():
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    if database_enabled():
        try:
            get_database().migrate()
        except DatabaseUnavailable:
            raise SystemExit("PostgreSQL migration failed. Check DATABASE_URL; the web server was not started.")
        finally:
            close_pools()
    os.execvp("gunicorn", ["gunicorn", "--config", "gunicorn.conf.py", "backend.app:app"])


if __name__ == "__main__":
    main()
