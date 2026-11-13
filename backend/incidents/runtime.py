"""Remote-only execution boundary. No subprocess, eval or user code runs on Flask."""
import json
import logging
import os
from pathlib import Path
from backend.incidents.contracts import validate_observations


class RuntimeUnavailable(RuntimeError):
    pass


def available():
    return bool(os.getenv('E2B_API_KEY'))


def execute(files, scenario, experiments):
    if not available():
        raise RuntimeUnavailable('The isolated runner is not configured on this server. Your saved work is unchanged.')
    from e2b import Sandbox
    sandbox = None
    try:
        sandbox = Sandbox.create(template=os.getenv('E2B_TEMPLATE_ID') or None, timeout=65,
            api_key=os.environ['E2B_API_KEY'], allow_internet_access=False, envs={}, request_timeout=15)
        sandbox.commands.run('mkdir -p /runner /work && chmod 755 /runner /work', user='root', timeout=5)
        for name in ('worker.py', 'launch.py'):
            sandbox.files.write('/runner/' + name, Path(__file__).with_name(name).read_text(), user='root')
        sandbox.files.write('/runner/input.json', json.dumps({'files': files, 'scenario': scenario, 'experiments': experiments}), user='root')
        sandbox.commands.run('chmod 600 /runner/input.json && python3 /runner/worker.py', user='root', timeout=45, request_timeout=50)
        size = sandbox.commands.run('wc -c < /runner/output.json', user='root', timeout=3)
        if not size.stdout.strip().isdigit() or int(size.stdout.strip()) > 400000:
            raise RuntimeUnavailable('Execution evidence exceeded its limit; choose a smaller experiment.')
        result = json.loads(sandbox.files.read('/runner/output.json', user='root'))
        return validate_observations(result, files, experiments)
    except RuntimeUnavailable:
        raise
    except Exception as error:
        logging.getLogger(__name__).warning('Incident sandbox failed: %s', type(error).__name__)
        raise RuntimeUnavailable('The isolated runner could not finish. No new test result was saved. Retry or check the sandbox setup.') from error
    finally:
        if sandbox is not None:
            try:
                sandbox.kill()
            except Exception:
                # The provider TTL still kills it; never replace the outcome with a cleanup verdict.
                logging.getLogger(__name__).warning('Sandbox cleanup failed; provider timeout remains active.')
