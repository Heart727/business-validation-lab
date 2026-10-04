# AI 经营分析与 7 天验证助手 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一个面试官可匿名体验的作品集应用，让 10 份虚构商家资料经过 FastAPI、飞书多维表格和 Dify/DeepSeek，生成并记录经营分析及 7 天验证动作。

**Architecture:** Python FastAPI 同时提供 API 与静态页面。`PipelineService` 先在专用飞书演示表创建 `processing` 记录，再调用 Dify Workflow，校验输出后更新同一记录；失败保留可重试状态。公开页面只允许选择仓库内的固定样例，Dify 与飞书密钥始终保存在服务端。

**Tech Stack:** Python 3.12、FastAPI、Pydantic v2、httpx、原生 HTML/CSS/JavaScript、Dify Cloud Workflow、DeepSeek、Feishu Bitable、Vercel Hobby、pytest。

**Spec:** `docs/superpowers/specs/2026-10-03-ai-business-validation-design.md`

## Global Constraints

- 唯一 AI 工作流平台是 Dify；不加入 n8n。
- 表单只接受 `data/scenarios.json` 中的 10 个虚构场景 ID；不接收自由文本或个人信息。
- 飞书记录只写入用户配置的专用演示表，所有记录标记 `DEMO`。
- 运行状态只使用 `processing`、`completed`、`retryable_failed`。
- 每份成功分析必须含恰好 7 个行动项；证据、推断和缺失信息必须分开表达。
- Dify Workflow API Key、DeepSeek API Key、飞书 App Secret 不得进入浏览器、日志、截图或 Git。
- FastAPI 外部请求设置超时，总请求耗时不得超过 Vercel Hobby 函数 60 秒上限。
- Vercel 公开分析入口启用 WAF IP 限流：固定窗口每 10 分钟最多 5 次；启用线上演示前先确认规则已发布。
- 未配置外部服务时，API 关闭真实集成，页面只允许展示明确标记的静态预览。
- 不自动开通付费服务；DeepSeek 实测会计入用户 API 额度并写入飞书演示表。

---

### Task 1: 建立项目骨架、场景目录与数据契约

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/schemas.py`
- Create: `app/services/__init__.py`
- Create: `app/services/scenarios.py`
- Create: `data/scenarios.json`
- Create: `data/example_analysis.json`
- Create: `tests/conftest.py`
- Create: `tests/test_scenarios.py`
- Create: `tests/test_schemas.py`

**Interfaces:**
- `Settings.from_env() -> Settings` validates service configuration without logging secret values.
- `ScenarioCatalog.load(path: Path) -> ScenarioCatalog`; `ScenarioCatalog.get(scenario_id: str) -> Scenario` raises `UnknownScenario` when absent; `ScenarioCatalog.all() -> list[Scenario]` returns the ten immutable fixtures.
- `AnalysisOutput` has `executive_summary: str`, `observations: list[str]`, `risks: list[str]`, and `seven_day_actions: list[DayAction]`.
- `DayAction` has `day: int`, `action: str`, `metric: str`, `decision_rule: str`; valid days are exactly 1 through 7, once each.

- [ ] **Step 1: Add the minimal dependency manifest and install the test environment.** Add `fastapi>=0.115,<1`, `uvicorn[standard]>=0.30,<1`, `httpx>=0.27,<1`, `pydantic>=2.8,<3`, `pydantic-settings>=2.4,<3`, `python-dotenv>=1,<2`, `pytest>=8,<9`, and `pytest-asyncio>=0.23,<1` to `requirements.txt`. Add `.gitignore` entries for `.venv/`, `.env`, `__pycache__/`, `.pytest_cache/`, `.vercel/`, and screenshot temp files. Add only variable names and harmless local defaults in `.env.example`.

Run in PowerShell: `python -m venv .venv; ./.venv/Scripts/python.exe -m pip install -r requirements.txt`

Expected: dependencies install without any service credentials.

- [ ] **Step 2: Write failing contract tests.** Create `tests/test_scenarios.py`:

```python
from pathlib import Path

