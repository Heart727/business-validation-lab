# 飞书多维表格：演示表字段与配置

应用用飞书 Bitable 作为实时演示记录的外部存储。请新建一份**专用演示多维表格**，不要将个人工作台或真实客户表连接到公开演示。

## 字段

将下列字段名与类型按表创建。API 字段名必须完全一致：

| 字段名 | 类型 | 用途 |
| --- | --- | --- |
| 请求ID | 文本 | UUID 幂等键，用于重试时找回同一条记录 |
| 演示标记 | 文本 | 固定写入 `DEMO` |
| 场景名称 | 文本 | 虚构样例标题 |
| 行业 | 文本 | 样例行业 |
| 产品服务 | 文本 | 样例提供的产品或服务 |
| 目标客群 | 文本 | 样例目标客户描述 |
| 经营问题 | 文本 | 待验证的问题 |
| 现有指标 | 文本 | 虚构基线 |
| 预算范围 | 文本 | 虚构预算描述 |
| 目标 | 文本 | 样例目标 |
| 时间限制 | 文本 | 样例时间范围 |
| 处理状态 | 文本 | 只使用 `processing`、`completed`、`retryable_failed` |
| 经营摘要 | 文本 | 成功后的分析摘要 |
| 关键观察 | 文本 | JSON 字符串数组，含证据/推断/缺失信息标签 |
| 风险 | 文本 | JSON 字符串数组 |
| 7天验证动作 | 文本 | JSON 字符串数组，恰好 7 项 |
| 错误码 | 文本 | 稳定应用错误码；失败记录不保存上游原始正文 |

不要把字段设置为真实客户姓名、手机号或邮箱。本项目的场景目录只允许 10 份虚构商家资料。

## 应用访问

1. 在飞书开放平台创建内部应用，并仅启用调用多维表格记录所需的权限。按实际调用的 [查询记录](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/search) 、[创建记录](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/create) 和 [更新记录](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/update) API 文档申请权限。
2. 为应用开通当前租户要求的多维表格访问范围，并发布应用版本；若 API 权限与多维表格分享范围未同时生效，服务端会返回安全的连接错误。
3. 从多维表格 URL 获取 `app_token` 与 `table_id`，并配置服务端变量 `FEISHU_APP_TOKEN`、`FEISHU_TABLE_ID`。
4. 将 `FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_BASE_URL` 作为服务端变量配置。飞书中国站默认 URL 已列在 `.env.example`；使用其他区域时应按对应开放平台配置。
5. 先在空白演示表中测试一次完整写入、更新和原请求重试，再检查每条记录的 `演示标记` 都是 `DEMO`。

飞书凭证只存本地 `.env` 或 Vercel 环境变量。不要在浏览器、前端构建变量或截图中暴露 App Secret。开放平台权限会随飞书策略变化，请以控制台对当前应用显示的最小权限为准。

本仓库目前没有真实飞书配置，所以公开版不会建立任何飞书记录；测试里的 Feishu gateway 都是本地假服务。
