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


if __name__=='__main__':
    unittest.main()
