from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    demo_mode: bool = False
    feishu_app_id: str | None = Field(default=None, repr=False)
    feishu_app_secret: str | None = Field(default=None, repr=False)
    feishu_app_token: str | None = Field(default=None, repr=False)
    feishu_table_id: str | None = Field(default=None, repr=False)
    feishu_base_url: str = "https://open.feishu.cn"
    dify_base_url: str = "https://api.dify.ai/v1"
    dify_workflow_api_key: str | None = Field(default=None, repr=False)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()

    @property
    def live_demo_ready(self) -> bool:
        required = (
            self.feishu_app_id,
            self.feishu_app_secret,
            self.feishu_app_token,
            self.feishu_table_id,
            self.dify_workflow_api_key,
        )
        return self.demo_mode and all(required)
