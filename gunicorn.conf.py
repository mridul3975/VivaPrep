"""Single-process deployment: turn state and locks live in this worker."""
import os

bind = f"0.0.0.0:{int(os.environ.get('PORT', '8000'))}"
workers = 1
worker_class = "gthread"
threads = 4
timeout = 90
graceful_timeout = 90
reload = False
accesslog = "-"
errorlog = "-"
