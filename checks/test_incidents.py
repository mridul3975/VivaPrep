import io
import json
import os
import unittest
import zipfile
from unittest.mock import patch, Mock
from backend.incidents import demo
from backend.incidents.bundle import read_project
from backend.incidents.contracts import digest, experiment, validate_observations, validate_scenario
from backend.incidents.intelligence import investigation
from backend.incidents.runtime import RuntimeUnavailable, execute
from checks.incident_fixtures import observation, ImmediateExecutor
from checks import test_postgres as pg


class IncidentBoundaryTests(unittest.TestCase):
    def test_zip_never_extracts_paths_links_secrets_or_oversized_files(self):
        for name, content in [('../app.py','x'),('.env','secret'),('app.py','x'*33000),('app.py',b'\x00')]:
            stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w') as archive: archive.writestr(name,content)
            with self.subTest(name=name), self.assertRaises(ValueError): read_project(stream.getvalue(),'project.zip')
        self.assertIn('app.py',read_project(demo.project()['app.py'].encode(),'app.py'))

    def test_experiments_cannot_be_remote_urls_or_arbitrary_commands(self):
        for path in ('https://example.com','//example.com','/\nHost: example.com','/\\example.com'):
            with self.assertRaises(ValueError): experiment({'name':'probe','concurrent':False,'requests':[{'method':'GET','path':path,'body':None}]},[],expectations=False)
        files, scenario=demo.project(),demo.scenario()
        self.assertNotEqual(validate_scenario(scenario,files),files)
        scenario['mutation']['before']='does not occur'
        with self.assertRaises(ValueError): validate_scenario(scenario,files)

    def test_controlled_change_preserves_uploaded_crlf_line_endings(self):
        files={'app.py':demo.project()['app.py'].replace('\n','\r\n')}
        changed=validate_scenario(demo.scenario(),files)['app.py']
        self.assertEqual(changed.count('\n'),changed.count('\r\n'))
        self.assertIn('available = conn.execute',changed)

    def test_remote_runtime_disables_egress_inherits_no_keys_and_always_kills(self):
        files, scenario=demo.project(),demo.scenario(); tests=[scenario['reproduction']]
        packet=observation(files,scenario,tests)
        sandbox=Mock(); sandbox.commands.run.return_value.stdout='100'; sandbox.files.read.return_value=json.dumps(packet)
        with patch.dict(os.environ,{'E2B_API_KEY':'private-fixture'}), patch('e2b.Sandbox.create',return_value=sandbox) as create:
            self.assertTrue(execute(files,scenario,tests)['passed'])
            self.assertIs(create.call_args.kwargs['allow_internet_access'],False)
            self.assertEqual(create.call_args.kwargs['envs'],{})
            self.assertNotIn('private-fixture',str(sandbox.files.write.call_args_list))
            sandbox.kill.assert_called_once()
        sandbox.reset_mock(); sandbox.commands.run.side_effect=RuntimeError('provider timeout')
        with patch.dict(os.environ,{'E2B_API_KEY':'private-fixture'}), patch('e2b.Sandbox.create',return_value=sandbox),self.assertRaises(RuntimeUnavailable): execute(files,scenario,tests)
        sandbox.kill.assert_called_once()

    def test_score_is_recomputed_and_cannot_come_from_a_claimed_pass(self):
        files,scenario=demo.project(),demo.scenario(); tests=[scenario['reproduction']]
        packet=observation(files,scenario,tests); packet['passed']=True; packet['experiments'][0]['passed']=True
        packet['experiments'][0]['responses'][0]['status']=500
        self.assertFalse(validate_observations(packet,files,tests)['passed'])
        packet['files_sha256']='stale'
        with self.assertRaises(ValueError): validate_observations(packet,files,tests)

    def test_hypothesis_invalid_citation_is_withheld(self):
        source=demo.project(); state={'files':source,'scenario':demo.scenario(),'broken_evidence':{}}
        answer={'action':'discuss','response':'Both reads overlapped.','citations':[{'path':'not-uploaded.py','line_start':1,'line_end':2}], 'experiment':{}}
        with patch('backend.incidents.intelligence.json_completion',return_value=answer),self.assertRaises(ValueError): investigation('Both requests read the last seat.',state)

    def test_mixed_language_imperative_becomes_reviewable_experiment_without_changing_explicit_targets(self):
        state={'files':demo.project(),'scenario':demo.scenario(),'broken_evidence':{}}
        with patch('backend.incidents.intelligence.json_completion') as model:
            planned=investigation('दो booking requests एक साथ भेजो।',state)
            self.assertEqual(planned['action'],'experiment');self.assertTrue(planned['experiment']['concurrent']);model.assert_not_called()
        answer={'action':'discuss','response':'Inspect the other endpoint.','citations':[],'experiment':{}}
        with patch('backend.incidents.intelligence.json_completion',return_value=answer) as model:
            investigation('Send two DELETE requests to /users at the same time',state)
            model.assert_called_once()
        for instruction in ('Do not send two booking requests at the same time','दो booking requests एक साथ मत भेजो','Send three booking requests at the same time','Send two delete requests to /bookings at the same time','Send two booking requests with customer names Alice and Bob at the same time'):
            with self.subTest(instruction=instruction),patch('backend.incidents.intelligence.json_completion',return_value=answer) as model:
                self.assertEqual(investigation(instruction,state)['action'],'discuss');model.assert_called_once()


