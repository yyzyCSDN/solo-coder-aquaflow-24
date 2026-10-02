from dataclasses import dataclass
from datetime import datetime,timezone


@dataclass(frozen=True)
class Event:
    seq:int;src:str;dst:str;at:datetime;seal:str


def validate(origin:str,events:list[Event])->str:
    """Replay a lab custody chain in sequence order.

    Besides the chain-level rules (gap-free sequence numbers, source
    continuity, no self-handover, unique seals), every timestamp must be
    timezone-aware and, after conversion to UTC, be non-decreasing so the
    audit chain can be replayed reliably regardless of source timezones.
    """
    cur=origin;exp=1;last=None;seals:set[str]=set()
    for e in sorted(events,key=lambda e:e.seq):
        if e.seq!=exp or e.src!=cur or e.src==e.dst:raise ValueError("custody")
        if e.at.tzinfo is None or e.at.tzinfo.utcoffset(e.at) is None:raise ValueError("timezone")
        t=e.at.astimezone(timezone.utc)
        if last is not None and t<last:raise ValueError("time")
        if not e.seal or e.seal in seals:raise ValueError("seal")
        seals.add(e.seal);cur=e.dst;last=t;exp+=1
    return cur
