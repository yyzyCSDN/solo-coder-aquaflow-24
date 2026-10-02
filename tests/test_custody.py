import unittest
from datetime import datetime,timedelta,timezone
from aquaflow.api import AquaFlowService
from aquaflow.lab.custody import Event,validate
UTC=timezone.utc
def ev(seq,src,dst,at,seal):return Event(seq,src,dst,at,seal)
class T(unittest.TestCase):
    def test_same_day_increasing_chain_accepted(self):
        events=[ev(1,"field","courier",datetime(2026,10,1,8,0,tzinfo=UTC),"S1"),
                ev(2,"courier","lab",datetime(2026,10,1,9,15,tzinfo=UTC),"S2"),
                ev(3,"lab","archive",datetime(2026,10,1,17,45,tzinfo=UTC),"S3")]
        self.assertEqual(validate("field",events),"archive")
    def test_equal_timestamps_allowed(self):
        at=datetime(2026,10,1,8,0,tzinfo=UTC)
        events=[ev(1,"field","courier",at,"S1"),ev(2,"courier","lab",at,"S2")]
        self.assertEqual(validate("field",events),"lab")
    def test_reversed_time_rejected(self):
        events=[ev(1,"field","courier",datetime(2026,10,1,9,0,tzinfo=UTC),"S1"),
                ev(2,"courier","lab",datetime(2026,10,1,8,0,tzinfo=UTC),"S2")]
        with self.assertRaises(ValueError) as ctx:validate("field",events)
        self.assertEqual(str(ctx.exception),"time")
    def test_mixed_timezones_ordered_after_conversion(self):
        # Wall clocks are not ordered, but UTC instants are: 07:00Z <= 13:30Z <= 14:00Z.
        events=[ev(1,"field","courier",datetime(2026,10,1,9,0,tzinfo=timezone(timedelta(hours=2))),"S1"),
                ev(2,"courier","lab",datetime(2026,10,1,8,30,tzinfo=timezone(timedelta(hours=-5))),"S2"),
                ev(3,"lab","archive",datetime(2026,10,1,14,0,tzinfo=UTC),"S3")]
        self.assertEqual(validate("field",events),"archive")
    def test_mixed_timezones_backdated_after_conversion(self):
        # 09:00 at +02:00 is 07:00Z, so the later seq at 06:30Z is a backdated handover.
        events=[ev(1,"field","courier",datetime(2026,10,1,9,0,tzinfo=timezone(timedelta(hours=2))),"S1"),
                ev(2,"courier","lab",datetime(2026,10,1,6,30,tzinfo=UTC),"S2")]
        with self.assertRaises(ValueError) as ctx:validate("field",events)
        self.assertEqual(str(ctx.exception),"time")
    def test_naive_datetime_rejected(self):
        events=[ev(1,"field","lab",datetime(2026,10,1,8,0),"S1")]
        with self.assertRaises(ValueError):validate("field",events)
    def test_source_continuity_preserved(self):
        events=[ev(1,"field","courier",datetime(2026,10,1,8,0,tzinfo=UTC),"S1"),
                ev(2,"other","lab",datetime(2026,10,1,9,0,tzinfo=UTC),"S2")]
        with self.assertRaises(ValueError) as ctx:validate("field",events)
        self.assertEqual(str(ctx.exception),"custody")
    def test_self_handover_preserved(self):
        events=[ev(1,"field","field",datetime(2026,10,1,8,0,tzinfo=UTC),"S1")]
        with self.assertRaises(ValueError) as ctx:validate("field",events)
        self.assertEqual(str(ctx.exception),"custody")
    def test_sequence_gap_preserved(self):
        events=[ev(1,"field","courier",datetime(2026,10,1,8,0,tzinfo=UTC),"S1"),
                ev(3,"courier","lab",datetime(2026,10,1,9,0,tzinfo=UTC),"S3")]
        with self.assertRaises(ValueError) as ctx:validate("field",events)
        self.assertEqual(str(ctx.exception),"custody")
    def test_duplicate_seal_preserved(self):
        events=[ev(1,"field","courier",datetime(2026,10,1,8,0,tzinfo=UTC),"S1"),
                ev(2,"courier","lab",datetime(2026,10,1,9,0,tzinfo=UTC),"S1")]
        with self.assertRaises(ValueError) as ctx:validate("field",events)
        self.assertEqual(str(ctx.exception),"seal")
    def test_workflow_acceptance_result(self):
        payload={"origin":"field","events":[
            {"seq":1,"src":"field","dst":"courier","at":"2026-10-01T09:00:00+02:00","seal":"S1"},
            {"seq":2,"src":"courier","dst":"lab","at":"2026-10-01T08:30:00-05:00","seal":"S2"}]}
        result=AquaFlowService().run_workflow("custody_chain",payload)
        self.assertEqual(result["decision"],"accept")
        self.assertEqual(result["value"],"lab")
        self.assertEqual(result["evidence"]["time_order"],"nondecreasing")
        self.assertEqual(result["audit"]["contract"],"v1")
    def test_workflow_reversed_time_rejected(self):
        payload={"origin":"field","events":[
            {"seq":1,"src":"field","dst":"courier","at":"2026-10-01T09:00:00Z","seal":"S1"},
            {"seq":2,"src":"courier","dst":"lab","at":"2026-10-01T08:00:00Z","seal":"S2"}]}
        with self.assertRaises(ValueError):AquaFlowService().run_workflow("custody_chain",payload)
    def test_workflow_naive_timestamp_rejected(self):
        payload={"origin":"field","events":[
            {"seq":1,"src":"field","dst":"lab","at":"2026-10-01T08:00:00","seal":"S1"}]}
        with self.assertRaises(ValueError):AquaFlowService().run_workflow("custody_chain",payload)
if __name__=="__main__":unittest.main()
