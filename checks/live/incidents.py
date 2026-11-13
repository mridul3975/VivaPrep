"""Opt-in real E2B check of the prepared incident. Creates three short-lived VMs."""
import json
from pathlib import Path
from dotenv import load_dotenv
from backend.incidents import demo, runtime
from backend.incidents.contracts import validate_scenario


def main():
    load_dotenv(Path(__file__).resolve().parents[2] / '.env')
    if not runtime.available():
        raise SystemExit('Add E2B_API_KEY privately to the root .env first. See INCIDENTS.md.')
    original, scenario = demo.project(), demo.scenario()
    broken = validate_scenario(scenario, original)
    tests = [scenario['reproduction'], *scenario['regressions']]
    try:
        before = runtime.execute(original, scenario, tests)
        failure = runtime.execute(broken, scenario, [scenario['reproduction']])
        after = runtime.execute(original, scenario, tests)
    except runtime.RuntimeUnavailable as error:
        raise SystemExit(str(error)) from error
    incident = failure['experiments'][0]
    oversold = sorted(row['status'] for row in incident['responses']) == [201,201] and incident['database_after'].get('bookings',{}).get('count') == 2
    if before['passed'] is not True or failure['passed'] is not False or after['passed'] is not True or not oversold:
        raise SystemExit('The live sandbox did not establish the expected original/failure/repair sequence. No success report written.')
    path = Path('.impeccable/review/incident-e2b-live.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'provider':'E2B','original':before,'failure':failure,'repair':after}, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Real E2B: original passed 4 checks, oversell reproduced, repair passed 4 checks. Sandbox shutdown requested after each batch.')
    print('Evidence saved privately to .impeccable/review/incident-e2b-live.json. This does not verify a deployed browser or real learner speech.')


if __name__ == '__main__':
    main()
