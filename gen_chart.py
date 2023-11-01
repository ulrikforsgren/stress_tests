#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

"""
TODO:
 - argParse
   - title

"""

import argparse
import json
import os.path as path
from string import Template
import sys

def parseArgs(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('result', type=str, nargs='+',
            help='Result file to convert.')
    parser.add_argument('-t', type=str, default='',
            help='Tag to include in header.')
    parser.add_argument('-d', type=str,
            help='Output directory. Default is same dir as the input file.')
    return parser.parse_args(args)

HEADER = """
<!DOCTYPE html>
<html>
  <head>
    <!-- Required meta tags -->
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${TITLE}</title>
    <!--Chart.js JS CDN-->
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.js"></script>
</head>
  <body>
    <h1>${TAG}${TITLE}</h1>
    <script>
      function MyChart(ctx, title, yt, xt, labels, data) {
        var myChart = new Chart(ctx, {
          type: 'line',
          options: {
            layout: {
                padding: 0
            },
            plugins: {
              title: {
                display: true,
                align: 'center',
                font: {
                  size: 40
                },
                text: title
              },
            },
            scales: {
              x: {
                display: true,
                title: {
                  display: true,
                  font: {
                    size: 25
                  },
                  text: xt
                }
              },
              y: {
                display: true,
                title: {
                  display: true,
                  font: {
                    size: 25
                  },
                  text: yt
                }
              }
            }
          },
          data: {
            labels: labels,
            datasets: [{
                lineTension: 0.0,
                data: data['create'],
                label: "Create",
                borderColor: "#3e95cd",
                backgroundColor: "#7bb6dd",
                fill: false,
              }, {
                lineTension: 0.0,
                data: data['read'],
                label: "Read",
                borderColor: "#3cba9f",
                backgroundColor: "#71d1bd",
                fill: false,
              }, {
                lineTension: 0.0,
                data: data['update'],
                label: "Update",
                borderColor: "#ffa500",
                backgroundColor:"#ffc04d",
                fill: false,
              }, {
                lineTension: 0.0,
                data: data['delete'],
                label: "Delete",
                borderColor: "#c45850",
                backgroundColor:"#d78f89",
                fill: false,
              }
            ]
          },
        });
      }
      function CRUDChartThroughput(title, labels, data) {
        ctx = addChart();
        return new MyChart(ctx, title,
                       'Requests per second', 'Concurrent requests',
                       labels, data)
      }
      function CRUDChartTime(title, labels, data) {
        ctx = addChart();
        return new MyChart(ctx, title,
                       'Request time seconds', 'Concurrent requests',
                       labels, data)
      }
      function DetailsChart(title, data) {
        ctx = addChart();
        var labels = [];
        for (let i = 0; i < data['create'].length; i++) {
          labels.push(i);
        }
        return new MyChart(ctx, title,
                       'Request time in seconds', 'Request id',
                       labels, data)
      }
      function addChart() {
        const canvas = document.createElement('canvas');
        const charts = document.getElementById('charts');
        charts.appendChild(canvas);
        const div = document.createElement('div');
        div.style.height = '200px';
        charts.appendChild(div);
        return canvas.getContext('2d');
      }
    </script>
"""

BODY = """
    <div id="charts" style="margin: 50px">
    </div>
    <script>
"""

FOOTER = """
    </script>
  </body> </html>
"""

def addThroughputChart(f, title, data):
    f.write('var data =')
    f.write(json.dumps(data))
    f.write(';')
    f.write(f'CRUDChartThroughput("{title}", labels, data);')

def addTimeChart(f, title, data):
    f.write('var data =')
    f.write(json.dumps(data))
    f.write(';')
    f.write(f'CRUDChartTime("{title}", labels, data);')

def addDetailedChart(f, title, data):
    f.write('var data =')
    f.write(json.dumps(data))
    f.write(';')
    f.write(f'DetailsChart("{title}", data);')


# Get a dict from a dict. Add if not found
def get_dict(d,k):
    i = d.get(k)
    if i is None:
        d[k] = i = {}
    return i
# Get a dict from a dict. Add if not found
def get_list(d,k):
    i = d.get(k)
    if i is None:
        d[k] = i = []
    return i

def transform_crud_results(results):
    total_details = {}
    summary_rate = {}
    summary_avg = {}
    summary_labels = []
    for res_p in results: # iterate over p
        t,n,p,res_rtp = res_p
        elapsed,n_success,_,avg,_,_,res_r = res_rtp
        # Collect details
        data = []
        for r in res_r:
            i,s,*rest = r
            if s == 'ok':
                data.append(round(rest[2],6))
            else:
                data.append(None)
        d = get_dict(total_details, p)
        d[t] = data
        # Collect summary
        if t == 'create': summary_labels.append(p)
        get_list(summary_rate, t).append(round(n_success/elapsed,2))
        get_list(summary_avg, t).append(round(avg,6))
    return summary_labels, summary_rate, summary_avg, total_details


def generate_html(args, name, oname):
    results = json.load(open(name))
    of = open(oname, 'w')

    summary_labels, summary_rate, summary_avg, total_details = transform_crud_results(results)

    space = '  ' if args.t else ''
    fields = {
        'TAG': args.t +('  ' if args.t else ''),
        'TITLE': name
    }
    of.write(Template(HEADER).substitute(fields))
    of.write(BODY)
    of.write('var labels =')
    of.write(json.dumps(summary_labels))
    of.write(';')
    addThroughputChart(of, 'Requests throughput with concurrent requests', summary_rate)
    addTimeChart(of, 'Average request time with parallel requests', summary_avg)
    for p, details in total_details.items():
        addDetailedChart(of, f"Individual request time with {p} concurrent requests", details)
    of.write(FOOTER)

data = {}
def main(args):
    for result in args.result:
        dirs, fname = path.split(result)
        name, ext = path.splitext(fname)
        odirs = args.d or dirs
        oname = path.join(odirs, name+'.html')
        generate_html(args, result, oname)
        print(f"Created {oname}")

if __name__ == '__main__':
    main(parseArgs(sys.argv[1:]))