import pytest

from app.services.scenarios import ScenarioCatalog, UnknownScenario


def test_catalog_contains_ten_unique_fictional_scenarios():
    catalog = ScenarioCatalog.load(Path("data/scenarios.json"))
    scenarios = catalog.all()
    assert len(scenarios) == 10
    assert len({item.id for item in scenarios}) == 10
    forbidden = {"name", "phone", "email", "contact"}
    assert all(forbidden.isdisjoint(item.model_dump()) for item in scenarios)


def test_unknown_scenario_is_rejected():
    catalog = ScenarioCatalog.load(Path("data/scenarios.json"))
    with pytest.raises(UnknownScenario):
        catalog.get("not-a-scenario")
```

Add shared `settings`, `scenario`, and `REQUEST_ID` fixtures/constants to `tests/conftest.py`; `scenario` is loaded from the first fixture in `data/scenarios.json`, `settings` uses fake non-secret values with `demo_mode=False`, and `REQUEST_ID` is the fixed test UUID `0e9dbe92-0fc0-4cc2-9b5e-d7baccc04853`.

- [ ] **Step 3: Run the focused test and verify it fails** because the catalog module does not exist.

Run: `.venv/Scripts/python.exe -m pytest tests/test_scenarios.py -q`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Add typed request/output models and configuration.** Use `pydantic-settings` for `.env` loading; fields include `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_APP_TOKEN`, `FEISHU_TABLE_ID`, `DIFY_BASE_URL`, `DIFY_WORKFLOW_API_KEY`, and `DEMO_MODE`. Default live integration to false. Model `Scenario` with `id`, `title`, `industry`, `offering`, `target_customer`, `business_problem`, `current_metrics`, `budget_range`, `goal`, and `time_limit`. Reject unknown input fields. `data/scenarios.json` contains these ten fictional businesses: breakfast catering, neighborhood coffee, online florist, personal training studio, pet grooming shop, secondhand clothing store, tutoring studio, wedding planner, commercial cleaning service, and home bakery. Add a fully fictional `data/example_analysis.json` as a clearly labeled offline preview.

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    demo_mode: bool = False
    feishu_app_id: str | None = None
    feishu_app_secret: str | None = None
    feishu_app_token: str | None = None
    feishu_table_id: str | None = None
    dify_base_url: str = "https://api.dify.ai/v1"
    dify_workflow_api_key: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()

    @property
    def live_demo_ready(self) -> bool:
        required = (self.feishu_app_id, self.feishu_app_secret, self.feishu_app_token,
                    self.feishu_table_id, self.dify_workflow_api_key)
        return self.demo_mode and all(required)
```

- [ ] **Step 5: Implement `ScenarioCatalog` and schema validation.** The output model validator must enforce `sorted(action.day for action in value) == [1, 2, 3, 4, 5, 6, 7]`; reject extra or missing actions.

```python
class AnalysisOutput(BaseModel):
    executive_summary: str = Field(min_length=1, max_length=1200)
    observations: list[str] = Field(min_length=1, max_length=8)
    risks: list[str] = Field(max_length=8)
    seven_day_actions: list[DayAction] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def require_seven_distinct_days(self):
        if sorted(item.day for item in self.seven_day_actions) != list(range(1, 8)):
            raise ValueError("seven_day_actions must contain days 1 through 7 once")
        return self
```

- [ ] **Step 6: Add tests for valid/invalid model output and configuration.** Assert six or eight actions fail, duplicated day numbers fail, and missing required server settings keep live submission disabled.

- [ ] **Step 7: Run the focused tests.**

Run: `.venv/Scripts/python.exe -m pytest tests/test_scenarios.py tests/test_schemas.py -q`

Expected: PASS; all ten fixture IDs are unique and contain no contact fields.

