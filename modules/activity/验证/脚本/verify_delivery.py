"""Verify the packaged import, full-output schema, and executable CLI/state example.

This delivery-only check uses jsonschema from the verification environment.
jsonschema is not a runtime dependency of cowmata_activity_aux.
"""
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import jsonschema
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from cowmata_activity_aux import ActivityModule, Context

HERE=Path(__file__).resolve().parents[2]
OUT=HERE/'验证/结果'
installed=HERE/'验证/临时环境/install_check'
schema=json.loads((HERE/'cowmata_activity_aux/output.schema.json').read_text(encoding='utf-8'))
validator=jsonschema.Draft7Validator(schema)
validator.check_schema(schema)
count=0
with (OUT/'逐包完整输出.jsonl').open(encoding='utf-8') as handle:
    for line in handle:
        validator.validate(json.loads(line));count+=1
with (OUT/'原始包实测审计.csv').open(encoding='utf-8-sig',newline='') as handle:
    first=next(csv.DictReader(handle))
packet=Path(first['source_path'])
doc=json.loads(packet.read_text(encoding='utf-8-sig'))
context=Context(first['cow_id'],doc['device'],'delivery-check',doc['create_time'])
m=ActivityModule(context)
validator.validate(m.snapshot(doc['create_time']))
r=m.process_packet(doc,received_at_ms=doc['update_time'],receive_time_source='json_update_proxy')
validator.validate(r)
validator.validate(m.process_packet(doc,received_at_ms=doc['update_time']))
validator.validate(m.snapshot(doc['update_time']+2*3600000))
validator.validate(m.set_phase('postpartum',at_ms=doc['update_time']+2*3600000))
schema_checks=count+5

with tempfile.TemporaryDirectory(prefix='delivery_check_',dir=installed.parent) as temp:
    # -I excludes CWD and PYTHONPATH; import must come from the pip-installed copy.
    script='''
import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import cowmata_activity_aux as pkg
from cowmata_activity_aux import ActivityModule,Context
installed=Path(sys.argv[1]).resolve()
assert installed in Path(pkg.__file__).resolve().parents
doc=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8-sig'))
m=ActivityModule(Context(sys.argv[3],doc['device'],'installed-check',doc['create_time']))
r=m.process_packet(doc,received_at_ms=doc['update_time'],receive_time_source='json_update_proxy')
assert r['input_status']=='ACCEPTED'
assert (Path(pkg.__file__).parent/'output.schema.json').exists()
assert ActivityModule.from_state_json(m.to_state_json()).snapshot(doc['update_time'])['features']==r['features']
print(json.dumps({'version':pkg.VERSION,'import_path':pkg.__file__,'raw_packet_accepted':True,'state_restore':True}))
'''
    p=subprocess.run([sys.executable,'-I','-X','utf8','-c',script,str(installed),str(packet),first['cow_id']],
                     cwd=temp,text=True,encoding='utf-8',capture_output=True,check=True)
    install_report=json.loads(p.stdout)
    state=Path(temp)/'state.json'
    command=[sys.executable,'-X','utf8',str(HERE/'示例/example.py'),'--packet',str(packet),'--state',str(state),
             '--now-ms',str(doc['update_time']),'--offline-update-time','--cow',first['cow_id'],
             '--device',doc['device'],'--binding','cli-check','--binding-start-ms',str(doc['create_time'])]
    p=subprocess.run(command,cwd=temp,text=True,encoding='utf-8',capture_output=True,check=True)
    initial=json.loads(p.stdout)
    validator.validate(initial['result'])
    assert initial['result']['input_status']=='ACCEPTED'
    original_state=state.read_bytes()
    snap_command=[sys.executable,'-X','utf8',str(HERE/'示例/example.py'),'--snapshot','--state',str(state),
                  '--now-ms',str(doc['update_time'])]
    p=subprocess.run(snap_command,cwd=temp,text=True,encoding='utf-8',capture_output=True,check=True)
    snap=json.loads(p.stdout)
    validator.validate(snap['result'])
    assert snap['result']['features']==initial['result']['features']
    assert not snap['result']['new_activity_evidence']
    bad=subprocess.run(snap_command+['--cow','DIFFERENT_COW'],cwd=temp,text=True,encoding='utf-8',capture_output=True)
    assert bad.returncode!=0 and state.read_bytes()==original_state
    cli_report={'first_raw_packet':True,'restored_snapshot':True,'wrong_binding_rejected_without_state_change':True}

report={'schema_checked_outputs':schema_checks+2,'independent_install':install_report,'cli':cli_report}
(OUT/'delivery_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
