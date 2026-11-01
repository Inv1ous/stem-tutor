"""CPU-only regressions; no native socket, GPU import or model registration."""
import asyncio
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PATH = Path(__file__).with_name('native_probe_v1.py')
spec = importlib.util.spec_from_file_location('native_probe_under_test', PATH)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
probe.production()


class CatalogueRestoration(unittest.TestCase):
    def catalogue(self, preexisting=False):
        alias = probe.ALIAS
        maps = [dict(other=f'keep-{i}') for i in range(4)]
        if preexisting:
            for i, mapping in enumerate(maps):
                mapping[alias] = (None, 'preexisting lifetime', 1234, 5678)[i]
        return SimpleNamespace(LOCAL_MODELS=maps[0], TEXT_MODELS={alias, 'other'} if preexisting else {'other'},
                               KEEP_ALIVE=maps[1], CONTEXT_LENGTH=maps[2], MAX_CONTEXT_LENGTH=maps[3])

    def test_normal_exit_restores_all_five_absent_entries(self):
        catalogue = self.catalogue()
        before = deepcopy(vars(catalogue))
        with probe.temporary_catalogue(catalogue):
            self.assertIn(probe.ALIAS, catalogue.TEXT_MODELS)
            self.assertEqual(catalogue.CONTEXT_LENGTH[probe.ALIAS], 8192)
        self.assertEqual(vars(catalogue), before)

    def test_exception_exit_restores_all_five_absent_entries(self):
        catalogue = self.catalogue()
        before = deepcopy(vars(catalogue))
        with self.assertRaisesRegex(RuntimeError, 'setup failed'):
            with probe.temporary_catalogue(catalogue):
                raise RuntimeError('setup failed')
        self.assertEqual(vars(catalogue), before)

    def test_preexisting_values_and_membership_survive_normal_and_exception(self):
        for fail in (False, True):
            with self.subTest(fail=fail):
                catalogue = self.catalogue(preexisting=True)
                before = deepcopy(vars(catalogue))
                try:
                    with probe.temporary_catalogue(catalogue):
                        self.assertEqual(catalogue.LOCAL_MODELS[probe.ALIAS], 'STEM Tutor Qwen3.5 pilot (probe only)')
                        if fail:
                            raise RuntimeError('simulated setup')
                except RuntimeError:
                    pass
                self.assertEqual(vars(catalogue), before)

    def test_failure_during_first_mutation_also_restores_every_entry(self):
        class FailOnce(dict):
            failed = False
            def __setitem__(self, key, value):
                super().__setitem__(key, value)
                if not self.failed:
                    self.failed = True
                    raise RuntimeError('first mutation failed after write')
        catalogue = self.catalogue(preexisting=True)
        catalogue.LOCAL_MODELS = FailOnce(catalogue.LOCAL_MODELS)
        before = {key: dict(value) if isinstance(value, dict) else set(value)
                  for key, value in vars(catalogue).items()}
        with self.assertRaisesRegex(RuntimeError, 'first mutation failed'):
            with probe.temporary_catalogue(catalogue):
                self.fail('body must not execute')
        self.assertEqual(vars(catalogue), before)

    def test_execute_constructor_failure_restores_real_imported_globals(self):
        from tutor_app import local_models, tutor_ai, stem_training
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'stem-tutor-training').mkdir()
            frozen = root/'frozen'; frozen.mkdir()
            (frozen/'manifest.json').write_text('{}')
            native = root/'native.json'; native.write_text('{"runner":"mlx"}')
            catalogue = self.catalogue(preexisting=True)
            before = deepcopy(vars(catalogue))
            class SetupFailed(Exception):
                pass
            def fail_setup(**kwargs):
                self.assertEqual(local_models.CONTEXT_LENGTH[probe.ALIAS], 8192)
                raise SetupFailed('injected constructor failure before any native socket')
            fake_monitor = SimpleNamespace(initial={}, latest={})
            with patch.multiple(local_models, **vars(catalogue)), \
                 patch.object(probe, 'SSD', root), patch.object(probe, 'ROOT', frozen), \
                 patch.object(probe, 'MODEL_MANIFEST', native), \
                 patch.object(stem_training, 'ResourceMonitor', return_value=fake_monitor), \
                 patch.object(tutor_ai, 'TutorAI', side_effect=fail_setup):
                try:
                    with self.assertRaises(SetupFailed):
                        asyncio.run(probe.execute(SimpleNamespace(output=root/'new-output', mode='fast'),
                                                  {'options_status': 'requested only'}, []))
                    for name, expected in before.items():
                        self.assertEqual(getattr(local_models, name), expected, name)
                finally:
                    # Also clean deliberately broken baseline state in this test process.
                    for name, value in before.items():
                        target = getattr(local_models, name)
                        target.clear(); target.update(value)


