"""Explicitly prepared booking application, not substituted for a student's upload."""
from pathlib import Path

BOOKING_FILE = Path(__file__).with_name('booking_app.py')
ATOMIC = '''        changed = conn.execute("UPDATE inventory SET seats = seats - 1 WHERE id = 1 AND seats > 0").rowcount
        if not changed:
            return 409, {"error": "Sold out"}'''
BROKEN = '''        available = conn.execute("SELECT seats FROM inventory WHERE id = 1").fetchone()[0]
        if available < 1:
            return 409, {"error": "Sold out"}
        time.sleep(0.15)
        conn.execute("UPDATE inventory SET seats = seats - 1 WHERE id = 1")'''


def project():
    return {'app.py': BOOKING_FILE.read_text(encoding='utf-8')}


def scenario():
    booking = lambda customer: {'method': 'POST', 'path': '/bookings', 'body': {'customer': customer}}
    return {'title': 'Two customers booked the last seat', 'description': 'There is one seat left. A pair of simultaneous booking requests should create exactly one booking. Reproduce the incident and explain why it happens.',
            'entrypoint': 'app.py', 'port': 8123, 'database': 'booking.sqlite3', 'tables': ['inventory', 'bookings'],
            'mutation': {'path': 'app.py', 'before': ATOMIC, 'after': BROKEN},
            'reproduction': {'name': 'Last seat, concurrent requests', 'concurrent': True, 'requests': [booking('Asha'), booking('Kabir')], 'expected_statuses': [201, 409], 'db_checks': [{'table': 'bookings', 'column': '_count', 'expected': 1}, {'table': 'inventory', 'column': 'seats', 'expected': [0]}]},
            'regressions': [
                {'name': 'A valid first booking succeeds', 'concurrent': False, 'requests': [booking('Mira')], 'expected_statuses': [201], 'db_checks': [{'table': 'bookings', 'column': '_count', 'expected': 1}]},
                {'name': 'Sequential requests cannot oversell', 'concurrent': False, 'requests': [booking('Dev'), booking('Tara')], 'expected_statuses': [201, 409], 'db_checks': [{'table': 'bookings', 'column': '_count', 'expected': 1}]},
                {'name': 'An invalid booking leaves the seat untouched', 'concurrent': False, 'requests': [{'method': 'POST', 'path': '/bookings', 'body': {}}], 'expected_statuses': [400], 'db_checks': [{'table': 'bookings', 'column': '_count', 'expected': 0}, {'table': 'inventory', 'column': 'seats', 'expected': [1]}]}
            ]}
