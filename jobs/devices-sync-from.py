from stress_testing.stress_testing import SequenceRequest

DATA = \
{
  "op": "action",
  "url": "/tailf-ncs:devices/device=r<<id>>/sync-from",
  "parameters": {
    "id": SequenceRequest(0),
    "stop": 1000
  }
}