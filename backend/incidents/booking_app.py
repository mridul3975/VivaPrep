"""Prepared one-seat booking app. Only executed in an incident sandbox."""
import json
import os
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DATABASE = 'booking.sqlite3'


def reserve(customer):
    if not isinstance(customer, str) or not customer.strip():
        return 400, {'error': 'A customer name is required'}
    with sqlite3.connect(DATABASE, timeout=3) as conn:
        changed = conn.execute("UPDATE inventory SET seats = seats - 1 WHERE id = 1 AND seats > 0").rowcount
        if not changed:
            return 409, {"error": "Sold out"}
        conn.execute('INSERT INTO bookings(customer) VALUES (?)', (customer,))
    return 201, {'booked': customer}


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.reply(200, {'ready': True}) if self.path == '/health' else self.reply(404, {'error': 'Not found'})

    def do_POST(self):
        if self.path != '/bookings':
            self.reply(404, {'error': 'Not found'})
            return
        try:
            body = json.loads(self.rfile.read(min(4096, int(self.headers.get('Content-Length', '0')))))
        except (ValueError, TypeError):
            self.reply(400, {'error': 'Invalid JSON'})
            return
        status, result = reserve(body.get('customer') if isinstance(body, dict) else None)
        self.reply(status, result)


if __name__ == '__main__':
    with sqlite3.connect(DATABASE) as conn:
        conn.executescript('CREATE TABLE inventory(id INTEGER PRIMARY KEY, seats INTEGER); INSERT INTO inventory VALUES (1,1); CREATE TABLE bookings(id INTEGER PRIMARY KEY, customer TEXT);')
    ThreadingHTTPServer(('127.0.0.1', int(os.environ.get('PORT', '8123'))), Handler).serve_forever()
