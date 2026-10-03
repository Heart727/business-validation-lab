"""Coordinates idempotent analysis requests across Feishu and Dify."""

import asyncio

from app.schemas import AnalysisOutput, PipelineResult
from app.services.dify import DifyClient, DifyError
from app.services.feishu import FeishuClient, FeishuError, FeishuRecord
from app.services.scenarios import ScenarioCatalog


PIPELINE_TIMEOUT_SECONDS = 50.0
PIPELINE_CLEANUP_SECONDS = 5.0


class PipelineError(Exception):
    """An application-safe service failure code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class PipelineService:
    def __init__(self, feishu: FeishuClient, dify: DifyClient, scenarios: ScenarioCatalog) -> None:
        self.feishu = feishu
        self.dify = dify
        self.scenarios = scenarios

    async def submit(self, scenario_id: str, request_id: str) -> PipelineResult:
        scenario = self.scenarios.get(scenario_id)
        loop = asyncio.get_running_loop()
        total_seconds = max(PIPELINE_TIMEOUT_SECONDS, 0.001)
        cleanup_seconds = min(PIPELINE_CLEANUP_SECONDS, total_seconds / 2)
        deadline = loop.time() + total_seconds
        work_deadline = deadline - cleanup_seconds
        token: str | None = None
        record: FeishuRecord | None = None

        try:
            async with asyncio.timeout_at(work_deadline):
                token = await self.feishu.get_tenant_token()
                record = await self.feishu.find_by_request_id(token, request_id)
                if record is None:
                    record = await self.feishu.create_processing_record(token, request_id, scenario)

                if record.status == "completed":
                    if record.analysis is None:
                        raise PipelineError("feishu_invalid_response")
                    return PipelineResult(
                        request_id=request_id,
                        status="completed",
                        analysis=record.analysis,
                    )

                try:
                    analysis = await self.dify.run_workflow(scenario, request_id)
                except DifyError as error:
                    await self._update_retryable(token, record, error.code)
                    return PipelineResult(
                        request_id=request_id,
                        status="retryable_failed",
                        error_code=error.code,
                    )

                await self.feishu.update_record(
                    token,
                    record.record_id,
                    self._completed_fields(analysis),
                )
                return PipelineResult(
                    request_id=request_id,
                    status="completed",
                    analysis=analysis,
                )
        except TimeoutError:
            if token is None or record is None:
                raise PipelineError("pipeline_timeout") from None
            try:
                async with asyncio.timeout_at(deadline):
                    await self._update_retryable(token, record, "pipeline_timeout")
            except TimeoutError:
                raise PipelineError("pipeline_timeout") from None
            except FeishuError as error:
                raise PipelineError(error.code) from None
            return PipelineResult(
                request_id=request_id,
                status="retryable_failed",
                error_code="pipeline_timeout",
            )
        except FeishuError as error:
            raise PipelineError(error.code) from None

    async def _update_retryable(self, token: str, record: FeishuRecord, error_code: str) -> None:
        await self.feishu.update_record(
            token,
            record.record_id,
            {"处理状态": "retryable_failed", "错误码": error_code},
        )

    @staticmethod
    def _completed_fields(analysis: AnalysisOutput) -> dict[str, object]:
        return {
            "处理状态": "completed",
            "经营摘要": analysis.executive_summary,
            "关键观察": analysis.observations,
            "风险": analysis.risks,
            "7天验证动作": [action.model_dump(mode="json") for action in analysis.seven_day_actions],
            "错误码": "",
        }
