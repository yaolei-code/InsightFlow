from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / '.env', extra="ignore", hide_input_in_errors=True)
    database_url: str = "sqlite:///./insightflow.db"
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4.1-mini"
    llm_protocol: Literal['responses','chat','json'] = "responses"
    enable_tracing: bool = False
    github_token: str = ""
    wechat_search_api_url: str = ''
    wechat_search_api_key: str = ''
    tavily_api_key: str = ''
    search_provider: Literal['tavily','github'] = 'tavily'


settings = Settings()