class MarkingAvailability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = [json.loads(line) for line in (probe.ROOT/'inputs.jsonl').read_text().splitlines()]
        cls.case = next(row for row in rows if row['id']=='native-mark-oxidation_omission')
        cls.gold = next(json.loads(line) for line in (probe.ROOT/'gold.jsonl').read_text().splitlines()
                        if json.loads(line)['id']==cls.case['id'])

    def score(self, mutation=None):
        value = deepcopy(self.gold['expected'])
        if mutation:
            mutation(value)
        return probe.score_case(self.case, json.dumps(value), 'stop', self.gold)

    def assert_unavailable(self, result):
        self.assertIsNone(result['marking_labels_equal'])
        self.assertIs(result['marking_vector_available'], False)
        self.assertIsNone(result['marking_decision_vector'])
        self.assertIsNone(result['marking_vector_correct'])

    def test_integer_one_zero_are_not_boolean_gold(self):
        result = self.score(lambda v: [p.update(met=i) for p,i in zip(v['points'], [1,0])])
        self.assertIs(result['raw_schema_valid'], False)
        self.assert_unavailable(result)

    def test_string_flags_are_unavailable(self):
        self.assert_unavailable(self.score(lambda v: v['points'][0].update(met='true')))

    def test_missing_met_flag_is_unavailable(self):
        self.assert_unavailable(self.score(lambda v: v['points'][1].pop('met')))

    def test_missing_feedback_envelope_is_unavailable(self):
        self.assert_unavailable(self.score(lambda v: v.pop('feedback')))

    def test_extra_envelope_key_cannot_credit_correct_vector(self):
        self.assert_unavailable(self.score(lambda v: v.update(unexpected='extra')))

    def test_missing_requested_why_is_unavailable(self):
        self.assert_unavailable(self.score(lambda v: v['points'][0].pop('why')))

    def test_wrong_criteria_are_unavailable(self):
        result=self.score(lambda v: v['points'][0].update(point='Altered criterion'))
        self.assertIs(result['exact_criteria_order'], False)
        self.assert_unavailable(result)

    def test_reordered_criteria_are_unavailable(self):
        self.assert_unavailable(self.score(lambda v: v['points'].reverse()))

    def test_wrong_points_container_is_unavailable(self):
        self.assert_unavailable(self.score(lambda v: v.update(points={'met':True})))

    def test_valid_correct_vector_is_available_and_correct(self):
        result=self.score()
        self.assertIs(result['raw_schema_valid'], True)
        self.assertIs(result['marking_envelope_valid'], True)
        self.assertIs(result['marking_vector_available'], True)
        self.assertEqual(result['marking_decision_vector'], [True,False])
        self.assertIs(result['marking_vector_correct'], True)
        self.assertIs(result['marking_labels_equal'], True)

    def test_valid_wrong_decisions_are_available_and_incorrect(self):
        result=self.score(lambda v: v['points'][0].update(met=False))
        self.assertIs(result['marking_vector_available'], True)
        self.assertIs(result['marking_vector_correct'], False)
        self.assertIs(result['marking_labels_equal'], False)


class RecorderMerge(unittest.TestCase):
    def test_explicit_event_fields_override_repeated_context_fields(self):
        context={'id':'context-case', 'turn':1, 'schema':{'private_to_context':True}}
        event={'type':'turn_result', 'case_id':'event-case', 'turn':2, 'elapsed_seconds':.25}
        before_context, before_event=deepcopy(context),deepcopy(event)
        record=probe.contextual_event(context,event,9.0)
        self.assertEqual(record, event)
        self.assertEqual(context,before_context)
        self.assertEqual(event,before_event)

    def test_missing_event_fields_receive_context_defaults(self):
        record=probe.contextual_event({'id':'case', 'turn':3}, {'type':'control_request'}, 2.0)
        self.assertEqual(record,{'case_id':'case','turn':3,'elapsed_seconds':2.0,'type':'control_request'})


