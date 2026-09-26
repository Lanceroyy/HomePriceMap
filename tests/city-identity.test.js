const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const code = fs.readFileSync(path.join(__dirname, "..", "js", "city-identity.js"), "utf8");
const context = { window: {} };
vm.runInNewContext(code, context);
const identity = context.window.CityIdentity;

const hotSprings = { name: "Hot Springs", state: "AR", county: "Garland County" };
const village = { name: "Hot Springs Village", state: "AR", county: "Garland County" };
const groups = identity.groups([hotSprings, village]);
const crime = { "AR|hotsprings": { name: "Hot Springs Village", state: "AR", population: 15861 } };
const income = { "AR|hotsprings": { name: "Hot Springs city", state: "AR", median_household_income: 47760 } };

assert.equal(identity.matchedSource(hotSprings, crime, groups), null);
assert.equal(identity.matchedSource(village, crime, groups), crime["AR|hotsprings"]);
assert.equal(identity.matchedSource(hotSprings, income, groups, true), income["AR|hotsprings"]);
assert.equal(identity.matchedSource(village, income, groups, true), null);
crime["AR|hotsprings"] = [
  { name: "Hot Springs", state: "AR", population: 38001 },
  { name: "Hot Springs Village", state: "AR", population: 15861 },
];
assert.equal(identity.matchedSource(hotSprings, crime, groups).population, 38001);
assert.equal(identity.matchedSource(village, crime, groups).population, 15861);

const gainesA = { name: "Gaines", state: "MI", county: "Kent County" };
const gainesB = { name: "Gaines", state: "MI", county: "Genesee County" };
const gainesGroups = identity.groups([gainesA, gainesB]);
const gainesCrime = { "MI|gaines": { name: "Gaines", state: "MI", population: 8000 } };
assert.equal(identity.matchedSource(gainesA, gainesCrime, gainesGroups), null);
assert.equal(identity.matchedSource(gainesB, gainesCrime, gainesGroups), null);

assert.equal(identity.hasCoordinates({ lat: 34.02, lon: -118.41 }), true);
assert.equal(identity.hasCoordinates({ lat: null, lon: null }), false);
console.log("city-identity: source matching and coordinate guards passed");
