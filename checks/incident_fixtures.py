"""Offline API observations. Real execution evidence is recorded separately."""
from backend.incidents.contracts import digest


def observation(files, scenario, tests):
    broken = 'available = conn.execute' in files['app.py']
    wrong = 'if True:' in files['app.py']
    rows = []
    for test in tests:
        statuses = test.get('expected_statuses', [201] * len(test['requests']))[:]
        fail = (broken and test['concurrent']) or wrong
        if fail:
            statuses = [201] * len(test['requests']) if broken else [409] * len(test['requests'])
        count = 2 if fail and broken else 0 if wrong else next((r['expected'] for r in test.get('db_checks', []) if r['column'] == '_count'), 1)
        after = {'bookings': {'count': count, 'rows': [], 'truncated': False}, 'inventory': {'count': 1, 'rows': [{'id':1,'seats': -1 if fail and broken else 1 if wrong or count == 0 else 0}], 'truncated': False}}
        rows.append({'name':test['name'],'concurrent':test['concurrent'],'responses':[{**request,'status':status,'response':'{}','milliseconds':1} for request,status in zip(test['requests'],statuses)],'database_before':{},'database_after':after,'trace':[],'logs':'Offline fixture'})
    from backend.incidents.contracts import validate_observations
    return validate_observations({'kind':'execution','files_sha256':digest(files),'experiments':rows},files,tests)


class ImmediateExecutor:
    def submit(self, function):
        function()