- [ ] **Step 8: Commit.**

```bash
git add requirements.txt .gitignore .env.example app data tests
git commit -m "feat: add project contracts and fictional scenarios"
```

### Task 2: Implement the Feishu Bitable gateway

**Files:**
- Create: `app/services/feishu.py`
- Create: `tests/test_feishu.py`
- Modify: `app/config.py`

**Interfaces:**
- `FeishuClient(settings: Settings, http_client: httpx.AsyncClient)` receives its HTTP client for deterministic tests.
- `FeishuClient.get_tenant_token() -> str`
- `FeishuClient.create_processing_record(token: str, request_id: str, scenario: Scenario) -> FeishuRecord`
- `FeishuClient.find_by_request_id(token: str, request_id: str) -> FeishuRecord | None`
- `FeishuClient.update_record(token: str, record_id: str, fields: dict[str, object]) -> None`
- `FeishuRecord` contains `record_id`, `request_id`, `status`, and optional parsed `analysis`.
- Raise only sanitized `FeishuError(code: str)` values to the application layer; never include tokens or raw response bodies in logs/errors.

- [ ] **Step 1: Write failing HTTP contract tests using `httpx.MockTransport`.** Verify token acquisition posts app credentials to `/open-apis/auth/v3/tenant_access_token/internal`; record calls use `Authorization: Bearer ...`; create/update use the configured app token and table ID; Feishu responses with nonzero `code`, 401, 429, or malformed JSON raise a sanitized `FeishuError`.

```python
@pytest.mark.asyncio
async def test_feishu_nonzero_code_is_sanitized(settings):
    response = httpx.Response(200, json={"code": 99991663, "msg": "permission denied", "data": {}})
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: response))
    client = FeishuClient(settings, http_client=http_client)
    with pytest.raises(FeishuError) as error:
        await client.get_tenant_token()
    assert error.value.code == "feishu_auth_failed"
    assert "permission denied" not in str(error.value)
    assert settings.feishu_app_secret not in str(error.value)
```

- [ ] **Step 2: Run the focused test and verify it fails.**

Run: `.venv/Scripts/python.exe -m pytest tests/test_feishu.py -q`

Expected: FAIL because `app.services.feishu` is absent.

- [ ] **Step 3: Implement a small async HTTP client.** The pipeline obtains one tenant token and reuses it for all Bitable requests in that invocation. Use `httpx.AsyncClient` with a five-second token timeout and a five-second timeout per Bitable call; map these endpoints:

```text
POST /open-apis/auth/v3/tenant_access_token/internal
POST /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records
GET  /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records?filter=CurrentValue.%5B请求ID%5D%20%3D%20%22{request_id}%22
PUT  /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}
```

Use `request_id` as a text field and the Feishu filter to find existing records. A zero-result query returns `None`; more than one result raises `feishu_duplicate_request_id` rather than updating an arbitrary row. Map the scenario and state into fixed text fields: `请求ID`, `演示标记`, `场景名称`, `行业`, `产品服务`, `目标客群`, `经营问题`, `现有指标`, `预算范围`, `目标`, `时间限制`, `处理状态`, `经营摘要`, `关键观察`, `风险`, `7天验证动作`, and `错误码`. Serialize list fields as UTF-8 JSON strings. Never accept a table ID from the request body.

- [ ] **Step 4: Implement create/find/update and sanitized error mapping.** Only treat Feishu `code == 0` with the expected data structure as success. Set `演示标记=DEMO` and `处理状态=processing` before the Dify call.

```python
def _require_success(payload: dict[str, object], error_code: str) -> dict[str, object]:
    if payload.get("code") != 0:
        raise FeishuError(error_code)
    data = payload.get("data")
    if not isinstance(data, dict):
        raise FeishuError("feishu_invalid_response")
    return data
```

- [ ] **Step 5: Run gateway tests and inspect request payloads.**

Run: `.venv/Scripts/python.exe -m pytest tests/test_feishu.py -q`

