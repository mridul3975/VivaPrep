"""Running-app/Neon persistence check using one disposable, seeded identity.

Browser execution is covered separately by the sandbox UI checks. These test
observations are fixtures used only to verify saving, restart and ownership.
"""
import json
import secrets
import time
import uuid
from pathlib import Path
import requests
from backend.app import app
from backend.database import get_database, close_pools
from backend.debugging import SCENARIO_ID, STARTER, TESTS

checkpoint = Path('.impeccable/review/neon/debug-checkpoint.json')
prefix = 'google:debug-verification-'
store = get_database()
owner = None
try:
    resuming = checkpoint.exists()
    if resuming:
        saved = json.loads(checkpoint.read_text())
        owner, cookie, csrf = saved['owner'], saved['cookie'], saved['csrf']
    else:
        owner = prefix + uuid.uuid4().hex
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        store.save_login({'id':owner,'email':'debug-check@example.test','name':'Debug verification'},token,time.time()+3600)
        cookie = app.session_interface.get_signing_serializer(app).dumps({'auth_session_id':token,'csrf_token':csrf})
    assert owner.startswith(prefix)
    client = requests.Session()
    client.cookies.set(app.config['SESSION_COOKIE_NAME'],cookie)
    client.headers['X-CSRF-Token'] = csrf
    def call(method, path, status=200, **kwargs):
        response = client.request(method,'http://127.0.0.1:5000'+path,timeout=90,**kwargs)
        assert response.status_code == status, f'{method} {path}: HTTP {response.status_code}'
        print(f'{method} {path}: HTTP {response.status_code}',flush=True)
        return response.json() if response.content else None
    if not resuming:
        before = call('GET','/profile')['usage']['allowances']
        run = call('POST','/debug/runs',201,json={'scenario_id':SCENARIO_ID})
        url = '/debug/runs/'+run['id']
        assert len(call('POST',url+'/hint')['hints']) == 1
        code = STARTER.replace('minSeconds * 1000','minSeconds')
        report = {'tested_code':code,'results':[{'id':test['id'],'actual':test['expected'],'passed':True,'error':''} for test in TESTS]}
        result = call('PATCH',url,json={'code':code,'hypothesis':'The comparison mixes units.','explanation':'Both sides now use seconds.','test_result':report})
        assert result['complete']
        assert call('GET','/profile')['usage']['allowances'] == before
        checkpoint.write_text(json.dumps({'owner':owner,'cookie':cookie,'csrf':csrf,'run_id':run['id']}))
        checkpoint.chmod(0o600)
        print('Live Neon debugging save/hint/no-AI-usage passed. Restart before resume.',flush=True)
    else:
        url = '/debug/runs/'+saved['run_id']
        run = call('GET',url)
        assert run['complete'] and len(run['hints']) == 1
        assert run['code'] == STARTER.replace('minSeconds * 1000','minSeconds')
        assert call('GET','/debug/runs')['runs'][0]['id'] == run['id']
        changed = call('PATCH',url,json={'code':STARTER})
        assert not changed['tests_current'] and not changed['complete']
        call('DELETE',url,204)
        with store.connection() as conn:
            conn.execute('DELETE FROM repoviva.users WHERE id=%s',(owner,))
        checkpoint.unlink()
        Path('checks/debugging_neon_result.json').write_text(json.dumps({'date_ist':'2026-11-10','storage':'Neon production via running local Gunicorn app','create_save_hint_list_delete':'passed','actual_process_restart_restore':'passed','code_edit_invalidates_results':'passed','AI_quota_unchanged':'passed','fixture_cleanup':'completed','boundary':'Seeded disposable identity and test-observation fixtures. Actual browser test execution is proved separately; this is not live Google authentication or a certified coding assessment.'},indent=2)+'\n')
        print('Neon restart restoration, stale verdict and scoped cleanup passed.',flush=True)
except Exception:
    if owner and owner.startswith(prefix):
        with store.connection() as conn:
            conn.execute('DELETE FROM repoviva.users WHERE id=%s',(owner,))
        checkpoint.unlink(missing_ok=True)
    raise
finally:
    close_pools()
