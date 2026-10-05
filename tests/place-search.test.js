const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const source = fs.readFileSync(path.join(__dirname, "..", "js", "place-search.js"), "utf8");
const records = [
  { id: "city:ca-los-angeles", name: "Los Angeles", state: "CA", type: "city", county: "Los Angeles County", url: "/cities/ca-los-angeles.html" },
  { id: "county:06037", name: "Los Angeles County", state: "CA", type: "county", url: "/counties/ca-los-angeles-county.html" },
  { id: "city:ca-beverly-hills", name: "Beverly Hills", state: "CA", type: "city", county: "Los Angeles County" },
  { id: "city:mi-beverly-hills", name: "Beverly Hills", state: "MI", type: "city", county: "Oakland County" },
  { id: "city:nc-chapel-hill", name: "Chapel Hill", state: "NC", type: "city", county: "Orange County" },
  { id: "city:nm-espanola", name: "Española", state: "NM", type: "city" },
];

function setup(fetchImpl = async () => ({ ok: true, json: async () => ({ places: records }) }), window = { setTimeout, clearTimeout }, document = {}) {
  vm.runInNewContext(source, { window, fetch: fetchImpl, console, document });
  return window.HomePriceSearch;
}

test("published profiles match full states, reordered terms, and partial words", async () => {
  const search = setup();
  const places = await search.loadCatalog();
  for (const query of ["Los Angeles California", "California Los Angeles", "CA Los Ang", "Los Angeles, CA", "California city Los Angeles", "city Los Angeles"])
    assert.equal(search.findMatches(places, query, 8)[0].id, "city:ca-los-angeles", query);
  assert.deepEqual(Array.from(search.findMatches(places, "Beverly Hills Michigan", 8), p => p.id), ["city:mi-beverly-hills"]);
  assert.equal(search.findMatches(places, "North Carolina Chapel", 8)[0].id, "city:nc-chapel-hill");
  assert.equal(search.findMatches(places, "Espanola New Mexico", 8)[0].id, "city:nm-espanola");
});

test("exact names outrank county association; short and unrelated queries stay empty", async () => {
  const search = setup();
  const places = await search.loadCatalog();
  assert.equal(search.findMatches(places, "Los Angeles", 8)[0].id, "city:ca-los-angeles");
  assert.equal(search.findMatches(places, "Los Angeles County", 8)[0].id, "county:06037");
  assert.equal(search.findMatches(places, "Beverly Hills California", 8)[0].id, "city:ca-beverly-hills");
  for (const query of ["", "a", "not a published place", "Beverly Hills Texas"])
    assert.equal(search.findMatches(places, query, 8).length, 0);
  assert.equal(search.findMatches(places, "Los Angeles", 1).length, 1);
});

test("a failed catalog load retries instead of caching a rejection", async () => {
  let attempts = 0;
  const search = setup(async () => {
    if (++attempts === 1) return { ok: false, status: 503 };
    return { ok: true, json: async () => ({ places: records }) };
  });
  await assert.rejects(search.loadCatalog(), /503/);
  assert.equal((await search.loadCatalog()).length, records.length);
  assert.equal(attempts, 2);
});

class Element {
  constructor() {
    this.children = [];
    this.attributes = new Map();
    this.listeners = new Map();
    this.classList = { toggle() {} };
    this.value = "";
    this.hidden = true;
    this.id = "search";
  }
  setAttribute(name, value) { this.attributes.set(name, value); }
  removeAttribute(name) { this.attributes.delete(name); }
  addEventListener(name, handler) { this.listeners.set(name, handler); }
  fire(name, data = {}) { return this.listeners.get(name)?.({ preventDefault() {}, ...data }); }
  append(...items) { this.children.push(...items); }
  appendChild(item) { this.children.push(item); }
  replaceChildren(...items) { this.children = items; }
  querySelectorAll() { return this.children.filter(item => item.attributes.get("role") === "option"); }
  scrollIntoView() {}
}

function ui(fetchImpl, gtag) {
  const timers = new Map();
  let nextTimer = 0;
  const window = {
    gtag,
    setTimeout(callback) { timers.set(++nextTimer, callback); return nextTimer; },
    clearTimeout(id) { timers.delete(id); },
  };
  const search = setup(fetchImpl, window, { createElement: () => new Element() });
  const input = new Element();
  const list = new Element();
  const selected = [];
  const controller = search.attach(input, list, { surface: "homepage", onSelect: place => selected.push(place.id) });
  return { search, input, list, selected, controller, timers };
}

test("keyboard and click selection measure published records, never raw search text", async () => {
  const events = [];
  const view = ui(undefined, (...event) => events.push(event));
  view.input.value = "Los Angeles California";
  await view.controller.update();
  view.input.fire("keydown", { key: "ArrowDown" });
  assert.equal(view.input.attributes.get("aria-activedescendant"), "search-option-0");
  view.input.fire("keydown", { key: "Enter" });
  assert.deepEqual(view.selected, ["city:ca-los-angeles"]);
  assert.equal(view.list.hidden, true);
  assert.deepEqual(JSON.parse(JSON.stringify(events[0])), ["event", "place_search_select", {
    place_id: "city:ca-los-angeles", place_type: "city", state: "CA", search_surface: "homepage",
  }]);
  view.input.value = "Los Angeles California";
  await view.controller.update();
  view.list.children[0].fire("click");
  assert.equal(view.selected.length, 2);
  assert.equal(events.length, 2);
});

test("analytics absent or throwing cannot prevent profile selection", async () => {
  for (const gtag of [undefined, () => { throw new Error("blocked"); }]) {
    const view = ui(undefined, gtag);
    view.input.value = "Los Angeles CA";
    await view.controller.update();
    view.list.children[0].fire("click");
    assert.deepEqual(view.selected, ["city:ca-los-angeles"]);
  }
});

test("changing query clears active options before the next async result", async () => {
  const view = ui();
  view.input.value = "Los Angeles";
  await view.controller.update();
  view.input.fire("keydown", { key: "ArrowDown" });
  view.input.value = "Beverly Hills Michigan";
  const pending = view.controller.update();
  view.input.fire("keydown", { key: "Enter" });
  assert.equal(view.selected.length, 0);
  await pending;
  view.input.fire("keydown", { key: "ArrowDown" });
  view.input.fire("keydown", { key: "Enter" });
  assert.deepEqual(view.selected, ["city:mi-beverly-hills"]);
});

test("blur and Escape cancel slow responses instead of reopening the list", async () => {
  for (const cancel of [view => view.input.fire("blur"), view => view.input.fire("keydown", { key: "Escape" })]) {
    let resolveFetch;
    const view = ui(() => new Promise(resolve => { resolveFetch = resolve; }));
    view.input.value = "Los Angeles";
    const pending = view.controller.update();
    cancel(view);
    for (const callback of view.timers.values()) callback();
    resolveFetch({ ok: true, json: async () => ({ places: records }) });
    await pending;
    assert.equal(view.list.hidden, true);
    assert.equal(view.list.querySelectorAll().length, 0);
  }
});

test("a rapid refocus cancels the old blur timer", async () => {
  const view = ui();
  view.input.value = "Los Angeles";
  await view.controller.update();
  view.input.fire("blur");
  view.input.fire("focus");
  assert.equal(view.timers.size, 0);
  assert.equal(view.list.hidden, false);
});
