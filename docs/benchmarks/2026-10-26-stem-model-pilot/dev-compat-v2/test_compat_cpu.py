"""CPU regressions for the exact-alias diagnostic transport and schema round trip."""
import asyncio
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('compat_diag', ROOT/'diagnostic.py')
d = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = d
spec.loader.exec_module(d)


class CompatTests(unittest.TestCase):
    def test_exact_alias_document_generation_only(self):
        source = {'model':'stem-tutor-qwen35:pilot', 'messages':[{'role':'user','content':'hello'}],
                  'format': {'type':'object'}, 'think':False, 'options':{'seed':42}}
        expected = copy.deepcopy(source); expected.pop('format')
        self.assertEqual(d.compat_payload(source, document_chat=True), expected)
        self.assertIn('format', source)
        for model, messages, document in [('other-model',source['messages'],True),
                                           (source['model'],[],True),
                                           (source['model'],source['messages'],False)]:
            payload = {**source,'model':model,'messages':messages}
            self.assertEqual(d.compat_payload(payload, document_chat=document), payload)

    def test_real_app_matrix_preserves_original_users_and_full_schema(self):
        fixtures = asyncio.run(d.build_fixtures())
        self.assertEqual(len(fixtures['conditions']),8)
        source = {r['id']:r for r in map(json.loads,(d.DEV/'test.jsonl').read_text().splitlines())}
        for row in fixtures['conditions']:
            self.assertNotIn('expected',row)
            if row['id'] == 'mark':
                self.assertIn('format',row['payload'])
                continue
            full = copy.deepcopy(row['app_payload']); full.pop('format')
            self.assertEqual(row['payload'],full)
            self.assertEqual([m['role'] for m in full['messages']],['system','user'])
            self.assertIn('Return exactly one JSON object matching this schema',full['messages'][0]['content'])
            if row['id'] in source:
                self.assertEqual(full['messages'][-1]['content'],source[row['id']]['messages'][0]['content'])

    def test_old_failure_reproduces_without_service_calls(self):
        value = asyncio.run(d.prior_mark_regression())
        self.assertFalse(value['v1_roundtrip_payload_equal'])
        self.assertEqual(value['changed_fields'],['messages[1].content'])
        self.assertEqual(value['prompt_lengths'],[1655,1655])

    def test_factory_roundtrip_keeps_embedded_prompt_and_property_order(self):
        fixture = asyncio.run(d.build_fixtures())
        loaded = json.loads(d.dump(fixture['conditions']))
        row = next(r for r in loaded if r['id']=='mark')
        schema = d.runtime_schema(row)
        self.assertEqual(list(schema['properties']),['points','feedback'])
        actual = asyncio.run(d.capture_app(row['prompt'],schema=schema,speech=False))
        self.assertEqual(actual,row['app_payload'])
        self.assertEqual(d.compat_payload(actual,document_chat=False),row['payload'])

    def test_deep_real_boolean_full_speech_and_fixed_budget(self):
        row = asyncio.run(d.build_fixtures())['conditions'][-1]
        self.assertEqual(row['id'],'Deep')
        self.assertIs(row['payload']['think'],True)
        self.assertEqual(row['max_tokens'],4096)
        self.assertEqual(row['seconds'],180)
        self.assertIn('speech',row['app_payload']['format']['required'])
        self.assertNotIn('format',row['payload'])

    def test_cpu_preparation_has_no_socket_or_mlx_import(self):
        with patch('asyncio.open_connection',side_effect=AssertionError('CPU socket')):
            asyncio.run(d.build_fixtures())
            asyncio.run(d.prior_mark_regression())
        self.assertFalse(any(k=='mlx' or k.startswith('mlx.') for k in sys.modules))

    def test_public_sanitizer_discards_private_and_split_delimiter(self):
        clean,tail = d.sanitize({'message':{'content':'Visible','thinking':'PRIVATE'},'token_ids':[1]},'')
        self.assertNotIn('PRIVATE',json.dumps(clean))
        self.assertNotIn('token_ids',clean)
        _,tail = d.sanitize({'message':{'content':'<thi'}},'')
        clean,_ = d.sanitize({'message':{'content':'nk>PRIVATE'}},tail)
        self.assertEqual(clean['message']['content'],'')
        self.assertIn('error',clean)

    def test_invalid_mark_still_exposes_no_vector(self):
        fixture = asyncio.run(d.build_fixtures())
        row = next(r for r in fixture['conditions'] if r['id']=='mark')
        raw = json.dumps({'points':[{'point':p,'met':'false','why':''} for p in row['criteria']], 'feedback':''})
        score = d.score(row,{'public_final':raw,'finish_reason':'stop'},fixture['gold'])
        self.assertFalse(score['marking_vector_available'])
        self.assertIsNone(score['marking_vector_correct'])

    def test_gate_requires_new_output_and_root_authorization(self):
        with self.assertRaises(ValueError):d.execution_gate(None,ROOT.parent/'new-v2-output')
        with self.assertRaises(ValueError):d.execution_gate('ROOT_GO',ROOT)


if __name__ == '__main__':unittest.main()
