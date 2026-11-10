const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "..", "js", "common.js"), "utf8");
const context = { document: { addEventListener() {} } };
vm.runInNewContext(source, context);

test("each deliberate map selection starts at the top of a scrolled details card", () => {
  for (const track of ["search", "map_click", "deep_link"]) {
    const card = { innerHTML: "", scrollTop: 192 };
    context.showInfo(card, { title: "New place", value: 400000, yoy: 0, track });
    assert.match(card.innerHTML, /New place/);
    assert.equal(card.scrollTop, 0, track);
  }
});

test("county hover previews do not write the details card scroll position", () => {
  const card = { innerHTML: "", scrollTop: 192 };
  context.showInfo(card, { title: "Preview", value: 400000, yoy: 0 });
  assert.match(card.innerHTML, /Preview/);
  assert.equal(card.scrollTop, 192);
});
