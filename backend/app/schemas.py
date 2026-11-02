from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Dimension = Literal['Data Management','Model Training','Simulation','Evaluation','Deployment','Experiment Tracking','Compute Management','AI Agent Integration']
DIMENSIONS = list(Dimension.__args__)

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

class ProductInput(Strict):
    name: str = Field(min_length=1, max_length=200)
    company: str = ''
    category: str = ''
    description: str = ''
    official_url: str = ''

class ProductPatch(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    company: str | None = None
    category: str | None = None
    description: str | None = None
    official_url: str | None = None
    is_active: bool | None = None

class SourceInput(Strict):
    product_id: int
    url: str
    source_type: Literal['official_website','documentation','github_repository','release_notes','other'] = 'official_website'

class SourcePatch(Strict):
    url: str | None = None
    is_active: bool | None = None
    source_type: Literal['official_website','documentation','github_repository','release_notes','other'] | None = None

class ClaimOutput(Strict):
    dimension: Dimension
    claim_text: str = Field(max_length=2000)
    claim_status: Literal['supported','not_supported','unknown','not_applicable']
    availability: Literal['released','demo','planned','in_development','unknown']
    evidence_text: str = Field(min_length=1, max_length=4000)

class Extraction(Strict):
    claims: list[ClaimOutput] = Field(max_length=32)

class ChangeOutput(Strict):
    change_type: Literal['feature_added','feature_removed','feature_updated','pricing_changed','documentation_updated','release_published','other']
    title: str
    description: str
    old_evidence: str
    new_evidence: str
    importance: Literal['low','medium','high']

class ImpactOutput(Strict):
    affected_dimensions: list[Dimension]
    relationship: Literal['direct_competition','functional_overlap','ecosystem_benchmark','not_comparable','insufficient_evidence']
    impact_level: Literal['low','medium','high','unknown']
    reasoning: str
    evidence_claim_ids: list[int]
    opportunities: list[str]
    risks: list[str]
    recommended_actions: list[str]
    uncertainties: list[str]

class ResearchInput(Strict):
    source_ids: list[int] = Field(default_factory=list, max_length=20)

class ComparisonInput(Strict):
    product_ids: list[int] = Field(min_length=2, max_length=10)
    relationship: Literal['direct_competition','functional_overlap','ecosystem_benchmark','not_comparable','insufficient_evidence'] = 'insufficient_evidence'
    rationale: str = '关系由研究员审阅；未公开不代表不支持。'

class ReportInput(Strict):
    title: str = Field(default='竞品研究报告', min_length=1, max_length=200)
