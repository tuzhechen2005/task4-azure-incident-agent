"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const { createPollController } = require("../../frontend/app.js");

function payload(path) {
  if (path === "/api/health") return { status: "healthy" };
  if (path === "/api/stats") return { total: 1 };
  return { items: [{ incident: { incident_id: "inc-1" } }] };
}

function timerHarness() {
  const timers = [];
  return {
    timers,
    setIntervalFn(callback, milliseconds) {
      const timer = { callback, milliseconds, cleared: false };
      timers.push(timer);
      return timer;
    },
    clearIntervalFn(timer) { timer.cleared = true; },
  };
}

test("test_poll_on_initial_load", async () => {
  const requests = [];
  const successes = [];
  const timers = timerHarness();
  const controller = createPollController({
    fetchJson: async (path) => { requests.push(path); return payload(path); },
    intervalMs: 5000,
    onSuccess: (value) => successes.push(value),
    onError: () => assert.fail("unexpected error"),
    ...timers,
  });

  await controller.start();

  assert.deepEqual(requests, ["/api/health", "/api/stats", "/api/incidents?page=1&page_size=100"]);
  assert.equal(successes[0].incidents.length, 1);
});

test("test_poll_at_configured_interval", async () => {
  let requestCount = 0;
  const timers = timerHarness();
  const controller = createPollController({
    fetchJson: async (path) => { requestCount += 1; return payload(path); },
    intervalMs: 7000,
    onSuccess: () => {},
    onError: () => assert.fail("unexpected error"),
    ...timers,
  });

  await controller.start();
  await timers.timers[0].callback();

  assert.equal(timers.timers[0].milliseconds, 7000);
  assert.equal(requestCount, 6);
});

test("test_poll_prevents_overlap", async () => {
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  const controller = createPollController({
    fetchJson: async (path) => { await gate; return payload(path); },
    intervalMs: 1000,
    onSuccess: () => {},
    onError: () => assert.fail("unexpected error"),
    ...timerHarness(),
  });

  const first = controller.refresh();
  const overlapping = await controller.refresh();
  release();
  await first;

  assert.equal(overlapping, false);
});

test("test_poll_error_retains_last_data", async () => {
  let fail = false;
  let lastData = null;
  let errorCount = 0;
  const timers = timerHarness();
  const controller = createPollController({
    fetchJson: async (path) => { if (fail) throw new Error("offline"); return payload(path); },
    intervalMs: 1000,
    onSuccess: (value) => { lastData = value; },
    onError: () => { errorCount += 1; },
    ...timers,
  });

  await controller.start();
  const previous = lastData;
  fail = true;
  await timers.timers[0].callback();

  assert.equal(lastData, previous);
  assert.equal(errorCount, 1);
});

test("test_poll_recovers", async () => {
  let fail = true;
  let successCount = 0;
  let errorCount = 0;
  const timers = timerHarness();
  const controller = createPollController({
    fetchJson: async (path) => { if (fail) throw new Error("offline"); return payload(path); },
    intervalMs: 1000,
    onSuccess: () => { successCount += 1; },
    onError: () => { errorCount += 1; },
    ...timers,
  });

  await controller.start();
  fail = false;
  await timers.timers[0].callback();

  assert.equal(errorCount, 1);
  assert.equal(successCount, 1);
});
