from stress_testing.stress_testing import SequenceRequest

start = 0
no_services = 10000


intent = {
  "op": "delete",
  "resource": "/python-service:python-service/python-service:service=S<<sid>>",
  "query_parameters": {
    "no-networking": "true",
#    "commit-queue": "sync",
  }
}

parameters = {
    "sid": SequenceRequest(start),
    "concurrency": 15,
#    "requests-per-second": 8, # 0 means no limit
    "stop": no_services, # 0 means continue forever
}
