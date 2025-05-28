from stress_testing.parameters import SequenceRequest

start = 0
stop = 1000


intent = {
  "op": "action",
  "resource": "/tailf-ncs:devices/device=r<<id>>/sync-from"
}

parameters = {
    "id": SequenceRequest(start),
    "stop": 1000
}