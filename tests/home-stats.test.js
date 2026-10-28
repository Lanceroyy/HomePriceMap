const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../js/home-stats.js'), 'utf8');

async function run(fetch, includePeriods = true) {
  const ids = ['statCounties', 'statCities', 'statUpdated'];
  if (includePeriods) ids.push('countyDataMonth', 'cityDataMonth');
  const nodes = Object.fromEntries(ids.map(id => [id, {textContent:'Loading…'}]));
  const errors = [];
  vm.runInNewContext(source, {document:{getElementById:id => nodes[id]}, fetch, Date, Intl,
    console:{error: (...args) => errors.push(args)}});
  await new Promise(resolve => setImmediate(resolve));
  return {nodes, errors};
}

(async () => {
  const payload = {county_count:3071, city_count:17640, updated:'2026-10-05T00:30:00Z',
    county_data_period:{oldest:'2026-08-31', newest:'2026-08-31'},
    city_data_period:{oldest:'2026-09-30', newest:'2026-09-30'}};
  let requests = [];
  const good = await run(async url => {
    requests.push(url);
    return {ok:true, json:async () => payload};
  });
  assert.deepEqual(requests, ['/data/site_summary.json']);
  assert.equal(good.nodes.statCounties.textContent, '3,071');
  assert.equal(good.nodes.statCities.textContent, '17,640');
  assert.equal(good.nodes.statUpdated.textContent, 'Oct 5, 2026');
  assert.equal(good.nodes.countyDataMonth.textContent, 'August 2026');
  assert.equal(good.nodes.cityDataMonth.textContent, 'September 2026');
  assert.equal(good.errors.length, 0);
  const mixed = await run(async () => ({ok:true, json:async () => ({...payload,
    city_data_period:{oldest:'2025-12-31', newest:'2026-09-30'}})}));
  assert.equal(mixed.nodes.cityDataMonth.textContent, 'December 2025 – September 2026');
  for (const period of [undefined, null, {}, {oldest:'2026-02-30', newest:'2026-09-30'},
    {oldest:'2026-10-31', newest:'2026-09-30'}, {oldest:'2026-09-30T00:00:00Z', newest:'2026-09-30'}]) {
    const result = await run(async () => ({ok:true, json:async () => ({...payload, city_data_period:period})}));
    assert.equal(result.nodes.cityDataMonth.textContent, 'Unavailable');
    assert.equal(result.nodes.countyDataMonth.textContent, 'August 2026');
    assert.equal(result.nodes.statCities.textContent, '17,640');
  }
  const leap = await run(async () => ({ok:true, json:async () => ({...payload,
    county_data_period:{oldest:'2024-02-29', newest:'2024-02-29'}})}));
  assert.equal(leap.nodes.countyDataMonth.textContent, 'February 2024');
  const legacy = await run(async () => ({ok:true, json:async () => ({county_count:1, city_count:2, updated:payload.updated})}));
  assert.equal(legacy.nodes.statCities.textContent, '2');
  assert.equal(legacy.nodes.countyDataMonth.textContent, 'Unavailable');
  const oldMarkup = await run(async () => ({ok:true, json:async () => payload}), false);
  assert.equal(oldMarkup.nodes.statUpdated.textContent, 'Oct 5, 2026');
  for (const [updated, expected] of [['2024-02-29T00:30:00Z', 'Feb 29, 2024'],
                                   ['2026-10-05T07:40:35.228667Z', 'Oct 5, 2026']]) {
    const valid = await run(async () => ({ok:true, json:async () => ({...payload, updated})}));
    assert.equal(valid.nodes.statUpdated.textContent, expected);
  }
  for (const fetch of [
    async () => {throw new Error('offline');},
    async () => ({ok:false, status:404}),
    async () => ({ok:true, json:async () => {throw new SyntaxError('invalid JSON');}}),
    ...[null, {}, {...payload, city_count:-1}, {...payload, county_count:'3071'},
      {...payload, county_count:1.5}, {...payload, updated:'invalid'},
      {...payload, updated:null}].map(value => async () => ({ok:true, json:async () => value})),
    ...['2026-10-05T00:30:00', '2026-02-30T00:30:00Z', '2026-13-01T00:30:00Z',
        '2026-01-01T24:00:00Z', '2026-10-05T00:30:00Zjunk'].map(updated =>
      async () => ({ok:true, json:async () => ({...payload, updated})})),
  ]) {
    const failure = await run(fetch);
    assert.ok(Object.values(failure.nodes).every(node => node.textContent === 'Unavailable'));
    assert.equal(failure.errors.length, 1);
  }
  const zero = await run(async () => ({ok:true, json:async () => ({...payload, city_count:0, county_count:0})}));
  assert.equal(zero.nodes.statCities.textContent, '0');
  const absent = await run(undefined);
  assert.equal(absent.nodes.statUpdated.textContent, 'Unavailable');
  console.log('home-stats: summary request, UTC date, counts and failure paths passed');
})().catch(error => {console.error(error); process.exitCode = 1;});
