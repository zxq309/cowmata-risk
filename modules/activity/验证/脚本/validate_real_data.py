"""Recompute from raw V2 JSON, then join calving labels solely for evaluation."""
import argparse
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from cowmata_activity_aux import ActivityModule, Context, Config, as_fusion_features


HERE = Path(__file__).resolve().parents[2]


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows):
    with Path(path).open('w',encoding='utf-8-sig',newline='') as handle:
        writer = csv.DictWriter(handle,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def evaluate(rows, labels, event_field):
    per = []
    for cow in sorted({r['cow_id'] for r in rows}):
        delivery = labels[(cow,'犊牛完全娩出')]
        hoof = labels[(cow,'露蹄')]
        g = [r for r in rows if r['cow_id']==cow and r['evaluated_at_ms'] < delivery]
        target = [r for r in g if delivery-6*3600000 <= r['evaluated_at_ms'] < hoof]
        hits = [r for r in target if r[event_field]]
        background = [r for r in g if r['evaluated_at_ms'] < delivery-6*3600000 and r['usable_for_fusion']]
        late = [r for r in g if r[event_field] and r['evaluated_at_ms'] >= hoof]
        per.append({'cow_id':cow,'early_hit':bool(hits),'late_hit':bool(late),
            'eligible_updates':sum(r['usable_for_fusion'] for r in target),
            'background_alerts':sum(r[event_field] for r in background),
            'background_observed_hours':sum(r['packet_valid_seconds']/3600 for r in background),
            'first_early_lead_delivery_hours':(delivery-hits[0]['evaluated_at_ms'])/3600000 if hits else None,
            'first_early_lead_hoof_hours':(hoof-hits[0]['evaluated_at_ms'])/3600000 if hits else None})
    hours = sum(r['background_observed_hours'] for r in per)
    totals = {'cows':len(per),'early_hits':sum(r['early_hit'] for r in per),
        'eligible_cows':sum(r['eligible_updates']>0 for r in per),
        'late_hits':sum(r['late_hit'] for r in per),
        'background_alerts':sum(r['background_alerts'] for r in per),
        'background_observed_hours':hours,
        'background_alerts_per24_observed_hours':sum(r['background_alerts'] for r in per)/hours*24 if hours else None}
    return per,totals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root',type=Path,default=HERE.parent/'正常数据')
    parser.add_argument('--labels',type=Path,default=HERE.parent/'温度数据集/CSV数据/产犊标注.csv')
    parser.add_argument('--reference-v1',type=Path,default=HERE.parent/'分析输出/20260906_活动量产犊对齐_v1')
    parser.add_argument('--reference-v2',type=Path,default=HERE.parent/'分析输出/20260906_活动量优化_v2')
    parser.add_argument('--out',type=Path,default=HERE/'验证/结果')
    args = parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    state_out=args.out/'状态快照'
    state_out.mkdir(parents=True,exist_ok=True)
    start = time.perf_counter()
    inventory = []
    for cow_dir in sorted(p for p in args.data_root.iterdir() if p.is_dir()):
        parts = cow_dir.name.split('-')
        if len(parts)<2:
            raise ValueError('expected device-cow-site directory: '+str(cow_dir))
        device,cow = parts[:2]
        for path in sorted(cow_dir.rglob('*.json')):
            raw_bytes = path.read_bytes()
            doc = json.loads(raw_bytes.decode('utf-8-sig'))
            inventory.append({'cow':cow,'device':device,'path':path,
                'create_ms':doc['create_time'],'received_ms':doc['update_time'],
                'sha256':hashlib.sha256(raw_bytes).hexdigest()})
    print('raw files',len(inventory),'cows',len({r['cow'] for r in inventory}),flush=True)
    if not inventory:
        raise ValueError('no V2 JSON files found')
    if args.reference_v1.exists():
        prior = {str((args.data_root.parent/row['source_path']).resolve()):row for row in read_csv(args.reference_v1/'数据包审计.csv')}
        if set(prior) != {str(p['path'].resolve()) for p in inventory}:
            raise AssertionError('current raw file set differs from v1 audit')
        for p in inventory:
            assert p['sha256']==prior[str(p['path'].resolve())]['source_sha256'], str(p['path'])
    else:
        prior = None
    results=[]; audits=[]; restored_count=0; snapshot_checks=0; duplicate_checks=0
    payloads = (args.out/'逐包完整输出.jsonl').open('w',encoding='utf-8')
    try:
        for cow in sorted({r['cow'] for r in inventory}):
            packets=sorted([r for r in inventory if r['cow']==cow],key=lambda r:(r['received_ms'],r['create_ms']))
            module=ActivityModule(Context(cow,packets[0]['device'],f'replay-{cow}',min(p['create_ms'] for p in packets)))
            for i,p in enumerate(packets):
                raw_bytes=p['path'].read_bytes()
                assert hashlib.sha256(raw_bytes).hexdigest()==p['sha256'], 'file changed during replay'
                doc=json.loads(raw_bytes.decode('utf-8-sig'))
                result=module.process_packet(doc,received_at_ms=p['received_ms'],evaluated_at_ms=p['received_ms'],
                                             receive_time_source='json_update_proxy')
                assert result['input_status']=='ACCEPTED', (cow,p['path'],result['input_status'])
                payloads.write(json.dumps(result,ensure_ascii=False,allow_nan=False)+'\n')
                f=result['features']; update=result['last_update']
                row={'cow_id':cow,'source_path':str(p['path'].resolve()),'source_sha256':p['sha256'],
                    'evaluated_at_ms':result['evaluated_at_ms'],'data_through_ms':result['data_through_ms'],
                    'feature_window_end_ms':update['feature_window_end_ms'],'quality_status':result['quality_status'],
                    'usable_for_fusion':result['usable_for_fusion'],'activity_evidence_level':result['activity_evidence_level'],
                    'new_activity_evidence':result['new_activity_evidence'],
                    'new_strong_activity_evidence':result['new_strong_activity_evidence'],
                    'packet_valid_seconds':update['valid_seconds'],**f}
                results.append(row)
                audits.append({'cow_id':cow,'source_path':str(p['path'].resolve()),'sha256':p['sha256'],
                    'raw_frames':update['raw_frames'],'observed_seconds':update['observed_seconds'],
                    'valid_seconds':update['valid_seconds'],'internal_gap_count':update['internal_gap_count']})
                if prior:
                    old=prior[str(p['path'].resolve())]
                    assert update['raw_frames']==int(old['frames'])
                    assert abs(update['valid_seconds']-float(old['ma_valid_seconds']))<1e-8
                    assert abs(update['observed_seconds']-float(old['observed_seconds']))<1e-8
                # Check no-data calls and disk restart on real data at regular checkpoints.
                if i%5==0 or i==len(packets)-1:
                    restored=ActivityModule.from_state_json(module.to_state_json())
                    a=module.snapshot(p['received_ms']+1)
                    b=restored.snapshot(p['received_ms']+1)
                    assert a==b, f'state restore changed output: {cow} {i}'
                    assert not a['new_activity_evidence'] and not a['new_strong_activity_evidence']
                    restored_count+=1; snapshot_checks+=1
                    dup=restored.process_packet(doc,received_at_ms=p['received_ms']+1,evaluated_at_ms=p['received_ms']+1)
                    assert dup['input_status']=='DUPLICATE_IGNORED'
                    assert not dup['new_activity_evidence'] and not dup['new_strong_activity_evidence']
                    assert dup['features']==a['features']
                    duplicate_checks+=1
                    module=restored
            later=p['received_ms']+int(Config().maximum_observation_age_minutes*60000)+1
            stale=module.snapshot(later)
            assert stale['quality_status']=='STALE_DATA' and not as_fusion_features(stale)['activity_available']
            assert not stale['new_activity_evidence'] and not stale['new_strong_activity_evidence']
            snapshot_checks+=1
            (state_out/f'state_{cow}.json').write_text(module.to_state_json(),encoding='utf-8')
            print('replayed',cow,len(packets),'packets; elapsed',round(time.perf_counter()-start,1),'s',flush=True)
    finally:
        payloads.close()
    write_csv(args.out/'原始包实测审计.csv',audits)
    write_csv(args.out/'逐包特征与决策.csv',results)
    # Labels are first loaded here, after all raw inference has finished.
    label_rows=read_csv(args.labels)
    labels={}
    for r in label_rows:
        if r['cohort'] != 'normal_calving':
            continue
        stamp=Decimal(r['start_ms'])
        if stamp != stamp.to_integral_value():
            raise ValueError('label timestamps must be integral milliseconds')
        key=(r['cow_id'],r['label'])
        if key in labels:
            raise ValueError('duplicate cow/event label: '+str(key))
        labels[key]=int(stamp)
    per1,total1=evaluate(results,labels,'new_activity_evidence')
    per2,total2=evaluate(results,labels,'new_strong_activity_evidence')
    write_csv(args.out/'逐牛_活动证据.csv',per1)
    write_csv(args.out/'逐牛_强活动证据.csv',per2)
    differences=[]; max_error=0.; compared=0
    if args.reference_v2.exists():
        expected={str((args.data_root.parent/r['packet_source']).resolve()):r for r in read_csv(args.reference_v2/'按数据包到达回放.csv')}
        mapping={'activity_1h_g':'A1h','activity_3h_g':'A3h','coverage_1h':'coverage_1h',
                 'history_baseline_g':'history_baseline','baseline_g':'blend_baseline',
                 'activity_ratio':'blend_ratio','reference_valid_hours':'reference_valid_hours',
                 'reference_days':'reference_days','activity_ratio_3h':'blend_ratio_3h'}
        assert len(expected)==len(results)
        for row in results:
            e=expected[row['source_path']]
            for actual_col,prior_col in mapping.items():
                a=row[actual_col]; b=float(e[prior_col]) if e[prior_col] else None
                if b is not None and not np.isfinite(b): b=None
                error=abs(a-b) if a is not None and b is not None else 0.
                if (a is None)!=(b is None) or error>1e-9:
                    differences.append({'cow':row['cow_id'],'path':row['source_path'],'feature':actual_col,'actual':a,'expected':b})
                max_error=max(max_error,error); compared+=1
        for per,filename in [(per1,'逐牛_blend_R1.5.csv'),(per2,'全量筛选规则_逐牛表现.csv')]:
            expected_per={r['cow_id']:r for r in read_csv(args.reference_v2/filename)}
            for row in per:
                e=expected_per[row['cow_id']]
                for key in ['early_hit','late_hit']:
                    assert row[key]==(e[key]=='True'), (row,key)
                for key in ['eligible_updates','background_alerts']:
                    assert row[key]==int(e[key]), (row,key)
                for key in ['first_early_lead_delivery_hours','first_early_lead_hoof_hours']:
                    assert (row[key] is None)==(e[key]==''), (row,key)
                    if row[key] is not None: assert abs(row[key]-float(e[key]))<1e-10
                assert abs(row['background_observed_hours']-float(e['background_observed_hours']))<1e-8
    report={'module_version':'1.0.0','data_source':str(args.data_root.resolve()),
        'raw_files':len(inventory),'cows':len(per1),'raw_frames':sum(r['raw_frames'] for r in audits),
        'valid_observed_hours':sum(r['valid_seconds']/3600 for r in audits),
        'runtime_seconds':time.perf_counter()-start,
        'raw_hashes_match_previous_audit':prior is not None,
        'feature_values_compared':compared,'feature_max_absolute_error':max_error,'feature_differences':differences,
        'state_restore_checks':restored_count,'snapshot_no_new_event_checks':snapshot_checks,
        'duplicate_packet_checks':duplicate_checks,'moderate_evidence':total1,'strong_evidence':total2,
        'definition':'new evidence events in [delivery-6h,hoof), using update_time as offline arrival proxy',
        'limitations':['same 10 previously inspected calving cows; not an independent accuracy test',
            'earlier-than-6h events per observed hour are a background burden proxy, not a healthy-control false-alarm rate',
            'activity evidence alone; no calving probabilities; receipt timestamps are proxies'],
        'code_sha256':{str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (HERE/'cowmata_activity_aux').glob('*.py')}}
    (args.out/'validation_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    if differences:
        raise AssertionError(f'{len(differences)} feature mismatches; see validation_summary.json')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
