"""One-packet CLI with persistent state. Serialize calls for each binding."""
import argparse
import json
import os
from pathlib import Path
import tempfile

import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cowmata_temperature_aux import TemperatureModule, Context, PacketError


def save_state(module, destination):
    """Atomic replacement; the caller must prevent concurrent binding writers."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(destination.parent),
            prefix=destination.name + ".",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temp_path = Path(stream.name)
            stream.write(module.to_state_json())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temp_path), str(destination))
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--packet", type=Path, help="Existing sensor JSON")
    action.add_argument(
        "--snapshot", action="store_true", help="Timer without a new packet"
    )
    action.add_argument("--phase", choices=["calving", "postpartum", "inactive"])
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--now-ms", required=True, type=int)
    parser.add_argument("--received-ms", type=int)
    parser.add_argument("--cow")
    parser.add_argument("--device")
    parser.add_argument("--binding")
    parser.add_argument("--binding-start-ms", type=int)
    args = parser.parse_args()
    if args.packet and args.received_ms is None:
        parser.error("--packet requires --received-ms (server receipt time)")
    if args.state.exists():
        module = TemperatureModule.from_state_json(
            args.state.read_text(encoding="utf-8")
        )
        for name, field in [
            ("cow", "cow_id"),
            ("device", "device_id"),
            ("binding", "binding_id"),
            ("binding_start_ms", "binding_start_ms"),
        ]:
            value = getattr(args, name)
            if value is not None and value != getattr(module.context, field):
                parser.error("Existing state belongs to a different " + field)
    else:
        if not all([args.cow, args.device, args.binding, args.binding_start_ms]):
            parser.error(
                "First call requires --cow --device --binding --binding-start-ms"
            )
        module = TemperatureModule(
            Context(args.cow, args.device, args.binding, args.binding_start_ms)
        )
    try:
        if args.packet:
            obj = json.loads(args.packet.read_text(encoding="utf-8-sig"))
            output = module.process_packet(
                obj, received_at_ms=args.received_ms, evaluated_at_ms=args.now_ms
            )
        elif args.phase:
            output = module.set_phase(args.phase, at_ms=args.now_ms)
        else:
            output = module.snapshot(args.now_ms)
    except PacketError as exc:
        parser.exit(2, str(exc) + "\n")
    save_state(module, args.state)
    print(json.dumps(output, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
