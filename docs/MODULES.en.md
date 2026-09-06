# Decision module guide

## Temperature

Package `cowmata_temperature_aux` version 0.6.0. Create a `TemperatureModule` with its own `Context(cow_id, device_id, binding_id, binding_start_ms)`. Ingest a packet using `process_packet(packet, received_at_ms=..., evaluated_at_ms=...)`, then call `as_fusion_features(result, now_ms=...)`.

The output includes evidence score/grade, quality and decaying freshness weight. Grade is not a calibrated calving probability. `eta_hours` and horizon probabilities are not predictions. This module does not independently issue urgent calving alerts.

Source-of-truth details: [original technical guide](../modules/temperature/说明/技术说明.md), [schema](../modules/temperature/cowmata_temperature_aux/output.schema.json), [CLI example](../modules/temperature/示例/example.py).

## Activity

Package `cowmata_activity_aux` version 1.0.0. Its `ActivityModule`, `Context` and `as_fusion_features` are separate types/functions with the same binding identity supplied by the caller. It ingests V2 IMU packets and produces activity ratios, reference quality, coverage and evidence freshness. Low coverage or insufficient baseline is unavailable evidence, not a negative calving result.

Source-of-truth details: [original technical guide](../modules/activity/说明/技术说明.md), [schema](../modules/activity/cowmata_activity_aux/output.schema.json), [CLI example](../modules/activity/示例/example.py).

## Minimal actual execution

```python
from cowmata_temperature_aux import TemperatureModule, Context, as_fusion_features

module = TemperatureModule(Context("cow", "device", "binding", 1800000000000))
# packet and times come from the acquisition/receipt system.
# result = module.process_packet(packet, received_at_ms=received, evaluated_at_ms=now)
# features = as_fusion_features(result, now_ms=now)
```

Run `python examples/calving_evidence_demo.py` for an executable synthetic packet through both modules. Persist each module with `to_state_json()` and restore with its class's `from_state_json()`. Serialize calls per binding; no cross-module transaction is claimed. Stage names differ between modules, so follow the original guides rather than forwarding one shared string.

## Evidence and limitations

The imported activity report uses development data (10 cows, 500 packets). Its reproducibility checks are not independent predictive accuracy. The referenced historical temperature validation directory and complete activity raw-packet directory were not supplied. This repository preserves these boundaries and does not label software tests as new calving validation. See [migration](MIGRATION.md) and [software checks](VERIFICATION.md).