@unittest.skipUnless(pg.TEST_URL,'Requires isolated repoviva_test PostgreSQL.')
class IncidentRouteTests(unittest.TestCase):
    setUpClass=classmethod(pg.PostgresTests.setUpClass.__func__)
    tearDownClass=classmethod(pg.PostgresTests.tearDownClass.__func__)
    setUp=pg.PostgresTests.setUp

    def start(self):
        with patch('backend.incidents.routes.runtime.available',return_value=True), patch('backend.incidents.routes.runtime.execute',side_effect=observation), patch('backend.incidents.routes.executor',ImmediateExecutor()):
            response=self.client.post('/incidents',json={'example':True})
        self.assertEqual(response.status_code,202,response.get_json())
        return self.client.get('/incidents/'+response.get_json()['id']).get_json()

    def test_missing_provider_never_runs_or_charges_and_owned_work_stays_private(self):
        with patch('backend.incidents.routes.runtime.available',return_value=False),patch('backend.incidents.routes.runtime.execute') as run:
            self.assertEqual(self.client.post('/incidents',json={'example':True}).status_code,503);run.assert_not_called()
        self.assertEqual(self.client.get('/incidents').get_json()['usage']['used'],0)
        lab=self.start();self.assertEqual(lab['status'],'ready');self.assertTrue(lab['baseline']['passed']);self.assertFalse(lab['broken_evidence']['passed'])
        self.assertEqual(self.other.get('/incidents/'+lab['id']).status_code,404)
        self.assertEqual(self.other.get('/incidents').get_json()['labs'],[])

    def test_patch_replay_regression_and_transcript_draft_survive_and_stale_results_do_not_pass(self):
        lab=self.start();url='/incidents/'+lab['id']
        draft={'text':'Dono requests same seat dekhte hain.','original':'Dono requests same seat dekhte hain.','reviewed':True}
        patched=self.client.patch(url,json={'files':lab['original_files'],'instruction_draft':draft})
        self.assertEqual(patched.status_code,200)
        plan=self.client.post(url+'/plan',json={'instruction':'Test my fix'}).get_json()['plan']
        with patch('backend.incidents.routes.runtime.available',return_value=True),patch('backend.incidents.routes.runtime.execute',side_effect=observation),patch('backend.incidents.routes.executor',ImmediateExecutor()):
            self.assertEqual(self.client.post(url+'/execute',json={'plan_id':plan['id'],'score':100}).status_code,202)
        finished=self.client.get(url).get_json();self.assertTrue(finished['solved'])
        from checks.auth_fixtures import authenticated_client
        restored=authenticated_client(pg.app,'google:db-one').get(url).get_json()
        self.assertEqual(restored['instruction_draft'],draft)
        stale=self.client.patch(url,json={'files':lab['files']}).get_json()
        self.assertFalse(stale['solved']);self.assertFalse(stale['current_execution'])
        self.assertEqual(self.client.post(url+'/execute',json={'plan_id':plan['id']}).status_code,409)

    def test_provider_failure_refunds_releases_job_and_preserves_patch(self):
        lab=self.start();url='/incidents/'+lab['id'];code=lab['files']
        before=self.client.get('/incidents').get_json()['usage']['used']
        plan=self.client.post(url+'/plan',json={'instruction':'Replay the incident'}).get_json()['plan']
        with patch('backend.incidents.routes.runtime.available',return_value=True),patch('backend.incidents.routes.runtime.execute',side_effect=RuntimeUnavailable('Runner down')),patch('backend.incidents.routes.executor',ImmediateExecutor()):
            self.assertEqual(self.client.post(url+'/execute',json={'plan_id':plan['id']}).status_code,202)
        saved=self.client.get(url).get_json();self.assertEqual(saved['files'],code);self.assertFalse(saved['solved']);self.assertIn('Runner down',saved['error'])
        self.assertEqual(self.client.get('/incidents').get_json()['usage']['used'],before)
        with self.store.connection() as conn: self.assertIsNone(conn.execute('SELECT lease_token FROM repoviva.incident_labs WHERE id=%s',(lab['id'],)).fetchone()['lease_token'])
        with patch.dict(os.environ,{'SHARED_INCIDENT_LIMIT':'2'}),patch('backend.incidents.routes.runtime.available',return_value=True):
            self.assertEqual(self.client.post('/incidents',json={'example':True}).status_code,429)

    def test_account_removal_cannot_reset_the_shared_sandbox_budget(self):
        lab=self.start()
        with self.store.connection() as conn:
            conn.execute('DELETE FROM repoviva.users WHERE id=%s',('google:db-one',))
            self.assertIsNone(conn.execute('SELECT owner FROM repoviva.incident_usage').fetchone()['owner'])
            self.assertIsNone(conn.execute('SELECT id FROM repoviva.incident_labs WHERE id=%s',(lab['id'],)).fetchone())
        with patch.dict(os.environ,{'SHARED_INCIDENT_LIMIT':'1'}),patch('backend.incidents.routes.runtime.available',return_value=True):
            self.assertEqual(self.other.post('/incidents',json={'example':True}).status_code,429)

    def test_transcript_confirmation_quota_and_csrf_are_enforced(self):
        lab=self.start();url='/incidents/'+lab['id']
        self.assertEqual(self.client.post(url+'/plan',json={'instruction':'Run','original_transcript':'Run','reviewed':False}).status_code,400)
        with patch.dict(os.environ,{'DAILY_INCIDENT_LIMIT':'1'}),patch('backend.incidents.routes.runtime.available',return_value=True),patch('backend.incidents.routes.runtime.execute') as run:
            self.assertEqual(self.client.post('/incidents',json={'example':True}).status_code,429);run.assert_not_called()
        csrf=self.client.environ_base.pop('HTTP_X_CSRF_TOKEN')
        try:self.assertEqual(self.client.post(url+'/plan',json={'instruction':'Test my fix'}).status_code,403)
        finally:self.client.environ_base['HTTP_X_CSRF_TOKEN']=csrf

    def test_guest_upgrade_keeps_inflight_project_and_usage(self):
        import secrets
        import time
        from checks.auth_fixtures import authenticated_client
        queued=[]
        class Deferred:
            def submit(self, function): queued.append(function)
        guest=authenticated_client(pg.app,'guest:incident-upgrade')
        with patch('backend.incidents.routes.runtime.available',return_value=True),patch('backend.incidents.routes.runtime.execute',side_effect=observation),patch('backend.incidents.routes.executor',Deferred()):
            response=guest.post('/incidents',json={'example':True})
            self.assertEqual(response.status_code,202,response.get_json())
            identifier=response.get_json()['id']
            self.store.save_login({'id':'google:incident-upgraded','name':'Fixture reviewer','email':'reviewer@example.test'},secrets.token_urlsafe(32),time.time()+3600,guest_owner='guest:incident-upgrade')
            queued[0]()
        upgraded=authenticated_client(pg.app,'google:incident-upgraded')
        result=upgraded.get('/incidents/'+identifier)
        self.assertEqual(result.status_code,200,result.get_json())
        self.assertEqual(result.get_json()['status'],'ready')
        self.assertEqual(upgraded.get('/incidents').get_json()['usage']['used'],1)
