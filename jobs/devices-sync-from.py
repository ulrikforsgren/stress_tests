from stress_testing.stress_testing import SequenceRequest

start = 0
stop = 1000


intent = {
  "op": "action",
  "url": "/tailf-ncs:devices/device=r<<id>>/sync-from"
}

parameters = {
    "did": SequenceRequest(start),
    "stop": 1000
}