Expected: PASS; mock assertions confirm server-side auth headers, correct record field names, and no secret in public errors.

- [ ] **Step 6: Commit.**

```bash
git add app/services/feishu.py app/config.py tests/test_feishu.py
git commit -m "feat: add Feishu Bitable gateway"
```

### Task 3: Implement the Dify workflow client

**Files:**
- Create: `app/services/dify.py`
- Create: `tests/test_dify.py`
- Modify: `app/config.py`

**Interfaces:**
- `DifyClient(settings: Settings, http_client: httpx.AsyncClient)` receives its HTTP client for deterministic tests.
- `DifyClient.run_workflow(scenario: Scenario, request_id: str) -> AnalysisOutput`
- Raise `DifyError(code: str)` for timeout, upstream failure, quota rejection, or invalid output.

- [ ] **Step 1: Write failing client tests.** Use `httpx.MockTransport` to test a valid blocking workflow response, API 401, 429, a timeout, a non-JSON body, and an output with only six actions. Define a `dify_client` fixture whose fake 200 response has `data.outputs.analysis_json` containing valid JSON with seven distinct actions; reuse the shared `scenario` fixture from `tests/conftest.py`.

```python
@pytest.mark.asyncio
async def test_run_workflow_validates_analysis_json(dify_client, scenario):
    result = await dify_client.run_workflow(scenario, "0e9dbe92-0fc0-4cc2-9b5e-d7baccc04853")
    assert isinstance(result, AnalysisOutput)
    assert [item.day for item in result.seven_day_actions] == list(range(1, 8))
```

- [ ] **Step 2: Run the focused test and verify it fails.**

Run: `.venv/Scripts/python.exe -m pytest tests/test_dify.py -q`

Expected: FAIL because `app.services.dify` is absent.

- [ ] **Step 3: Implement the Dify client.** POST to `{DIFY_BASE_URL}/workflows/run` with `Authorization: Bearer {DIFY_WORKFLOW_API_KEY}`, `response_mode="blocking"`, `user=request_id`, and `inputs.scenario_json` containing only the server-loaded fictional scenario. Expect published workflow output key `analysis_json` under the blocking response's `data.outputs`. Set a 30-second request timeout. Parse JSON and validate it with `AnalysisOutput`; rely on the workflow prompt and output schema to separate facts from assumptions and prohibit guaranteed outcomes.

```python
response = await self.http_client.post(
    f"{self.base_url}/workflows/run",
    headers={"Authorization": f"Bearer {self.api_key}"},
    json={"response_mode": "blocking", "user": request_id,
          "inputs": {"scenario_json": scenario.model_dump_json()}},
    timeout=30.0,
)
response.raise_for_status()
payload = response.json()["data"]["outputs"]["analysis_json"]
return AnalysisOutput.model_validate_json(payload)
```

- [ ] **Step 4: Run client tests.**

Run: `.venv/Scripts/python.exe -m pytest tests/test_dify.py -q`

Expected: PASS; every non-success response is converted to a stable error code without echoing the API key or upstream body.

- [ ] **Step 5: Commit.**

```bash
git add app/services/dify.py app/config.py tests/test_dify.py
git commit -m "feat: add Dify workflow client"
```

### Task 4: Coordinate record creation, analysis, retries, and status

**Files:**
- Create: `app/services/pipeline.py`
- Create: `tests/test_pipeline.py`
- Modify: `app/schemas.py`

**Interfaces:**
- `PipelineService(feishu: FeishuClient, dify: DifyClient, scenarios: ScenarioCatalog)`
- `async PipelineService.submit(scenario_id: str, request_id: str) -> PipelineResult`
- `PipelineResult` contains `request_id`, `status`, `analysis | None`, and `error_code | None`.

