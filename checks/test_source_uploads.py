import io
import unittest
from unittest.mock import patch

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from backend.app import app
from backend.evidence.documents import MAX_FILE_BYTES, MAX_TEXT_BYTES
from backend.evidence.uploads import sources, SOURCE_TTL_SECONDS


def pdf_bytes(pages, encrypted=False):
    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=612, height=792)
        if text is not None:
            font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                     NameObject('/Subtype'): NameObject('/Type1'),
                                     NameObject('/BaseFont'): NameObject('/Helvetica')})
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
            stream = DecodedStreamObject()
            stream.set_data(f'BT /F1 12 Tf 72 720 Td ({text}) Tj ET'.encode('ascii'))
            page[NameObject('/Contents')] = writer._add_object(stream)
    if encrypted:
        writer.encrypt('test-password', algorithm='RC4-128')
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class SourceUploadTests(unittest.TestCase):
    def setUp(self):
        sources.clear()
        self.client = app.test_client()

    def tearDown(self):
        sources.clear()

    def upload(self, data, filename='example.py', client=None):
        response = (client or self.client).post('/sources', data={'source_file': (io.BytesIO(data), filename)})
        self.addCleanup(response.close)
        self.addCleanup(response.request.environ['wsgi.input'].close)
        return response

    def test_source_lines_blanks_indentation_and_boundaries(self):
        lines = ['def example():', '', '    return 40'] + [f'# line {n}' for n in range(4, 42)]
        response = self.upload(('\r\n'.join(lines) + '\r\n').encode())
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data['line_count'], 41)
        self.assertEqual([(s['start_line'], s['end_line']) for s in data['snippets']], [(1, 40), (41, 41)])
        self.assertEqual(data['snippets'][0]['content'][1:3], ['', '    return 40'])
        self.assertEqual(data['snippets'][0]['citation_type'], 'lines')
        self.assertEqual(self.client.get('/sources/' + data['source_id']).status_code, 200)

    def test_browser_sessions_cannot_read_or_delete_each_others_upload(self):
        first = self.upload(b'first = 1').get_json()
        other = app.test_client()
        self.assertEqual(other.get('/sources/' + first['source_id']).status_code, 404)
        self.assertEqual(other.delete('/sources/' + first['source_id']).status_code, 404)
        second = self.upload(b'second = 2', client=other).get_json()
        self.assertNotEqual(first['source_id'], second['source_id'])
        self.assertEqual(self.client.get('/sources/' + second['source_id']).status_code, 404)

    def test_replacement_and_removal_are_scoped_to_owner(self):
        first = self.upload(b'a = 1').get_json()
        second = self.upload(b'b = 2').get_json()
        self.assertEqual(self.client.get('/sources/' + first['source_id']).status_code, 404)
        self.assertEqual(len(sources), 1)
        self.assertEqual(self.client.delete('/sources/' + second['source_id']).status_code, 204)
        self.assertEqual(len(sources), 0)

    def test_expired_source_is_removed(self):
        source_id = self.upload(b'value = 1').get_json()['source_id']
        sources[source_id]['created'] -= SOURCE_TTL_SECONDS
        self.assertEqual(self.client.get('/sources/' + source_id).status_code, 404)
        self.assertNotIn(source_id, sources)

    def test_upload_code_is_data_and_filename_cannot_choose_a_server_path(self):
        response = self.upload(b"raise RuntimeError('This must never execute')\n", '../../private/example.py')
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertNotIn('/', data['filename'])
        self.assertIn('raise RuntimeError', data['snippets'][0]['content'][0])

    def test_missing_binary_unsupported_empty_and_oversized_files(self):
        self.assertEqual(self.client.post('/sources').status_code, 400)
        for data, name, status in [(b'', 'empty.txt', 400), (b'\xff\xfe', 'bad.py', 400),
                                   (b'abc\x00def', 'binary.txt', 400), (b'hello', 'program.exe', 415),
                                   (b'not a PDF', 'fake.pdf', 415),
                                   (b'a' * (MAX_TEXT_BYTES + 1), 'large.txt', 413),
                                   (b'a' * (MAX_FILE_BYTES + 65537), 'large.pdf', 413)]:
            with self.subTest(name=name):
                self.assertEqual(self.upload(data, name).status_code, status)

    def test_pdf_citations_preserve_original_page_numbers(self):
        response = self.upload(pdf_bytes(['First page evidence', None, 'Third page evidence']), 'notes.pdf')
        self.assertEqual(response.status_code, 201, response.get_json())
        document = response.get_json()
        self.assertEqual(document['page_count'], 3)
        self.assertEqual([s['page'] for s in document['snippets']], [1, 3])
        self.assertTrue(all(s['start_line'] is None for s in document['snippets']))
        self.assertIn('First page evidence', document['snippets'][0]['content'][0])
        self.assertTrue(document['warnings'])

    def test_encrypted_and_textless_pdf_errors(self):
        for data, expected in [(pdf_bytes(['Secret'], encrypted=True), 'Password-protected'),
                               (pdf_bytes([None]), 'OCR'), (pdf_bytes([None] * 21), '20 pages')]:
            response = self.upload(data, 'notes.pdf')
            self.assertEqual(response.status_code, 400, response.get_json())
            self.assertIn(expected, response.get_json()['error'])

    def test_storage_capacity_is_bounded(self):
        self.upload(b'first = 1')
        with patch('backend.evidence.uploads.MAX_SOURCES', 1):
            self.assertEqual(self.upload(b'second = 2', client=app.test_client()).status_code, 503)
            self.assertEqual(self.upload(b'replacement = 3').status_code, 201)


if __name__ == '__main__':
    unittest.main()
