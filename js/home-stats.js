// Keep counts, observation months and retrieval time in one tiny summary request.
(async function () {
  const nodes = ['statCounties', 'statCities', 'statUpdated'].map(id => document.getElementById(id));
  if (nodes.some(node => !node)) return;
  const periodNodes = ['countyDataMonth', 'cityDataMonth'].map(id => document.getElementById(id));
  function periodLabel(period) {
    function sourceDate(value) {
      if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
      const date = new Date(value + 'T00:00:00Z');
      return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value ? date : null;
    }
    const first = period && sourceDate(period.oldest);
    const last = period && sourceDate(period.newest);
    if (!first || !last || first > last) return 'Unavailable';
    const format = new Intl.DateTimeFormat('en-US', {month:'long', year:'numeric', timeZone:'UTC'});
    const start = format.format(first);
    const end = format.format(last);
    return start === end ? start : start + ' – ' + end;
  }
  try {
    const response = await fetch('/data/site_summary.json');
    if (!response.ok) throw new Error('Stats request failed: ' + response.status);
    const stats = await response.json();
    // fetch_data.py emits UTC ISO timestamps with a Z and optional microseconds.
    // Date alone accepts impossible dates and local-time (zone-less) strings.
    const timestamp = stats && typeof stats.updated === 'string' &&
      /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?Z$/.exec(stats.updated);
    if (!stats || !Number.isSafeInteger(stats.county_count) || stats.county_count < 0 ||
        !Number.isSafeInteger(stats.city_count) || stats.city_count < 0 ||
        !timestamp) {
      throw new Error('Invalid homepage stats');
    }
    const updated = new Date(stats.updated);
    const parts = [updated.getUTCFullYear(), updated.getUTCMonth() + 1, updated.getUTCDate(),
      updated.getUTCHours(), updated.getUTCMinutes(), updated.getUTCSeconds()];
    if (parts.some((part, index) => part !== Number(timestamp[index + 1]))) {
      throw new Error('Invalid stats refresh date');
    }
    const date = new Intl.DateTimeFormat('en-US', {
      month:'short', day:'numeric', year:'numeric', timeZone:'UTC',
    }).format(updated);
    nodes[0].textContent = stats.county_count.toLocaleString('en-US');
    nodes[1].textContent = stats.city_count.toLocaleString('en-US');
    nodes[2].textContent = date;
    // Old cached summaries can still supply counters while a source refresh
    // introduces the new period fields. Never infer a month from updated.
    [stats.county_data_period, stats.city_data_period].forEach((period, index) => {
      if (periodNodes[index]) periodNodes[index].textContent = periodLabel(period);
    });
  } catch (error) {
    nodes.concat(periodNodes).filter(Boolean).forEach(node => { node.textContent = 'Unavailable'; });
    console.error('Failed to load homepage stats', error);
  }
})();
