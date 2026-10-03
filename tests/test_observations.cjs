const assert = require("node:assert/strict");
const { test } = require("node:test");

const { groupObservations } = require("../static/observations.js");

test("trims leading whitespace and keeps every valid observation", () => {
  const grouped = groupObservations([
    "  证据：来源 A",
    "证据: 来源 B",
    " 推断：推理内容",
    "\t缺失信息：待补资料",
  ]);

  assert.deepEqual(grouped, {
    "证据": "来源 A\n来源 B",
    "推断": "推理内容",
    "缺失信息": "待补资料",
  });
});

test("empty and unrelated values do not create invented observations", () => {
  assert.deepEqual(groupObservations(["其他：不属于已知标签", "   "]), {
    "证据": "",
    "推断": "",
    "缺失信息": "",
  });
});
