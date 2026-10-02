const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

function fixture() {
    const now = 100000000;
    const elements = new Map();
    const handlers = {};
    const requests = [];
    const timers = new Map();
    let timerId = 0;
    const context = vm.createContext({
        console: {log() {}},
        Date: {now: () => now},
        setInterval() {},
        setTimeout(callback) { timers.set(++timerId, callback); return timerId; },
        clearTimeout(id) { timers.delete(id); },
        document: {
            getElementById(id) {
                if (!elements.has(id)) elements.set(id, {textContent: ''});
                return elements.get(id);
            },
        },
        luxon: {DateTime: {fromMillis: () => ({toFormat: () => '12:00:00'})}},
        Chart: class {
            constructor(element, config) {
                this.data = config.data;
                this.options = config.options;
                this.width = 1200;
                this.scales = {x: {}};
                this.updates = 0;
                this.update();
            }
            update() {
                this.updates++;
                const realtime = this.options.scales.x.realtime;
                this.scales.x.max = now - realtime.delay;
                this.scales.x.min = this.scales.x.max - realtime.duration;
            }
            resetZoom() {}
        },
        io: () => ({
            on(name, handler) { handlers[name] = handler; },
            emit(name, payload) { requests.push({name, payload}); },
        }),
    });
    const html = fs.readFileSync(`${__dirname}/templates/index.html`, 'utf8');
    vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);
    return {
        now, context, handlers, requests, elements,
        run(code) { return vm.runInContext(code, context); },
        flush() {
            const callbacks = Array.from(timers.values());
            timers.clear();
            callbacks.forEach(callback => callback());
        },
        respond(metrics, retention = 86400) {
            handlers.startdata({
                request_id: context.history_request_id,
                retention, metrics, end: now,
            });
        },
    };
}

test('requests only visible duration and rejects stale responses', () => {
    const f = fixture();
    f.handlers.connect();
    f.flush();
    assert.equal(f.requests[0].payload.duration, 302);
    f.run('set_windowsize(10)');
    f.flush();
    assert.equal(f.requests[1].payload.duration, 12);
    f.handlers.startdata({
        request_id: 1, retention: 86400, metrics: [{ts: f.now, ok: 999, nok: 0}],
    });
    assert.equal(f.context.metrics_by_timestamp.size, 0);
    f.respond([{ts: f.now - 2000, ok: 2, nok: 0}]);
    assert.equal(f.context.metrics_by_timestamp.size, 1);
});

test('rolling average uses hidden context and live values wait for refresh', () => {
    const f = fixture();
    f.handlers.connect();
    f.flush();
    const start = f.now - 302000;
    const metrics = [];
    for (let i = -60; i <= 302; i++) {
        metrics.push({ts: start + i * 1000, ok: i === 0 ? 20 : 10, nok: 0});
    }
    f.respond(metrics);
    const average = f.run('myChart.data.datasets[2].data.find(p => p.x === visible_bounds().start).y');
    assert.equal(average, 11);
    const updates = f.run('myChart.updates');
    f.handlers.value({ts: f.now, ok: 30, nok: 1});
    assert.equal(f.run('myChart.updates'), updates);
    assert.equal(f.context.chart_dirty, true);
    f.run('options.scales.x.realtime.onRefresh()');
    assert.equal(f.context.chart_dirty, false);
    assert.equal(f.run('myChart.data.datasets[0].data.at(-1).y'), 30);
});

test('six-hour windows bound drawing and preserve extrema', () => {
    const f = fixture();
    f.run('history_retention = 86400; set_windowsize(21600)');
    f.flush();
    const metrics = [];
    for (let i = 0; i < 21662; i++) {
        metrics.push({
            ts: f.now - (21661 - i) * 1000,
            ok: i === 12000 ? 100000 : i === 15000 ? -100 : 10,
            nok: 0,
        });
    }
    f.respond(metrics);
    for (const length of f.run('myChart.data.datasets.map(d => d.data.length)')) {
        assert.ok(length <= 2400, `Rendered ${length} points`);
    }
    assert.equal(f.run('Math.max(...myChart.data.datasets[0].data.map(p => p.y))'), 100000);
    assert.equal(f.run('Math.min(...myChart.data.datasets[0].data.map(p => p.y))'), -100);
    assert.ok(f.context.metrics_by_timestamp.size <= 21662);
});

test('paused historical views request old data and ignore newer live samples', () => {
    const f = fixture();
    f.run("history_retention = 86400; view_mode = 'paused'; options.scales.x.realtime.delay = 3600000; myChart.update()");
    f.run('handle_pan_complete({chart: myChart})');
    f.flush();
    assert.equal(f.requests[0].payload.end_timestamp, (f.now - 3600000) / 1000);
    f.handlers.value({ts: f.now, ok: 1, nok: 0});
    assert.equal(f.context.metrics_by_timestamp.size, 0);
});

test('changing rolling average keeps exact raw samples', () => {
    const f = fixture();
    f.handlers.connect();
    f.flush();
    f.respond([
        {ts: f.now - 5000, ok: 3, nok: 0},
        {ts: f.now - 4000, ok: 6, nok: 0},
        {ts: f.now - 3000, ok: 9, nok: 0},
        {ts: f.now - 2000, ok: 12, nok: 0},
    ]);
    f.run('set_rolling_average(3)');
    assert.equal(f.run('myChart.data.datasets[2].data.at(-1).y'), 9);
});

test('live zoom duration survives the history response', () => {
    const f = fixture();
    f.run('options.scales.x.realtime.duration = 10000; myChart.update(); handle_zoom_complete({chart: myChart})');
    f.flush();
    f.respond([]);
    assert.equal(f.run('options.scales.x.realtime.duration'), 10000);
});

test('live panning fetches the visible range, not all intervening history', () => {
    const f = fixture();
    f.run('history_retention = 86400; options.scales.x.realtime.delay = 43200000; myChart.update(); handle_pan_complete({chart: myChart})');
    f.flush();
    const request = f.requests[0].payload;
    assert.equal(request.duration, 330);
    assert.equal(request.end_timestamp, (f.now - 43200000 + 30000) / 1000);
    f.respond([]);
    f.context.history_loaded_end = f.now - 43200000;
    f.run('options.scales.x.realtime.onRefresh()');
    f.flush();
    assert.equal(f.requests[1].payload.duration, 30);
    f.handlers.value({ts: f.now, ok: 1, nok: 0});
    assert.equal(f.context.metrics_by_timestamp.size, 0);
});
