import unittest
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from aquaflow.api import AquaFlowService
from aquaflow.treatment.chlorine_ct import Segment
from aquaflow.network.isolation import Pipe
from aquaflow.meters.balance import Meter
from aquaflow.lab.custody import Event,validate
from aquaflow.simulation.hydraulics import Node,Link,solve
class T(unittest.TestCase):
    def test_health(self):self.assertEqual(AquaFlowService().health()["runtime_dependencies"],0)
    def test_ct(self):self.assertTrue(AquaFlowService().ct([Segment(20,1,.8,20)],10))
    def test_isolation(self):
        self.assertEqual(AquaFlowService().isolate({"S","A","B"},[Pipe("1","S","A"),Pipe("2","A","B")],{"2"},{"S"}),{"B"})
    def test_balance(self):
        i=[Meter("i",Decimal(0),Decimal(20),Decimal(1))]
        o=[Meter("o",Decimal(0),Decimal(15),Decimal(1))]
        self.assertEqual(AquaFlowService().water_balance(i,o,Decimal(1)),Decimal(4))
    def test_solver(self):
        r=solve([Node("S",0,60),Node("A",5,None)],[Link("L","S","A",2)])
        self.assertTrue(r.converged)
    def _chain(self,ats,seals=("s1","s2","s3"),srcs=("A","B","C"),dsts=("B","C","D"),seqs=(1,2,3)):
        return [{"seq":q,"src":s,"dst":d,"at":a,"seal":x} for q,s,d,a,x in zip(seqs,srcs,dsts,ats,seals)]
    def test_custody_reversed_time_rejected(self):
        svc=AquaFlowService()
        payload={"origin":"A","events":self._chain([
            "2026-10-02T10:00:00Z","2026-10-02T09:00:00Z","2026-10-02T11:00:00Z"])}
        with self.assertRaises(ValueError):svc.run_workflow("custody_chain",payload)
        events=[Event(1,"A","B",datetime(2026,10,2,10,tzinfo=timezone.utc),"s1"),
                Event(2,"B","C",datetime(2026,10,2,9,tzinfo=timezone.utc),"s2")]
        with self.assertRaisesRegex(ValueError,"time"):validate("A",events)
    def test_custody_different_timezones_accepted(self):
        # Local clocks appear out of order, but UTC conversion is non-decreasing.
        svc=AquaFlowService()
        payload={"origin":"A","events":self._chain([
            "2026-10-02T12:00:00+03:00",  # 09:00Z
            "2026-10-02T05:00:00-04:00",  # 09:00Z (equal timestamps allowed)
            "2026-10-02T03:30:00-07:00"])}# 10:30Z
        result=svc.run_workflow("custody_chain",payload)
        self.assertEqual(result["decision"],"accept")
        self.assertEqual(result["value"],"D")
        self.assertEqual(result["audit"]["contract"],"v1")
    def test_custody_same_day_increasing_accepted(self):
        svc=AquaFlowService()
        payload={"origin":"A","events":self._chain([
            "2026-10-02T08:00:00Z","2026-10-02T08:30:00Z","2026-10-02T09:15:00Z"])}
        result=svc.run_workflow("custody_chain",payload)
        self.assertEqual(result["decision"],"accept")
        self.assertEqual(result["value"],"D")
        self.assertEqual(result["evidence"]["events"],3)
    def test_custody_naive_time_rejected(self):
        payload={"origin":"A","events":self._chain([
            "2026-10-02T08:00:00","2026-10-02T08:30:00","2026-10-02T09:15:00"])}
        with self.assertRaisesRegex(ValueError,"timezone"):
            AquaFlowService().run_workflow("custody_chain",payload)
    def test_custody_preserved_chain_rules(self):
        base=self._chain(["2026-10-02T08:00:00Z","2026-10-02T08:30:00Z","2026-10-02T09:15:00Z"])
        svc=AquaFlowService()
        # sequence gap
        gap=self._chain(["2026-10-02T08:00:00Z","2026-10-02T08:30:00Z"],seqs=(1,3))
        with self.assertRaisesRegex(ValueError,"custody"):svc.run_workflow("custody_chain",{"origin":"A","events":gap})
        # broken source continuity
        broken=self._chain(["2026-10-02T08:00:00Z","2026-10-02T08:30:00Z"],srcs=("A","X"))
        with self.assertRaisesRegex(ValueError,"custody"):svc.run_workflow("custody_chain",{"origin":"A","events":broken})
        # self-handover
        selfhand=self._chain(["2026-10-02T08:00:00Z"],srcs=("A",),dsts=("A",),seals=("s1",))
        with self.assertRaisesRegex(ValueError,"custody"):svc.run_workflow("custody_chain",{"origin":"A","events":selfhand})
        # duplicate seal
        dup=self._chain(["2026-10-02T08:00:00Z","2026-10-02T08:30:00Z"],seals=("s1","s1"))
        with self.assertRaisesRegex(ValueError,"seal"):svc.run_workflow("custody_chain",{"origin":"A","events":dup})
        # untouched valid chain replays to the final custodian
        self.assertEqual(validate("A",[
            Event(1,"A","B",datetime(2026,10,2,8,tzinfo=timezone.utc),"s1"),
            Event(2,"B","C",datetime(2026,10,2,8,30,tzinfo=timezone.utc),"s2")]),"C")
if __name__=="__main__":unittest.main()
