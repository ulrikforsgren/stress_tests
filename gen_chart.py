#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

"""
TODO:
 - argParse
   - title
 - Generic CRUDChart function.
 - Chart for avg. rate 
 - Chart for avg. request time
 - Chart for each detail level

"""

import json
import sys

HEADER = """
<!DOCTYPE html>
<html>
  <head>
    <!-- Required meta tags -->
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>===TITLE===</title>
    <!--Chart.js JS CDN-->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/2.9.4/Chart.min.js"></script>
  </head>
  <body>
    <script>
      function CRUDChart(ctx, labels, data) {
        var myChart = new Chart(ctx, {
          type: 'line',
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
      function CRUDChartDetails(ctx, data) {
        var labels = [];
        for (let i = 0; i < data['create'].length; i++) {
          labels.push(i);
        }
        return new CRUDChart(ctx, labels, data)
      }
      function addChart(title) {
        const canvas = document.createElement('canvas');
        const t = document.createElement("h2");
        t.innerHTML = title;
        const charts = document.getElementById('charts');
        charts.appendChild(t);
        charts.appendChild(canvas);
        return canvas.getContext('2d');
      }
    </script>
"""

BODY = """
    <div id="charts">
    </div>
    <script>
"""

FOOTER = """
    </script>
  </body> </html>
"""

def addSummaryChart(title, data):
    print('var data =', json.dumps(data))
    print(f'CRUDChart(addChart("{title}"), labels, data);')

def addDetailedChart(title, data):
    print('var data =', json.dumps(data))
    print(f'CRUDChartDetails(addChart("{title}"), data);')


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
        elapsed,_,_,avg,_,_,res_r = res_rtp
        # Collect details
        data = [round(r[4],6) for r in res_r]
        d = get_dict(total_details, p)
        d[t] = data
        # Collect summary
        if t == 'create': summary_labels.append(p)
        l = get_list(summary_rate, t)
        l.append(round(n/elapsed,2))
        l = get_list(summary_avg, t)
        l.append(round(avg,6))
    return summary_labels, summary_rate, summary_avg, total_details


data = {}
if __name__ == '__main__':
    name = sys.argv[1]
    results = json.load(open(name))

    summary_labels, summary_rate, summary_avg, total_details = transform_crud_results(results)

    print(HEADER.replace('===TITLE===', name))
    print(BODY)
    print(f'var labels =', json.dumps(summary_labels), ';')
    addSummaryChart('Transactional throughput with parallel requests', summary_rate)
    addSummaryChart('Average request time with parallel requests', summary_avg)
    for p, details in total_details.items():
        addDetailedChart(f"Time for each request - {p} parallel requests", details)
    print(FOOTER)
