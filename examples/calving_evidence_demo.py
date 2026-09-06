"""Synthetic V2 packet through both modules; this is not a fused alarm."""
import base64
import json

import numpy as np
from cowmata_activity_aux import ActivityModule, Context as ActivityContext
from cowmata_activity_aux import as_fusion_features as activity_features
from cowmata_activity_aux.protocol import FRAME_DTYPE
from cowmata_temperature_aux import TemperatureModule, Context as TemperatureContext
from cowmata_temperature_aux import as_fusion_features as temperature_features


def synthetic_packet():
    start = 1800000000000
    frames = np.zeros(3001, dtype=FRAME_DTYPE)
    frames['elapsed_ms'] = np.arange(len(frames)) * 20
    frames['values'][:, 0] = np.where(np.arange(len(frames)) % 2, 256, -256)
    frames['values'][:, 2] = 4096
    return {
        'uid': 'synthetic-demo-1', 'device': 'DEMO001', 'version': 2,
        'create_time': start,
        'imu': base64.b64encode(frames.tobytes()).decode('ascii'),
        'temperature': base64.b64encode(np.array([3800], dtype='<i2').tobytes()).decode('ascii'),
    }


def main():
    packet = synthetic_packet()
    binding = dict(cow_id='DEMO-COW', device_id=packet['device'],
                   binding_id='DEMO-BINDING', binding_start_ms=packet['create_time'])
    now = packet['create_time'] + 61000
    temperature = TemperatureModule(TemperatureContext(**binding))
    activity = ActivityModule(ActivityContext(**binding))
    t = temperature.process_packet(packet, received_at_ms=now, evaluated_at_ms=now)
    a = activity.process_packet(packet, received_at_ms=now, evaluated_at_ms=now)
    print(json.dumps({
        'synthetic': True, 'fusion_implemented': False,
        'temperature_quality': t['quality_status'],
        'activity_quality': a['quality_status'],
        'temperature': temperature_features(t, now_ms=now),
        'activity': activity_features(a, now_ms=now),
    }, ensure_ascii=False, allow_nan=False, indent=2))


if __name__ == '__main__':
    main()
