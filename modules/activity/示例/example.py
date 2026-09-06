"""Local single-binding command-line example. The caller provides a per-binding lock."""
import argparse
import json
import os
from pathlib import Path
import tempfile
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cowmata_activity_aux import ActivityModule, Context, as_fusion_features


def main():
    parser = argparse.ArgumentParser(description='COWMATA activity module: raw V2 packet or no-data snapshot')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--packet', type=Path)
    mode.add_argument('--snapshot', action='store_true')
    mode.add_argument('--phase', choices=['calving', 'postpartum'])
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--now-ms', type=int, required=True)
    parser.add_argument('--received-ms', type=int)
    parser.add_argument('--offline-update-time', action='store_true')
    parser.add_argument('--cow')
    parser.add_argument('--device')
    parser.add_argument('--binding')
    parser.add_argument('--binding-start-ms', type=int)
    args = parser.parse_args()
    if args.state.exists():
        module = ActivityModule.from_state_json(args.state.read_text(encoding='utf-8'))
        # Never silently reuse another cow's state when binding arguments are supplied.
        from cowmata_activity_aux.protocol import device_key
        expected = {'cow':module.context.cow_id, 'device':module.context.device_id,
                    'binding':module.context.binding_id, 'binding_start_ms':module.context.binding_start_ms}
        for key,value in expected.items():
            supplied = getattr(args,key)
            if key == 'device' and supplied is not None:
                supplied = device_key(supplied)
            if supplied is not None and supplied != value:
                parser.error(f'{key} differs from persisted binding')
    else:
        if any(x is None for x in [args.cow,args.device,args.binding,args.binding_start_ms]):
            parser.error('new state requires --cow --device --binding --binding-start-ms')
        module = ActivityModule(Context(args.cow,args.device,args.binding,args.binding_start_ms))
    if args.packet:
        document = json.loads(args.packet.read_text(encoding='utf-8-sig'))
        if args.offline_update_time:
            if args.received_ms is not None:
                parser.error('use either --received-ms or --offline-update-time')
            received = document.get('update_time')
            source = 'json_update_proxy'
        else:
            if args.received_ms is None:
                parser.error('live processing requires --received-ms')
            received, source = args.received_ms, 'server_received'
        result = module.process_packet(document, received_at_ms=received,
            evaluated_at_ms=args.now_ms, receive_time_source=source)
    elif args.phase:
        result = module.set_phase(args.phase, at_ms=args.now_ms)
    else:
        result = module.snapshot(args.now_ms)
    args.state.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=args.state.parent,
                                     prefix=args.state.name+'.',suffix='.tmp',delete=False) as handle:
        handle.write(module.to_state_json())
        temporary = handle.name
    os.replace(temporary,args.state)
    print(json.dumps({'result':result,'fusion':as_fusion_features(result)},ensure_ascii=False,allow_nan=False,indent=2))


if __name__ == '__main__':
    main()
