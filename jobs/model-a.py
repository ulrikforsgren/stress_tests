from stress_testing.parameters import SequenceRequest, RandomValue

start = 0
no_services = 1000


intent = {
  "op": "update",
  "resource": "/model-a:model-a/model-a:list=S<<id>>",
  "data": {
    "list":{
        "str-value": "Changed string data <<data>>",
        "int-value": "<<data>>"
    }
  }
}

parameters = {
    "id": SequenceRequest(start, wrap=no_services),
    "data": RandomValue(0, 4000000000)
}
