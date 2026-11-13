"""Trusted sandbox-side launcher. No local variables are collected by line tracing."""
import json
import os
from pathlib import Path
import runpy
import sys
import threading

root = Path.cwd().resolve()
prefix = str(root) + '/'
seen = set()
lock = threading.Lock()


def trace(frame, event, _arg):
    filename = frame.f_code.co_filename
    if not filename.startswith(prefix):
        return None
    if event != 'line':
        return trace
    item = (filename[len(prefix):], frame.f_lineno, threading.get_ident())
    with lock:
        if item not in seen and len(seen) < 180:
            seen.add(item)
            sys.stderr.write('RVTRACE:' + json.dumps({'path': item[0], 'line': item[1], 'thread': item[2]}) + '\n')
            sys.stderr.flush()
    return trace


threading.settrace(trace)
sys.settrace(trace)
sys.path.insert(0, str(root))
sys.path.insert(0, str((root / sys.argv[1]).parent))
runpy.run_path(str(root / sys.argv[1]), run_name='__main__')
