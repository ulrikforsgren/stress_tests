import csv
import re

from dateutil.parser import isoparse


# Extract the result from the output file
# 2024-09-28T21:40:30.040540 create (222.91564014554024, 10000, 0, 0) (100000, 90000, 718249945, 1140419757, 87680, 0, 0, 0) (3953090560, 436.6, pcputimes(user=16838.27, system=4955.27, children_user=0.0, children_system=0.0, iowait=0.0))
def parse_line(line):
        global last_result
        match = re.match(
            r'(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)\s+'
            r'(?P<operation>[\w-]+)\s+'
            r'\((?P<execution_time>[\d\.]+),\s+(?P<number2>\d+),\s+(?P<number3>\d+),\s+(?P<number4>\d+)\)\s+'
            r'\((?P<number_of_devices>\d+),\s+(?P<number_of_services>\d+),\s+(?P<number7>\d+),\s+(?P<number8>\d+),\s+(?P<number9>\d+),\s+(?P<number10>\d+),\s+(?P<number11>\d+),\s+(?P<number12>\d+)\)\s+'
            r'\((?P<number13>\d+),\s+(?P<number14>[\d\.]+),\s+pcputimes\(user=(?P<user>[\d\.]+),\s+system=(?P<system>[\d\.]+),\s+children_user=(?P<children_user>[\d\.]+),\s+children_system=(?P<children_system>[\d\.]+),\s+iowait=(?P<iowait>[\d\.]+)\)\)',
            line
        )
        if match:
            result = match.groupdict()
            result['timestamp'] = isoparse(result['timestamp']).timestamp()
            last_result = result
            return result
        match = re.match(
            r'(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)\s+'
            r'(?P<operation>[\w-]+)\s+'
            r'(?P<execution_time>[\d\.]+)\s+'
            r'\((?P<number_of_devices>\d+),\s+(?P<number_of_services>\d+),\s+(?P<number7>\d+),\s+(?P<number8>\d+),\s+(?P<number9>\d+),\s+(?P<number10>\d+),\s+(?P<number11>\d+),\s+(?P<number12>\d+)\)\s+'
            r'\((?P<number13>\d+),\s+(?P<number14>[\d\.]+),\s+pcputimes\(user=(?P<user>[\d\.]+),\s+system=(?P<system>[\d\.]+),\s+children_user=(?P<children_user>[\d\.]+),\s+children_system=(?P<children_system>[\d\.]+),\s+iowait=(?P<iowait>[\d\.]+)\)\)',
            line
        )
        if match:
            result = match.groupdict()
            result['timestamp'] = isoparse(result['timestamp']).timestamp()
            last_result = result
            return result
        match = re.match(
            r'(?P<operation>[\w ]+)\s+'
            r'(?P<execution_time>[\d\.]+)\s+',
            line
        )
        if match:
            return {'timestamp': last_result['timestamp'], 'operation': 'wait_cpu_idle_time', 'execution_time': match.group('execution_time')}
        return None

def main(args):
    output_file = args.input_file
    with open(output_file, 'r') as f:
        with open(args.output_file, 'w') as result_file:
            columns = ['timestamp', 'create-devices', 'create', 'load', 'wait_cpu_idle_time', 'update', 'number_of_devices', 'number_of_services']
            writer = csv.DictWriter(result_file, columns, extrasaction='ignore')
            writer.writeheader()
            for l in f.readlines():
                result = parse_line(l)
                if result:
                    #result['timestamp'] = isoparse(result['timestamp']).timestamp()
                    result[result['operation']] = result['execution_time']
                    #row = {k: v for k,v in result.items() if k in columns }
                    #r = result.copy()
                    writer.writerow(result)
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Extract the result from the input file')
    parser.add_argument('input_file', help='The input file')
    parser.add_argument('output_file', help='The output file')
    args = parser.parse_args()
    main(args)