- [ ] **Step 1: Write failing order and failure tests with recording fakes.** Assert the first call order is token → find → create `processing` record → Dify → update `completed`; a Dify timeout updates the same record to `retryable_failed`; a retry reuses the existing record ID; a completed retry returns the saved result without another Dify call; Feishu lookup/create failures do not call Dify.

```python
@pytest.mark.asyncio
async def test_timeout_marks_existing_row_retryable(pipeline, fake_feishu, fake_dify):
    fake_dify.error = DifyError("dify_timeout")
    result = await pipeline.submit("coffee_shop", REQUEST_ID)
    assert result.status == "retryable_failed"
    assert fake_feishu.rows[REQUEST_ID].fields["处理状态"] == "retryable_failed"
    assert fake_feishu.create_count == 1
```

- [ ] **Step 2: Run the focused test and verify it fails.**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -q`

Expected: FAIL because the pipeline module is absent.

- [ ] **Step 3: Implement the pipeline state transitions.** Validate the scenario before any external request. Obtain one tenant token; find a record by `request_id`; if missing, create it as `processing`. If its status is `completed`, return its stored analysis. Otherwise call Dify, then update the same record with `completed`, output JSON, and empty error code. For `DifyError`, update the same record to `retryable_failed` with its stable error code and return a retryable result. For Feishu failure, return a sanitized service error and do not disclose raw upstream content. Set a 50-second application budget across token, Bitable, and Dify calls, leaving margin under Vercel's 60-second limit.

```python
token = await self.feishu.get_tenant_token()
record = await self.feishu.find_by_request_id(token, request_id)
if record is None:
    record = await self.feishu.create_processing_record(token, request_id, scenario)
if record.status == "completed":
    return PipelineResult(request_id=request_id, status=record.status, analysis=record.analysis)
try:
    analysis = await self.dify.run_workflow(scenario, request_id)
except DifyError as error:
    await self.feishu.update_record(token, record.record_id,
                                    {"处理状态": "retryable_failed", "错误码": error.code})
    return PipelineResult(request_id=request_id, status="retryable_failed", error_code=error.code)
await self.feishu.update_record(token, record.record_id, {
    "处理状态": "completed", "经营摘要": analysis.executive_summary,
    "关键观察": json.dumps(analysis.observations, ensure_ascii=False),
    "风险": json.dumps(analysis.risks, ensure_ascii=False),
    "7天验证动作": json.dumps([item.model_dump() for item in analysis.seven_day_actions], ensure_ascii=False),
})
return PipelineResult(request_id=request_id, status="completed", analysis=analysis)
```

- [ ] **Step 4: Re-run pipeline tests and add a repeated-request assertion.**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -q`

Expected: PASS; a retry never creates a second row when `request_id` lookup finds the first.

- [ ] **Step 5: Commit.**

```bash
git add app/services/pipeline.py app/schemas.py tests/test_pipeline.py
git commit -m "feat: coordinate analysis pipeline and retries"
```

### Task 5: Expose the FastAPI service and protect the public API

**Files:**
- Create: `app/main.py`
- Create: `index.py`
- Create: `tests/test_api.py`
- Modify: `app/config.py`

**Interfaces:**
- `create_app(settings: Settings, pipeline: PipelineService, scenarios: ScenarioCatalog) -> FastAPI`
- `GET /api/health -> {"status": "ok", "live_demo_enabled": bool}`
- `GET /api/scenarios -> list[{"id": str, "title": str}]`
- `GET /api/preview -> AnalysisOutput` serves the clearly labeled static sample result.
- `POST /api/analyze` and `POST /api/retry` accept `{ "scenario_id": str, "request_id": UUID }` and return a `PipelineResult`.

- [ ] **Step 1: Write failing FastAPI tests.** Inject fake services. Cover valid scenario listing, invalid scenario returning 400 before any external call, malformed UUID returning 422, live integration disabled returning 503, success result serialization, and retry preserving the request ID.

