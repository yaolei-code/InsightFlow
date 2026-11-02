from typing import Literal
from datetime import date
from pydantic import Field
from .schemas import Strict

SourceType=Literal['official_website','company_news','wechat_official_account','github','arxiv','technical_blog','industry_media','press_release','customer_case','customer_announcement','government','video','job_posting','other']
Stage=Literal['research','prototype','demonstration','pilot','commercial_deployment','scaled_production','unknown']
Level=Literal['company_claim','technical_artifact','independent_verification','customer_confirmation']

class CompanyInput(Strict):
    name: str=Field(min_length=1,max_length=200)
    category: str='待研究'
    description: str=''
    official_url: str=''
    technology_tags: list[str]=Field(default_factory=list,max_length=20)

class CompanyPatch(Strict):
    category: str | None=None
    description: str | None=None
    official_url: str | None=None
    technology_tags: list[str] | None=None
    is_active: bool | None=None

class ProjectInput(Strict):
    company_id:int
    name:str=Field(min_length=1,max_length=200)
    description:str=''
    technology_tags:list[str]=Field(default_factory=list)

class CompanySourceInput(Strict):
    company_id:int
    project_id:int | None=None
    url:str
    source_type:SourceType
    evidence_authority:Level='company_claim'

class CompanySourcePatch(Strict):
    url:str | None=None
    source_type:SourceType | None=None
    is_active:bool | None=None

class Metric(Strict):
    name:str
    value:str
    unit:str
    evidence_text:str=Field(min_length=1,max_length=1000)

class EventOutput(Strict):
    event_type:Literal['technology_breakthrough','model_release','product_release','robot_demo','benchmark_result','open_source_release','pilot_deployment','commercial_deployment','customer_cooperation','funding','mass_production','other']
    title:str=Field(min_length=1,max_length=200)
    description:str=Field(max_length=2000)
    project_name:str | None
    capability_tags:list[str]=Field(max_length=15)
    progress_stage:Stage
    published_at:date | None
    occurred_at:date | None
    published_evidence:str
    occurred_evidence:str
    evidence_text:str=Field(min_length=1,max_length=4000)
    evidence_level:Level
    metrics:list[Metric]=Field(max_length=10)

class ProgressOutput(Strict):
    events:list[EventOutput]=Field(max_length=16)
