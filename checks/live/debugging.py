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
from checks.debug_fixtures import CODE

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
        source = call('POST','/sources',201,files={'source_file': ('debug-tax.js', CODE.encode(), 'text/plain')})
        run = call('POST','/debug/runs',201,json={'source_id':source['source_id']})
        assert run['scenario']['execution_mode'] == 'javascript'
        url = '/debug/runs/'+run['id']
        assert len(call('POST',url+'/hint')['hints']) == 1
        code = run['scenario']['reference_code']
        report = {'tested_code':code,'results':[{'id':test['id'],'actual':test['expected'],'passed':True,'error':''} for test in run['scenario']['tests']]}
        result = call('PATCH',url,json={'code':code,'hypothesis':'Inspect the arithmetic in this uploaded function.','explanation':'Restoring the reference behavior matches the practice cases.','test_result':report})
        assert result['complete']
        assert call('GET','/profile')['usage']['allowances']['questions']['used'] == before['questions']['used'] + 1
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text(json.dumps({'owner':owner,'cookie':cookie,'csrf':csrf,'run_id':run['id'],'code':code,'starter':run['scenario']['starter_code']}))
        checkpoint.chmod(0o600)
        print('Live source-derived Neon debugging save/hint/generation allowance passed. Restart before resume.',flush=True)
    else:
        url = '/debug/runs/'+saved['run_id']
        run = call('GET',url)
        assert run['complete'] and len(run['hints']) == 1
        assert run['code'] == saved['code']
        assert call('GET','/debug/runs')['runs'][0]['id'] == run['id']
        changed = call('PATCH',url,json={'code':saved['starter']})
        assert not changed['tests_current'] and not changed['complete']
        call('DELETE',url,204)
        with store.connection() as conn:
            conn.execute('DELETE FROM repoviva.users WHERE id=%s',(owner,))
        checkpoint.unlink()
        Path('checks/source_debugging_neon_result.json').write_text(json.dumps({'storage':'Neon production via running local Gunicorn app','source_derived_create_save_hint_list_delete':'passed','actual_process_restart_restore':'passed','code_edit_invalidates_results':'passed','generation_charges_one_question_allowance':'passed','fixture_cleanup':'completed','boundary':'Seeded disposable identity and test-observation fixtures. Live Groq generation; actual browser test execution is proved separately. This is not live Google authentication or a certified coding assessment.'},indent=2)+'\n')
        print('Neon restart restoration, stale verdict and scoped cleanup passed.',flush=True)
except Exception:
    if owner and owner.startswith(prefix):
        with store.connection() as conn:
            conn.execute('DELETE FROM repoviva.users WHERE id=%s',(owner,))
        checkpoint.unlink(missing_ok=True)
    raise
finally:
    close_pools()
