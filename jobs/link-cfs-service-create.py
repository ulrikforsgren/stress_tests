from stress_testing.stress_testing import SequenceRequest, RandomValue

DATA = \
{
  "op": "create",
  "url": "/link-cfs:link-cfs",
  "data": {
    "link-cfs":{
      "name": "K<<id>>",
      "sleep": "<<delay>>",
      "unit": "<<unit>>",
      "vid": "<<vid>>",
      "str-value": "<<data>>",
      "device": [
        {
          "name": "r<<id>>",
          "list-entries": 1
        }
      ]
    }
  },
  "parameters": {
    "id": SequenceRequest(0),
    "unit": SequenceRequest(0),
    "vid": SequenceRequest(0),
    "data": RandomValue(0, 4000000000),
    "delay": 0,
    "stop": 1000
  }
}