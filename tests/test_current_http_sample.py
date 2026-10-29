"""Execute the customer Python HTTP example against controlled current entity responses."""
import io
import json
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
DOMAIN = '11111111-1111-4111-8111-111111111111'
ID = '33333333-3333-4333-8333-333333333333'


class CurrentHttpSampleTest(unittest.TestCase):
    def setUp(self):
        text = (ROOT / 'skills/shieldlabs-server/references/python.md').read_text()
        self.namespace = {}
        exec(re.search(r'```python\n(.*?)```', text, re.S).group(1), self.namespace)
        self.card = {'id': ID, 'domain_id': DOMAIN, 'type': 'identification',
                     'risk': {'state': 'ok', 'score': 15}, 'signals': {'state': 'ok', 'items': []}}

    def read(self, card):
        requests = []
        def open_response(request, timeout):
            requests.append(request)
            self.assertEqual(timeout, 5)
            return io.BytesIO(json.dumps({'data': card}).encode())
        with patch.dict(os.environ, {'SHIELDLABS_DOMAIN_ID': DOMAIN, 'SHIELDLABS_API_KEY': 'sec_test'}):
            with patch.dict(self.namespace, {'urlopen': open_response}):
                value = self.namespace['read_action'](ID)
        self.assertEqual(requests[0].full_url, f'https://account.shieldlabs.ai/api/v1/domains/{DOMAIN}/history/identifications/{ID}')
        return value

    def test_current_card_is_preserved(self):
        self.assertEqual(self.read(self.card), self.card)

    def test_unavailable_is_not_clean(self):
        for key in ('risk', 'signals'):
            with self.subTest(field=key):
                card = {**self.card, key: {'state': 'unavailable'}}
                self.assertIsNone(self.read(card))

    def test_wrong_identity_is_rejected(self):
        for key in ('id', 'domain_id'):
            with self.subTest(field=key):
                with self.assertRaisesRegex(ValueError, 'identity mismatch'):
                    self.read({**self.card, key: 'wrong'})