```python
def test_disabled_demo_rejects_submission(client, fake_pipeline):
    response = client.post("/api/analyze", json={"scenario_id": "coffee_shop", "request_id": REQUEST_ID})
    assert response.status_code == 503
    assert fake_pipeline.calls == []
```

- [ ] **Step 2: Run the focused test and verify it fails.**

Run: `.venv/Scripts/python.exe -m pytest tests/test_api.py -q`

Expected: FAIL because `create_app` is absent.

- [ ] **Step 3: Implement app factory and routes.** Require `DEMO_MODE=true` and all service credentials before accepting real submissions. Configure `index.py` to export `app` for Vercel's Python runtime. Register all `/api/*` routes before the static catch-all; serve `static/index.html` at `/` and mount assets at `/static`. `GET /api/preview` loads the fixed sample result. The client-provided request ID is validated as UUID and reused only for retry; all business fields are loaded by ID from `ScenarioCatalog`.

```python
@app.post("/api/analyze", response_model=PipelineResult)
async def analyze(body: ScenarioRequest) -> PipelineResult:
    if not settings.live_demo_ready:
        raise HTTPException(status_code=503, detail={"code": "demo_disabled"})
    return await pipeline.submit(body.scenario_id, str(body.request_id))
```

- [ ] **Step 4: Test API errors and JSON responses.**

Run: `.venv/Scripts/python.exe -m pytest tests/test_api.py -q`

Expected: PASS; invalid requests never call Feishu or Dify and public errors contain no credentials or upstream details.

- [ ] **Step 5: Commit.**

```bash
git add app/main.py index.py app/config.py tests/test_api.py
git commit -m "feat: expose protected FastAPI demo endpoints"
```

### Task 6: Build the responsive Chinese sample experience

**Files:**
- Create: `static/index.html`
- Create: `static/styles.css`
- Create: `static/app.js`
- Create: `tests/test_static_contract.py`
- Modify: `app/main.py`

**Interfaces:**
- On page load, JS calls `GET /api/scenarios` and displays the 10 fictional sample cards; CSS and JS load from `/static/styles.css` and `/static/app.js`.
- A sample submission sends only its `scenario_id` and a `crypto.randomUUID()` request ID to `/api/analyze`.
- Retry sends the same pair to `/api/retry`; success renders `AnalysisOutput` without reloading the page.

- [ ] **Step 1: Write failing static/API contract tests.** Assert the HTML links local CSS/JS, has a Chinese form heading, provides a live-region status element, and does not contain secret-like environment variable values or a real contact field.

- [ ] **Step 2: Run the test and verify it fails.**

Run: `.venv/Scripts/python.exe -m pytest tests/test_static_contract.py -q`

Expected: FAIL because static assets are absent.

- [ ] **Step 3: Add semantic mobile-first HTML and CSS.** Show the product purpose, sample selection, preview-only result, run button, processing state, result sections, error/retry state, and a footer stating samples are fictional and live analysis consumes API quota. At 360 px viewport, controls fit without horizontal scrolling; use visible focus and `aria-live` for status.

- [ ] **Step 4: Implement browser behavior.** Load sample titles from the API; disable repeat submits while pending; retain the request ID and sample ID in `sessionStorage` only until success; allow retry with the same ID; render text with `textContent` (never `innerHTML` for model output). If live demo is disabled or an upstream service is unavailable, call `/api/preview` and clearly label it `静态预览，未执行实时分析`.

```javascript
function addModelText(parent, value) {
  const node = document.createElement("p");
  node.textContent = String(value);
  parent.append(node);
}
```

- [ ] **Step 5: Serve the static preview file and test the DOM contract.**

Run: `.venv/Scripts/python.exe -m pytest tests/test_static_contract.py -q`

Expected: PASS; `GET /`, `/api/preview`, and the scenario list return 200, and model text is rendered as text.

- [ ] **Step 6: Commit.**

```bash
git add static app/main.py data/example_analysis.json tests/test_static_contract.py
git commit -m "feat: add mobile-friendly fictional analysis demo"
```

