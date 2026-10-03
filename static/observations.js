(function exposeObservationGrouper(root, factory) {
  const { groupObservations } = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = { groupObservations };
  } else {
    root.groupObservations = groupObservations;
  }
})(typeof window === "undefined" ? globalThis : window, function createObservationGrouper() {
  const labels = ["证据", "推断", "缺失信息"];

  function groupObservations(observations) {
    const grouped = new Map(labels.map((label) => [label, []]));

    for (const value of observations || []) {
      const text = String(value).trimStart();
      const match = text.match(/^(证据|推断|缺失信息)[：:](.*)$/s);
      if (!match || !grouped.has(match[1])) continue;
      const content = match[2].trim();
      if (content) grouped.get(match[1]).push(content);
    }

    return Object.fromEntries(labels.map((label) => [label, grouped.get(label).join("\n")]));
  }

  return { groupObservations };
});
