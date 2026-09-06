"""Installed package data, shared packet semantics, and state continuity."""
import importlib.resources
import json
from pathlib import Path
import sys
import unittest

import jsonschema
from cowmata_activity_aux import ActivityModule, Context as ActivityContext
from cowmata_temperature_aux import TemperatureModule, Context as TemperatureContext

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'examples'))
from calving_evidence_demo import synthetic_packet


class IntegrationTests(unittest.TestCase):
    def modules(self):
        packet = synthetic_packet()
        binding = dict(cow_id='DEMO-COW', device_id=packet['device'],
                       binding_id='DEMO-BINDING', binding_start_ms=packet['create_time'])
        return packet, [
            ('cowmata_temperature_aux', TemperatureModule(TemperatureContext(**binding))),
            ('cowmata_activity_aux', ActivityModule(ActivityContext(**binding))),
        ]

    def test_same_packet_outputs_match_installed_schemas(self):
        packet, modules = self.modules()
        now = packet['create_time'] + 61000
        for package, module in modules:
            with self.subTest(package=package):
                result = module.process_packet(packet, received_at_ms=now, evaluated_at_ms=now)
                with importlib.resources.open_text(package, 'output.schema.json', encoding='utf-8') as handle:
                    schema = json.load(handle)
                jsonschema.validate(result, schema)
                json.dumps(result, allow_nan=False)

    def test_state_restore_preserves_future_snapshot(self):
        packet, modules = self.modules()
        now = packet['create_time'] + 61000
        for package, module in modules:
            with self.subTest(package=package):
                module.process_packet(packet, received_at_ms=now, evaluated_at_ms=now)
                restored = type(module).from_state_json(module.to_state_json())
                self.assertEqual(module.snapshot(now + 60000), restored.snapshot(now + 60000))

    def test_wrong_binding_rejected_without_state_change(self):
        packet, modules = self.modules()
        packet['device'] = 'WRONG'
        now = packet['create_time'] + 61000
        for package, module in modules:
            with self.subTest(package=package):
                before = module.to_state_json()
                with self.assertRaises(ValueError):
                    module.process_packet(packet, received_at_ms=now, evaluated_at_ms=now)
                self.assertEqual(before, module.to_state_json())


if __name__ == '__main__':
    unittest.main()
