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
import os.path as path
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
    <div id="charts" style="margin: 50px">
    </div>
    <script>
"""

FOOTER = """
    </script>
  </body> </html>
"""

def addSummaryChart(f, title, data):
    f.write('var data =')
    f.write(json.dumps(data))
    f.write(';')
    f.write(f'CRUDChart(addChart("{title}"), labels, data);')

def addDetailedChart(f, title, data):
    f.write('var data =')
    f.write(json.dumps(data))
    f.write(';')
    f.write(f'CRUDChartDetails(addChart("{title}"), data);')


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


data = {}
if __name__ == '__main__':
    name = sys.argv[1]
    if len(sys.argv)>2:
        oname = sys.argv[2]+'/'+path.basename(name).rsplit('.',1)[0] + ".html"
    else:
        oname = name.rsplit('.',1)[0] + ".html"
    print(oname)

    results = json.load(open(name))
    of = open(oname, 'w')

    summary_labels, summary_rate, summary_avg, total_details = transform_crud_results(results)

    of.write(HEADER.replace('===TITLE===', name))
    of.write(BODY)
    of.write('var labels =')
    of.write(json.dumps(summary_labels))
    of.write(';')
    addSummaryChart(of, 'Transactional throughput with parallel requests', summary_rate)
    addSummaryChart(of, 'Average request time with parallel requests', summary_avg)
    for p, details in total_details.items():
        addDetailedChart(of, f"Time for each request - {p} parallel requests", details)
    of.write(FOOTER)