### Task 7: Verify the complete mocked flow and failure recovery

**Files:**
- Create: `tests/test_end_to_end.py`
- Create: `scripts/verify_mock_flow.py`
- Modify: `tests/conftest.py`

**Interfaces:**
- `scripts/verify_mock_flow.py` exits 0 only after all ten fixtures pass through fake Feishu and fake Dify and each result has exactly seven actions.
- The script prints counts and scenario IDs only; it never prints secrets or raw service responses.

- [ ] **Step 1: Write failing end-to-end tests.** Run all ten catalog scenarios through the same `PipelineService` used by the API; inject invalid sample ID, Dify timeout, invalid output, Feishu 401, and Feishu update 429. Verify each failure has the expected status/code and that the original row is reused on retry.

- [ ] **Step 2: Run tests and verify the new cases fail.**

Run: `.venv/Scripts/python.exe -m pytest tests/test_end_to_end.py -q`

Expected: FAIL until the shared fakes and complete assertions are implemented.

- [ ] **Step 3: Implement reusable deterministic fakes and the verification script.** Fake Dify returns stable analysis derived from the scenario title, with day 1 through day 7 actions; fake Feishu records each call and stores rows in memory.

```python
async def verify_all_scenarios(pipeline, catalog):
    scenarios = catalog.all()
    for scenario in scenarios:
        result = await pipeline.submit(scenario.id, str(uuid4()))
        assert result.status == "completed"
        assert [item.day for item in result.analysis.seven_day_actions] == list(range(1, 8))
    return len(scenarios)
```

- [ ] **Step 4: Run the entire mock suite.**

Run: `.venv/Scripts/python.exe -m pytest -q`

Expected: PASS with zero network calls and zero DeepSeek usage.

- [ ] **Step 5: Run the ten-scenario acceptance script.**

Run: `.venv/Scripts/python.exe scripts/verify_mock_flow.py`

Expected: `10 scenarios passed`; no credentials are required.

- [ ] **Step 6: Commit.**

```bash
git add tests scripts
git commit -m "test: verify ten fictional workflows and recovery paths"
```

### Task 8: Prepare Vercel, Dify, Feishu, README, and evidence

**Files:**
- Create: `vercel.json`
- Create: `README.md`
- Create: `docs/feishu-table-fields.md`
- Create: `docs/dify-workflow.md`
- Create: `docs/failure-cases.md`
- Create: `docs/case-study.md`
- Create: `docs/screenshots/` with four verified screenshots after live demo configuration
- Create: `tests/test_docs.py`
- Modify: `.env.example`
- Modify: `.gitignore`

**Interfaces:**
- Local setup uses `.env.example` copied to `.env`; production variables are entered only in Vercel and Dify dashboards.
- README includes the public demo link only after deployment is anonymously verified.
- Failure report includes the actual input type, visitor-facing result, internal stable code, recovery, and limitation for at least three distinct failures.

- [ ] **Step 1: Write failing documentation checks.** Extend `tests/test_docs.py` to assert README documents local install, Dify Workflow setup, Feishu app scopes/table headers, all environment variable names, test commands, 10 fictional fixtures, costs, and public WAF requirement; assert it contains no real credential patterns.

```python
def test_readme_documents_safe_demo_setup():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "DEMO_MODE=false" in readme
    assert "5 requests" in readme
    assert "虚构" in readme
    assert "FEISHU_APP_SECRET=" not in readme
```

- [ ] **Step 2: Run documentation checks and verify they fail.**

Run: `.venv/Scripts/python.exe -m pytest tests/test_docs.py -q`

Expected: FAIL until deployment documentation exists.

