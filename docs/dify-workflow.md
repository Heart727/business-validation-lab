# Dify Workflow 与 DeepSeek

FastAPI 将固定虚构商家资料提交给已发布的 Dify Workflow，并只接受经过结构校验的结果。Workflow API 使用 blocking 响应，以便 API 能在一次限时请求中完成写表。

## Workflow 输入和输出

创建 Workflow，输入变量为：

| 变量 | 类型 | 说明 |
| --- | --- | --- |
| `scenario_json` | 文本 | 服务端提供的一份虚构场景 JSON |

服务端另将请求 UUID（`request_id`）作为 Dify API 的 `user` 字段传入，供该次执行关联；它不是 Workflow 的输入变量，不包含访客个人信息。

建议的节点顺序：开始 → LLM → 结束。LLM 节点根据场景资料形成摘要、观察、风险与行动，结束节点必须输出字符串 `analysis_json`，其内容为 JSON：

```json
{
  "executive_summary": "先记录基线，再用小样本验证",
  "observations": [
    "证据：资料给出的现状指标……",
    "推断：可能的经营解释……",
    "缺失信息：尚未提供、需要在实验中记录……"
  ],
  "risks": ["样本偏小，结果不能直接代表长期表现"],
  "seven_day_actions": [
    {"day": 1, "action": "记录基线", "metric": "每日订单数", "decision_rule": "先确认记录口径"},
    {"day": 2, "action": "执行小样本测试", "metric": "点击或咨询数", "decision_rule": "保持条件一致"},
    {"day": 3, "action": "继续记录", "metric": "有效咨询数", "decision_rule": "区分新客与老客"},
    {"day": 4, "action": "检查反馈", "metric": "转化数", "decision_rule": "记录异常原因"},
    {"day": 5, "action": "对比基线", "metric": "转化率", "decision_rule": "使用相同统计口径"},
    {"day": 6, "action": "整理成本", "metric": "单次获客成本", "decision_rule": "纳入实际支出"},
    {"day": 7, "action": "作出继续或停止决定", "metric": "预先约定的核心指标", "decision_rule": "按测试前设定的门槛决定"}
  ]
}
```

以上只是格式示例，不是对经营结果的承诺。`observations` 必须同时有内容非空的「证据」「推断」「缺失信息」条目；`seven_day_actions` 必须包含第 1 至第 7 天且每一天仅一次，共七项行动，所有字符串字段不可为空。FastAPI 会拒绝格式不符的输出，不会将其标为完成。

## 模型设置

在 Dify 的模型供应商设置中配置用户自己的 DeepSeek API 凭证，并在 LLM 节点选择可用模型。DeepSeek 提供 OpenAI 兼容接口，官方 API 基础地址为 `https://api.deepseek.com`；可查阅 [DeepSeek API 首次调用说明](https://api-docs.deepseek.com/guides/codex) 与 [当前 API 更新](https://api-docs.deepseek.com/updates/)。模型和价格可能调整，按 DeepSeek 控制台当前列出的模型与价格选择。

API key 只输入 Dify 的服务端供应商配置，不要写进提示词、Workflow 输出、代码或 Vercel 环境变量。Dify workflow API key 另行生成，仅保存在 FastAPI 服务端变量 `DIFY_WORKFLOW_API_KEY`。服务调用 `/workflows/run` 时使用 `response_mode=blocking`，Workflow 发布后响应必须包含 `data.status=succeeded` 与 `data.outputs.analysis_json`。

## 发布前检查

1. 使用以上示例结构在 Dify 内调试，检查 JSON 可以解析且包含 7 条行动。
2. 发布 Workflow，再由服务端调用其 API；未发布的草稿不能供 API 执行。
3. 查看 Dify 工作空间额度和 DeepSeek 账号用量。公开样例每次真实提交都会使用外部服务额度。
4. 将 workflow API key 加入 Vercel 的服务端环境变量，保持 `DEMO_MODE=false` 直到飞书专用表和 Vercel 限流规则也都验证完成。

当前仓库未配置或调用真实 Dify/DeepSeek；自动化测试使用固定假响应。
