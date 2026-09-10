import argparse


###############################################################################
#  ARGUMENTS PARSER FUNCTIONS
###############################################################################
#

def parseArgs(args=None, extra_cmds=[], options='old-crud', path=None):
    commands = []
    if isinstance(options, str):
        options = [options]
    if {'old-crud', 'crud'}.intersection(options):
        options += [
            'basic',
            'scale',
            'params',
            'commit-params',
            'json',
            'report',
            'highlight',
        ]
        commands += ['clean', 'create', 'read', 'update', 're-deploy', 'delete', 'crud', 'crurd', 'cud']
    elif 'old-crud' in options:
        options += ['single']
    elif 'benchmarking' in options:
        options += ['basic']
    elif 'scripted' in options:
        options += [
            'basic',
            'state'
        ]
        commands += ['clean', 'run']
    elif 'single' in options:
        options += [
            'basic',
            'scale',
            'params',
            'commit-params',
            'action'
        ]

    parser = argparse.ArgumentParser()
    if commands:
        parser.add_argument('cmd', nargs='+', choices=commands + extra_cmds)
    if {'crud', 'action'}.intersection(options):
        parser.add_argument('test', type=str,
                            help='Test to run.')
    if 'action' in options:
        parser.add_argument('operation', type=str,
                            help='Operation to run.')
    if 'basic' in options:
        parser.add_argument('--host', type=str,
                            help='host[:port]',
                            default='localhost:8080')
        parser.add_argument("--dry-run", required=False, action='store_true', default=False,
                            help="Run sequence but do not send request over network.")
        parser.add_argument("--echo", required=False, action='store_true', default=False,
                            help="Echo request to console.")
        parser.add_argument("--log-file", required=False, type=str,
                            help="Write echo/debug logs to this file.")
        parser.add_argument("-q", required=False, action='store_true',
                            default=False, help='Silent mode.')
        parser.add_argument("-v", required=False, action='store_true',
                            default=False, help='Verbose mode. Show result of each request.')
    if 'state' in options:
        parser.add_argument("--keep-state", required=False, action='store_true', default=False,
                            help="Loads state if state files exist and saves after run.")
    if 'single' in options:
        parser.add_argument("--single", required=False, action='store_true', default=False,
                        help="Run one iteration of one operation with one windows size.")
    if 'scale' in options:
        parser.add_argument("-n", required=False, type=int,
                            help='Number of total requests.')
        parser.add_argument("-w", required=False, type=int, default=40,
                            help='Max window size. Starting 1, 2, 5, .., max')
        parser.add_argument("-s", required=False, type=str,
                            help='Window size(s) comma sepated.')
    if 'params' in options:
        parser.add_argument("-p", required=False, type=str, action='append',
                            help='Alter parameters.')
    if 'commit-params' in options:
        parser.add_argument("--no-networking", required=False, action='store_true',
                            default=False, help='Commit with no-networking.')
        parser.add_argument("--commit-queue", required=False, action='store_true',
                            default=False, help='Commit to commit-queue.')
    if 'json' in options:
        parser.add_argument("-o", required=False, type=str,
                            help='Output result in json format to file.')
    if 'report' in options:
        parser.add_argument("--html", required=False, action='store_true',
                            help='Output results as graphs in html.')
        parser.add_argument("--open", required=False, action='store_true',
                            help='Open generated html.')
    if 'benchmarking' in options:
        parser.add_argument('--history', type=int, default=3600,
                             help='How many seconds to keep history data.')
    if 'highlight' in options:
        parser.add_argument("--highlight", required=False, action='store_true',
                            default=False, help='Highlight output to make it more readable.')
    if path:
        parser.add_argument("--path", required=False, type=str, action='append',
                            default=path, help='Path to search for modules.')
    
    parsed_args = parser.parse_args(args)
    if 'state' not in options:
        parsed_args.keep_state = False
    return parsed_args
