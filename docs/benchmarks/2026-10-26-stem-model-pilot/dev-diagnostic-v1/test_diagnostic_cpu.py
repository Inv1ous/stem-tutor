"""CPU contracts: privacy, experiment isolation, real app payload capture and execution gates."""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent


class DiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / 'diagnostic.py'
        if not path.exists():
            return
        spec = importlib.util.spec_from_file_location('devdiag', path)
        cls.d = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.d
        spec.loader.exec_module(cls.d)

    def test_harness_exists(self):
        self.assertTrue((ROOT / 'diagnostic.py').is_file(), 'CPU harness is not implemented')

    def test_privacy_discards_thought_unknown_fields_and_token_ids(self):
        if not hasattr(self, 'd'):
            self.skipTest('Harness not implemented')
        clean, tail = self.d.sanitize({'message': {'content': 'Visible', 'thinking': 'PRIVATE'},
                                      'token_ids': [42], 'unknown': 'PRIVATE'}, '')
        self.assertEqual(clean, {'message': {'role': 'assistant', 'content': 'Visible', 'thinking': True}})
        self.assertNotIn('PRIVATE', json.dumps(clean))
        self.assertEqual(tail, 'Visible')

    def test_split_thought_delimiter_fails_closed(self):
        if not hasattr(self, 'd'):
            self.skipTest('Harness not implemented')
        _, tail = self.d.sanitize({'message': {'content': '<thi'}}, '')
        clean, _ = self.d.sanitize({'message': {'content': 'nk>leak'}}, tail)
        self.assertEqual(clean['message']['content'], '')
        self.assertIn('error', clean)

    def test_matrix_and_real_payload_capture_keep_c_d_identical_except_format(self):
        if not hasattr(self, 'd'):
            self.skipTest('Harness not implemented')
        fixtures = asyncio.run(self.d.build_fixtures())
        rows = fixtures['conditions']
        self.assertEqual([r['id'] for r in rows], ['python', 'A', 'B', 'C', 'D', 'mark', 'Deep'])
        payloads = {r['id']: r['payload'] for r in rows if r['id'] != 'python'}
        d = dict(payloads['D']); d.pop('format')
        self.assertEqual(payloads['C'], d)
        self.assertEqual(payloads['D']['messages'][-1]['content'], self.d.USER)
        self.assertEqual([m['role'] for m in payloads['A']['messages']], ['user'])
        self.assertIs(payloads['D']['think'], False)
        self.assertIs(payloads['Deep']['think'], True)
        self.assertEqual(payloads['Deep']['options']['num_predict'], 1024)
        self.assertEqual(payloads['mark']['format']['properties']['points']['minItems'], 2)
        for row in rows:
            self.assertNotIn('expected', row)
            self.assertNotIn('gold', row)

    def test_pair_assertion_rejects_changed_system(self):
        if not hasattr(self, 'd'):
            self.skipTest('Harness not implemented')
        a = {'format': {}, 'messages': [{'role': 'system', 'content': 'one'}]}
        b = {'messages': [{'role': 'system', 'content': 'two'}]}
        with self.assertRaises(AssertionError):
            self.d.assert_pair(b, a)

    def test_requires_explicit_root_go_and_new_output(self):
        if not hasattr(self, 'd'):
            self.skipTest('Harness not implemented')
        with self.assertRaises(ValueError):
            self.d.execution_gate(None, ROOT.parent / 'new-output')
        with self.assertRaises(ValueError):
            self.d.execution_gate('ROOT_GO', ROOT)

    def test_cpu_render_prefixes_are_source_evidence_only(self):
        if not hasattr(self, 'd'):
            self.skipTest('Harness not implemented')
        value = self.d.render_evidence([{'role': 'user', 'content': 'hello'}], False)
        self.assertTrue(value['equal'])
        self.assertTrue(value['source_derived_native'].endswith('<think>\n\n</think>\n\n'))
        self.assertFalse(value['actual_native_runtime_capture'])

    def test_cpu_fixture_preparation_never_imports_mlx_or_opens_a_socket(self):
        if not hasattr(self, 'd'):
            self.skipTest('Harness not implemented')
        from unittest.mock import patch
        with patch('asyncio.open_connection', side_effect=AssertionError('CPU preparation opened a socket')):
            asyncio.run(self.d.build_fixtures())
        self.assertFalse(any(name == 'mlx' or name.startswith('mlx.') for name in sys.modules))

    def test_invalid_marking_vector_remains_unavailable(self):
        if not hasattr(self, 'd'):
            self.skipTest('Harness not implemented')
        fixtures = asyncio.run(self.d.build_fixtures())
        row = next(r for r in fixtures['conditions'] if r['id'] == 'mark')
        raw = json.dumps({'points': [{'point': p, 'met': 'false', 'why': ''} for p in row['criteria']],
                          'feedback': ''})
        score = self.d.score(row, {'public_final': raw, 'finish_reason': 'stop'}, fixtures['gold'])
        self.assertFalse(score['marking_vector_available'])
        self.assertIsNone(score['marking_vector_correct'])


if __name__ == '__main__':
    unittest.main()
