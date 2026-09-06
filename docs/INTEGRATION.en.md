# Calving evidence integration

[中文说明](INTEGRATION.md) · [Module APIs](MODULES.en.md)

The two independently installable packages expose their own module, Context and fusion-feature adapter. Supply identical binding identity to both Context types, but do not interchange those types. Maintain separate state per cow/device binding and serialize processing per binding.

Use Unix millisecond timestamps and distinguish acquisition, server receipt and evaluation time. Live alerts cannot be backdated before data reception. Save full module output together with compact fusion features so quality, provenance and freshness are retained.

Each module validates its own input; cross-module atomic transactions are not provided. Log failures separately. Stage enums differ, so explicitly map business phases using the original module guides.

The demo places outputs side by side; it does not implement weighted fusion, probabilities, ETA, a unified alert state machine or a behavior-event adapter. Missing evidence does not veto other modalities. Timer snapshots must not be counted as new observations that retrigger alerts.

Fusion development: define real-time available fields → freeze independent cow/calving splits → replay → calibrate thresholds → evaluate continuous negatives and lead time. Full calf expulsion (T0) and first visible fetal part are separate anchors and must be reported separately.
