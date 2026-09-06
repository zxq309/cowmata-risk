import base64
import copy
import json
import unittest
import numpy as np
from cowmata_activity_aux import ActivityModule, Context, Config, PacketError, as_fusion_features
from cowmata_activity_aux.protocol import FRAME_DTYPE, decode_packet
from cowmata_activity_aux.features import packet_minutes, compute_features

BASE = 1800000000000


def document(uid, create_ms=BASE, *, n=3000, amplitude=256, elapsed=None, values=None):
    frame = np.zeros(n, dtype=FRAME_DTYPE)
    frame['elapsed_ms'] = np.arange(n)*20 if elapsed is None else elapsed
    frame['values'][:, 0] = np.where(np.arange(n)%2, amplitude, -amplitude)
    frame['values'][:, 2] = 4096
    if values is not None:
        frame['values'][:, :3] = values
    return {'uid':uid,'device':'ABC123','version':2,'create_time':create_ms,
            'imu':base64.b64encode(frame.tobytes()).decode('ascii')}


class ActivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = Context('42','ABC123','binding-42',BASE)
        cls.baseline_docs = [document(i,BASE+i*67*60000,n=180000) for i in range(3)]
        m = ActivityModule(cls.context)
        for d in cls.baseline_docs:
            m.process_packet(d,received_at_ms=d['create_time']+66*60000)
        cls.baseline_state = m.to_state_json()
        cls.high = document(3,BASE+3*67*60000,n=180000,amplitude=768)
        cls.high_received = cls.high['create_time']+66*60000

    def baseline(self):
        return ActivityModule.from_state_json(self.baseline_state)

    def assert_rejected_without_mutation(self, m, doc, code, received):
        before=m.to_state_json()
        with self.assertRaises(PacketError) as caught:
            m.process_packet(doc,received_at_ms=received)
        self.assertEqual(caught.exception.code,code)
        self.assertEqual(m.to_state_json(),before)

    def test_empty_and_new_binding_have_no_evidence(self):
        m=ActivityModule(self.context)
        self.assertEqual(m.snapshot(BASE)['quality_status'],'NO_DATA')
        r=m.process_packet(self.high,received_at_ms=self.high_received)
        self.assertEqual(r['quality_status'],'INSUFFICIENT_HISTORY')
        self.assertIsNone(as_fusion_features(r)['activity_ratio'])

    def test_constant_pose_and_gap_do_not_create_motion(self):
        values=np.zeros((300,3),dtype=np.int16)
        values[:150,2]=4096; values[150:,0]=4096
        elapsed=np.r_[np.arange(150)*20,4000+np.arange(150)*20]
        p=decode_packet(document('pose',n=300,elapsed=elapsed,values=values),self.context)
        rows,diag=packet_minutes(p,Config())
        self.assertEqual(diag['internal_gap_count'],1)
        self.assertAlmostEqual(sum(r[1] for r in rows),0.)
        self.assertAlmostEqual(diag['valid_seconds'],102/50)
        self.assertAlmostEqual(diag['observed_seconds'],6.)

    def test_known_alternating_acceleration_magnitude(self):
        p=decode_packet(document('magnitude',n=200,amplitude=512),self.context)
        rows,diag=packet_minutes(p,Config())
        self.assertAlmostEqual(sum(r[1] for r in rows)/sum(r[2] for r in rows),.125,places=12)
        self.assertAlmostEqual(diag['valid_seconds'],101/50)

    def test_reference_excludes_current_hour_and_missing_time(self):
        rows=[[(i+1)*60000,2250*(2 if i>=180 else 1),2250,3000] for i in range(240)]
        f=compute_features(rows,feature_end_ms=240*60000,first_minute_end_ms=60000,config=Config())
        self.assertAlmostEqual(f['activity_ratio'],2.)
        self.assertAlmostEqual(f['baseline_g'],1.)
        self.assertAlmostEqual(f['coverage_1h'],.75)
        self.assertAlmostEqual(f['reference_valid_hours'],2.25)
        missing=[r for r in rows if r[0]<=180*60000]
        f=compute_features(missing,feature_end_ms=240*60000,first_minute_end_ms=60000,config=Config())
        self.assertIsNone(f['activity_1h_g'])
        self.assertIsNone(f['activity_ratio'])
        self.assertEqual(f['coverage_1h'],0.)

    def test_feature_future_prefix_invariance(self):
        rows=[[(i+1)*60000,3000*(1+i%7/10),3000,3000] for i in range(4500)]
        cut=4440
        a=compute_features(rows,feature_end_ms=cut*60000,first_minute_end_ms=60000,config=Config())
        b=compute_features(rows[:cut],feature_end_ms=cut*60000,first_minute_end_ms=60000,config=Config())
        self.assertEqual(a,b)
        self.assertEqual(a['reference_days'],3)
        self.assertEqual(a['same_clock_weight'],.6)

    def test_evidence_levels_and_real_packet_episode_cooldown(self):
        m=self.baseline()
        r=m.process_packet(self.high,received_at_ms=self.high_received)
        self.assertAlmostEqual(r['activity_ratio'],3.,places=9)
        self.assertEqual(r['activity_evidence_level'],'STRONG')
        self.assertTrue(r['new_activity_evidence'])
        self.assertTrue(r['new_strong_activity_evidence'])
        d=document(4,BASE+4*67*60000,n=180000,amplitude=768)
        r2=m.process_packet(d,received_at_ms=d['create_time']+66*60000)
        self.assertFalse(r2['new_activity_evidence'])
        self.assertFalse(r2['new_strong_activity_evidence'])

    def test_duplicate_does_not_emit_or_update_features(self):
        m=self.baseline()
        r=m.process_packet(self.high,received_at_ms=self.high_received)
        d=copy.copy(self.high);d['temperature']='ignored';d['update_time']=0
        duplicate=m.process_packet(d,received_at_ms=self.high_received+1)
        self.assertEqual(duplicate['input_status'],'DUPLICATE_IGNORED')
        self.assertEqual(duplicate['features'],r['features'])
        self.assertFalse(duplicate['new_activity_evidence'])
        self.assertFalse(duplicate['new_strong_activity_evidence'])

    def test_uid_conflict_is_transactional(self):
        m=self.baseline()
        d=copy.copy(self.baseline_docs[-1]);d['imu']=document(9,n=180000,amplitude=512)['imu']
        self.assert_rejected_without_mutation(m,d,'UID_CONFLICT',self.high_received)

    def test_wrong_binding_and_malformed_protocol_are_transactional(self):
        for key,value,code in [('device','OTHER','DEVICE_MISMATCH'),('version',1,'UNSUPPORTED_VERSION'),
                               ('imu','not base64?!','INVALID_BASE64'),('create_time',1.2,'INVALID_TIME')]:
            m=self.baseline();d=copy.copy(self.high);d[key]=value
            self.assert_rejected_without_mutation(m,d,code,self.high_received)

    def test_nonmonotonic_samples_and_future_samples_rejected(self):
        m=ActivityModule(self.context)
        d=document('badtime',n=20,elapsed=np.r_[np.arange(19)*20,0])
        self.assert_rejected_without_mutation(m,d,'NONMONOTONIC_SAMPLES',BASE+1000)
        self.assert_rejected_without_mutation(m,document('future'), 'FUTURE_SAMPLES',BASE+1000)

    def test_late_overlapping_packet_does_not_rewrite_history(self):
        m=self.baseline();before=m.snapshot(self.high_received)
        d=copy.copy(self.baseline_docs[0]);d['uid']='late-new-uid'
        r=m.process_packet(d,received_at_ms=self.high_received)
        self.assertEqual(r['input_status'],'LATE_OR_OVERLAP_IGNORED')
        self.assertEqual(r['features'],before['features'])
        self.assertFalse(r['new_activity_evidence'])

    def test_snapshot_and_cached_fusion_become_unavailable_when_stale(self):
        m=self.baseline();r=m.process_packet(self.high,received_at_ms=self.high_received)
        snap=m.snapshot(self.high_received+1)
        self.assertFalse(snap['new_activity_evidence'])
        self.assertEqual(snap['features'],r['features'])
        expiry=r['data_through_ms']+90*60000
        self.assertTrue(as_fusion_features(r,now_ms=expiry)['activity_available'])
        self.assertFalse(as_fusion_features(r,now_ms=expiry+1)['activity_available'])
        stale=m.snapshot(expiry+1)
        self.assertEqual(stale['quality_status'],'STALE_DATA')
        self.assertIsNone(stale['activity_ratio'])
        self.assertFalse(stale['new_activity_evidence'])

    def test_state_restore_preserves_events_and_next_packet_result(self):
        a=self.baseline();a.process_packet(self.high,received_at_ms=self.high_received)
        b=ActivityModule.from_state_json(a.to_state_json())
        d=document(4,BASE+4*67*60000,n=180000,amplitude=768)
        self.assertEqual(a.process_packet(d,received_at_ms=d['create_time']+66*60000),
                         b.process_packet(d,received_at_ms=d['create_time']+66*60000))
        json.dumps(a.snapshot(d['create_time']+66*60000),allow_nan=False)

    def test_corrupt_state_is_rejected(self):
        for mutate in [lambda s:s.update(state_version=99),
                       lambda s:s['minutes'][-1].__setitem__(1,float('nan')),
                       lambda s:s['minutes'][-1].__setitem__(2,99999),
                       lambda s:s['last_update'].__setitem__('data_through_ms',BASE-1)]:
            s=json.loads(self.baseline_state);mutate(s)
            with self.assertRaises(ValueError): ActivityModule.from_state_json(json.dumps(s))

    def test_phase_closure_suppresses_prepartum_evidence(self):
        m=self.baseline();m.set_phase('calving',at_ms=self.high_received)
        r=m.process_packet(self.high,received_at_ms=self.high_received)
        self.assertEqual(r['quality_status'],'PHASE_INACTIVE')
        self.assertFalse(r['new_activity_evidence'])
        self.assertFalse(as_fusion_features(r)['activity_available'])
        with self.assertRaises(ValueError):m.set_phase('prepartum',at_ms=self.high_received)

    def test_clock_and_configuration_validation(self):
        m=self.baseline();before=m.to_state_json()
        with self.assertRaises(PacketError):m.snapshot(BASE)
        self.assertEqual(before,m.to_state_json())
        for kwargs in [{'acc_counts_per_g':0},{'minimum_hour_coverage':1.2},{'history_retention_hours':24},
                       {'evidence_ratio':3.},{'sample_rate_hz':100},{'episode_cooldown_minutes':float('nan')}]:
            with self.assertRaises(ValueError):Config(**kwargs)

    def test_binding_identifiers_and_numpy_timestamp_are_serializable(self):
        context=Context(42,'AB:C1:23','numpy-time',np.int64(BASE))
        m=ActivityModule(context)
        restored=ActivityModule.from_state_json(m.to_state_json())
        self.assertEqual(restored.context,context)
        for bad in [None,True,'   ']:
            with self.assertRaises(ValueError):Context(bad,'ABC','binding',BASE)
        with self.assertRaises(ValueError):Context('42','::','binding',BASE)


if __name__=='__main__':
    unittest.main(verbosity=2)
