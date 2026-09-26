const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const loaderPath = path.join(__dirname, "..", "js", "analytics-loader.js");
const source = fs.readFileSync(loaderPath, "utf8");

function runOn(hostname) {
  const appended = [];
  const window = { location: { hostname } };
  const document = {
    createElement(tagName) {
      assert.equal(tagName, "script");
      return { async: false, src: "" };
    },
    head: { appendChild(script) { appended.push(script); } },
  };
  vm.runInNewContext(source, { window, document, Date });
  return { window, appended };
}

for (const hostname of ["localhost", "127.0.0.1", "lanceroyy.github.io", ""]) {
  const result = runOn(hostname);
  assert.equal(result.appended.length, 0, `${hostname} must not load GA4`);
  assert.equal(result.window.gtag, undefined, `${hostname} must not queue GA4 events`);
}

for (const hostname of ["homepricemap.us", "www.homepricemap.us"]) {
  const result = runOn(hostname);
  assert.equal(result.appended.length, 1);
  assert.equal(result.appended[0].async, true);
  assert.equal(
    result.appended[0].src,
    "https://www.googletagmanager.com/gtag/js?id=G-2K8JWH5ZKY",
  );
  assert.equal(result.window.dataLayer.length, 2);
  assert.equal(result.window.dataLayer[0][0], "js");
  assert.equal(result.window.dataLayer[1][0], "config");
  assert.equal(result.window.dataLayer[1][1], "G-2K8JWH5ZKY");
  result.window.gtag("event", "profile_click");
  assert.equal(result.window.dataLayer[2][0], "event");
}

console.log("analytics-loader: production-only GA4 checks passed");
