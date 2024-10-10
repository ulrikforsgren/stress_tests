from stress_testing.parameters import SequenceRequest, RandomValue

start = 0
stop = 1000
delay = 0


intent = {
  "op": "create",
  "url": "/link-cfs:link-cfs",
  "data": {
    "link-cfs":{
      "name": "S<<id>>",
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
  }
}

parameters= {
    "id": SequenceRequest(start),
    "unit": SequenceRequest(start),
    "vid": SequenceRequest(start),
    "data": RandomValue(0, 4000000000),
    "delay": delay,
    "stop": stop
}