- [ ] **Step 3: Add Vercel entry/config and complete README.** Use `index.py` as the ASGI entrypoint and set function `maxDuration` to 60. `vercel.json` must contain `{"functions":{"index.py":{"maxDuration":60}}}`. Document local command `.venv/Scripts/python.exe -m uvicorn app.main:app --reload`, Dify inputs `scenario_json`/`request_id`, expected `analysis_json`, DeepSeek provider setup, Feishu tenant token permissions, table field mapping, and server-only secret configuration. Do not place credentials into commands or screenshots.

- [ ] **Step 4: Document public controls and failures.** Include the single WAF rule matching only `/api/analyze` or `/api/retry` (5 requests/IP/10 minutes), enable live submission only after the rule is published and the dedicated demo table is configured, explain Dify quota and DeepSeek costs, and document invalid sample, Dify timeout/malformed JSON, and Feishu auth/write failures with retry steps. Keep live mode disabled until the operator has configured both external services.

- [ ] **Step 5: Run all tests, static checks, and secret scan.**

Run: `.venv/Scripts/python.exe -m pytest -q`

Run: `.venv/Scripts/python.exe -m compileall -q app index.py scripts`

Run: `git diff --check`

Run in PowerShell: `$secretScanHits = rg -n "sk-[A-Za-z0-9]{20,}|cli_[A-Za-z0-9]{10,}|dify-[A-Za-z0-9_-]{20,}" --glob "!docs/screenshots/**" .; if ($LASTEXITCODE -eq 0) { throw "Potential credential found" }; if ($LASTEXITCODE -gt 1) { throw "Secret scan failed" }`

Expected: tests and compile pass; diff has no whitespace errors; secret scan exits 1 for no matches (exit 0 fails the step).

- [ ] **Step 6: Stage and commit the verified application and deployment instructions.** Run `git add vercel.json README.md docs .env.example .gitignore tests/test_docs.py`, then `git diff --cached --check`, then `git commit -m "docs: prepare deployment and portfolio case study"`.

- [ ] **Step 7: Publish the project repository.** Create `Heart727/business-validation-lab` as a public GitHub repository and push the verified `main` branch with `gh repo create Heart727/business-validation-lab --public --source . --remote origin --push`. Confirm the GitHub page contains no `.env`, tokens, or customer data.

- [ ] **Step 8: Deploy the static-preview mode to Vercel.** Connect the public GitHub repository, set `DEMO_MODE=false`, deploy with `vercel.json` mapping `index.py` to `maxDuration: 60`, and verify the page and `/api/preview` open anonymously in a private window. The page must clearly label the result as static until Dify and Feishu are configured.

- [ ] **Step 9: Configure the live integrations without sharing secrets in chat.** In the user's Feishu developer console, create a test app with only Bitable record read/write permissions and create a dedicated demo table using `docs/feishu-table-fields.md`. In Dify, set the DeepSeek provider and publish the Workflow described in `docs/dify-workflow.md`. Enter credentials only in Vercel's server environment; publish one WAF rate rule matching `/api/analyze` and `/api/retry`, five requests per source IP per ten minutes. Keep `DEMO_MODE=false` until all three checks (demo table isolation, published workflow, WAF rule) pass.

- [ ] **Step 10: Run live acceptance with the ten fictional scenarios.** This makes ten DeepSeek calls and creates/updates ten records in the dedicated Feishu demo table. Verify success status and seven actions for each record; record at least three intentional failure cases. If the services are not configured, keep the live demo disabled and label the public preview as static.

- [ ] **Step 11: Capture and review four screenshots.** Capture the sample form, processing/error status, generated analysis with 7-day plan, and matching Feishu demo record. Confirm every visible value is fictional and no credentials appear.

- [ ] **Step 12: Review the two-minute case page.** Ensure `docs/case-study.md` states business need, flow diagram, evidence, code/demo URLs, failure behavior, limits, and the author's contribution without claiming unverified live behavior.

- [ ] **Step 13: Commit the screenshots and final case page, then push.**

```bash
git add docs/screenshots docs/case-study.md README.md
git commit -m "docs: add verified portfolio evidence"
git push origin main
```
