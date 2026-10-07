// A single tiny summary replaces two full datasets used only for three numbers.
(async function () {
  const nodes = ['statCounties', 'statCities', 'statUpdated'].map(id => document.getElementById(id));
  if (nodes.some(node => !node)) return;
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
  } catch (error) {
    nodes.forEach(node => { node.textContent = 'Unavailable'; });
    console.error('Failed to load homepage stats', error);
  }
})();