class NormalExecuteRecording(unittest.TestCase):
    """Real TutorAI/LocalAI/decoder; only HTTP transport and OS probes are stubbed."""
    def execute_one(self, completion):
        from tutor_app import local_models, local_ai, stem_training
        case=next(json.loads(line) for line in (probe.ROOT/'inputs.jsonl').read_text().splitlines()
                  if json.loads(line)['id']=='005c35460c204a0c150cd248')
        gold=next(json.loads(line) for line in (probe.ROOT/'gold.jsonl').read_text().splitlines()
                  if json.loads(line)['id']==case['id'])
        mode='deep' if completion=='stop' else 'fast'
        sentinel='HIDDEN_THOUGHT_MUST_NEVER_BE_RETAINED'
        public=json.dumps(gold['expected']) if completion=='stop' else '{"blocks":[{"kind":"paragraph","text":"unfinished'
        counters=dict(total_duration=100000000,load_duration=1000000,prompt_eval_duration=2000000,
                      eval_duration=90000000,prompt_eval_count=100,prompt_eval_cached_count=0,
                      eval_count=20 if completion=='stop' else 4096)
        loaded=False
        requests=[]
        async def transport(self,payload,timeout,path='/api/chat',**kwargs):
            nonlocal loaded
            requests.append((path,deepcopy(payload)))
            def decoded(value):
                return self._decode(json.dumps(value).encode())
            if path=='/api/version':
                yield decoded({'version':'0.40.11'})
            elif path=='/api/ps':
                yield decoded({'models':[{'name':probe.NAME,'size_vram':1024}] if loaded else []})
            elif not payload.get('messages'):
                unloading=payload.get('keep_alive')==0
                loaded=not unloading
                yield decoded({'done':True,'done_reason':'unload' if unloading else 'load',
                               'message':{'content':''}})
            else:
                self_test.assertEqual(payload['format'],case['schema'])
                self_test.assertIs(payload['think'],mode=='deep')
                if mode=='deep':
                    yield decoded({'message':{'thinking':sentinel,'content':''}, 'context':[123456]})
                yield decoded({'message':{'content':public}, 'context':[789012]})
                yield decoded({'done':True,'done_reason':completion,'message':{'content':''},**counters})
        self_test=self
        fake_monitor=SimpleNamespace(initial={'pressure':1},latest={'pressure':1},check=lambda:None)
        before={name:deepcopy(getattr(local_models,name)) for name in
                ('LOCAL_MODELS','TEXT_MODELS','KEEP_ALIVE','CONTEXT_LENGTH','MAX_CONTEXT_LENGTH')}
        with TemporaryDirectory() as temp:
            root=Path(temp); (root/'stem-tutor-training').mkdir()
            frozen=root/'frozen'; frozen.mkdir()
            (frozen/'manifest.json').write_text('{}')
            (frozen/'gold.jsonl').write_text(json.dumps(gold)+'\n')
            native=root/'manifests-v2/ollama.com/library/stem-tutor-qwen35/pilot'
            native.parent.mkdir(parents=True); native.write_text('{"runner":"mlx"}')
            output=root/'result'
            with patch.object(probe,'SSD',root), patch.object(probe,'ROOT',frozen), \
                 patch.object(probe,'MODEL_MANIFEST',native), patch.object(local_models,'ROOT',root), \
                 patch.object(local_ai.LocalAI,'_http_events',transport), \
                 patch.object(stem_training,'ResourceMonitor',return_value=fake_monitor), \
                 patch('subprocess.check_output',return_value='Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free: 400000.\nPages inactive: 0.\nPages speculative: 0.\n'), \
                 patch('asyncio.open_connection',side_effect=AssertionError('CPU test must never open native socket')):
                asyncio.run(probe.execute(SimpleNamespace(output=output,mode=mode),
                                          {'options_status':'requested only'},[case]))
            events=[json.loads(line) for line in (output/'public-events.jsonl').read_text().splitlines()]
            receipt=json.loads((output/'receipt.json').read_text())
            scores=json.loads((output/'scores.json').read_text())
            text=(output/'public-events.jsonl').read_text()
            for name,old in before.items():
                self.assertEqual(getattr(local_models,name),old,name)
            self.assertNotIn(sentinel,text)
            self.assertNotIn('123456',text)
            self.assertNotIn('789012',text)
            self.assertNotIn('"thinking"',text)
            self.assertFalse(loaded,'owned candidate must be unloaded by final cleanup')
            self.assertEqual(receipt['cleanup'],'candidate released or no candidate loaded')
            self.assertEqual(receipt['state'],'completed_requires_manual_review')
            self.assertEqual(receipt['completed_turns'],1)
            self.assertNotIn('scoring_error',receipt)
            self.assertEqual(len(scores),1)
            self.assertTrue(any(not payload.get('messages') and payload.get('keep_alive')==0
                                for path,payload in requests if path=='/api/chat'))
            turn_events=[e for e in events if e['type']=='turn_result']
            self.assertEqual(len(turn_events),1)
            turn=turn_events[0]
            self.assertEqual(turn['case_id'],case['id'])
            self.assertEqual(turn['id'],case['id'])
            self.assertEqual(turn['turn'],1)
            self.assertEqual(turn['actual_api_counters'],counters)
            self.assertEqual(turn['missing_api_counters'],[])
            self.assertEqual(turn['public_final'],public)
            return turn,scores[0]['scores']

    def test_normal_chat_completion_records_scores_and_cleans_up(self):
        turn,score=self.execute_one('stop')
        self.assertTrue(turn['app_ok'])
        self.assertTrue(turn['thinking_observed'])
        self.assertIsNotNone(turn['first_rendered_block_seconds'])
        self.assertTrue(score['raw_schema_valid'])
        self.assertTrue(score['decoder_finish'])
        self.assertTrue(score['delivery_gate'])

    def test_length_failed_model_completion_is_recorded_and_scored(self):
        turn,score=self.execute_one('length')
        self.assertFalse(turn['app_ok'])
        self.assertIsNotNone(turn['error'])
        self.assertEqual(turn['finish_reason'],'length')
        self.assertIsNone(turn['first_rendered_block_seconds'])
        self.assertFalse(score['raw_schema_valid'])
        self.assertFalse(score['decoder_finish'])
        self.assertFalse(score['delivery_gate'])


if __name__=='__main__':
    unittest.main()
