import time
import random

print("Loaded", flush=True)

def description(w, t, r, i):
    print(w, i.name, i, i.i, flush=True)
    time.sleep(1)

def create_python_service_config(w, t, r, i):
    print(w, i.name, i, flush=True)
    s = r.python_service.service.create(f'S{i.i}')
    s.str_value = "987k234hgb34lkj"
    s.delay = 0
    s.start_vlan = 1
    s.num_vlan = 20
    s.device = f'r{i.i}'
    s.template = [ "if-desc-config", "vlans-config" ]

def create_python_service_device(w, t, r, i):
    print(w, i.name, i, flush=True)
    s = r.python_service.service.create(f'S{i.i}')
    s.str_value = "987k234hgb34lkj"
    s.delay = 0
    s.start_vlan = 1
    s.num_vlan = 20
    s.device = f'r{i.i}'
    s.template = [ "if-desc", "vlans" ]


