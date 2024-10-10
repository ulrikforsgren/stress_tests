import json
import time

from .restconf_api import restconf_request


###############################################################################
#  HELPER FUNCTIONS
###############################################################################
#

async def setup_task(args, client, host):
    # Reading an arbitrary leaf to force the client to setup a connection.
    resource = '/tailf-ncs:devices/global-settings/read-timeout'
    op = 'read'
    st = time.monotonic()
    resp = await restconf_request(args, client,
                                  host,
                                  op,
                                  resource)
    elapsed = time.monotonic()-st
    return (*resp, elapsed)


# Calculate the average execution time for all "ok" requests and
# count number of result types "ok"/"nok"/"exception".
def calc_average(results):
    total_ok = 0.0
    count_ok = 0
    count_wrong = 0
    count_exc = 0
    for r in results:
        rid, res, *rest = r
        if res == 'ok':
            st, _, el = rest
            total_ok += el
            count_ok += 1
        elif res == 'nok':
            count_wrong += 1
        elif res == 'exception':
            count_exc += 1

    return count_ok, total_ok, count_wrong, count_exc


def set_flags(args, d):
    flags = {}
    if args.no_networking:
        flags['no-networking'] = 'true'
    if args.commit_queue:
        flags['commit-queue'] = 'sync'
    if 'query_parameters' in d:
        d['query_parameters'].update(flags)
    else:
        d['query_parameters'] = flags


# Generator for 1,2,5,10,20,... sequence
def np_gen(max_p):
    n = 1
    m = 1
    while n <= max_p:
        for s in [1, 2, 5]:
            np = s*m
            if np < max_p:
                yield np
            else:
                yield max_p
                return
        m *= 10


# Function to replace any of the characters in the string s with the character c
def replace_chars(s, c, chars):
    for ch in chars:
        s = s.replace(ch, c)
    return s


def json_to_tuple(json_str):
    def convert(obj):
        if isinstance(obj, list):
            return tuple(convert(item) for item in obj)
        elif isinstance(obj, dict):
            return {key: convert(value) for key, value in obj.items()}
        else:
            return obj

    return convert(json.loads(json_str))


def number_of_open_connections(conn):
    if len(conn._conns):
        key = list(conn._conns.keys())[0]  # Assuming only one key
        return len(conn._conns[key])
    else:
        return 0