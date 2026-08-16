
from __future__ import annotations

from pydantic import BaseModel, Field


class ParsedPage(BaseModel):

    url: str = Field(..., description="URL della pagina originale")
    domain: str = Field(..., description="Dominio della pagina, es. it.wikipedia.org")
    title: str = Field(..., description="Titolo della pagina web")
    html_text: str = Field(
        ...,
        description=(
            "Testo/HTML grezzo della pagina (senza filtri). "
            "Deve permettere di rieseguire il parsing per ottenere di nuovo parsed_text."
        ),
    )
    parsed_text: str = Field(
        ...,
        description="Testo estratto pulito, senza tag HTML, in formato Markdown.",
    )

    def to_json_dict(self) -> dict:
        return self.model_dump()


class GoldStandardEntry(BaseModel):

    url: str = Field(..., description="URL della pagina originale")
    domain: str = Field(..., description="Dominio della pagina, es. it.wikipedia.org")
    title: str = Field(..., description="Titolo della pagina web")
    html_text: str = Field(
        ...,
        description="HTML grezzo della pagina, permette di rieseguire il parsing.",
    )
    gold_text: str = Field(
        ...,
        description="Testo estratto pulito A MANO, senza tag HTML o markdown.",
    )

    def to_json_dict(self) -> dict:
        return self.model_dump()


class ParseRequest(BaseModel):
    url: str
    html_text: str | None = None
    local: bool | None = False


class DomainsResponse(BaseModel):
    domains: list[str]


class GoldStandardUrlsResponse(BaseModel):
    gold_standard_urls: list[str]


class FullGoldStandardResponse(BaseModel):
    gold_standard: list[GoldStandardEntry]


class EvaluateRequest(BaseModel):
    parsed_text: str
    gold_text: str


class TokenLevelEval(BaseModel):
    precision: float
    recall: float
    f1: float


class Rouge1Eval(BaseModel):
    precision: float
    recall: float
    f1: float


class XEval(BaseModel):
    rouge1: Rouge1Eval


class EvaluateResponse(BaseModel):
    token_level_eval: TokenLevelEval
    x_eval: XEval


class EvaluateJudgeRequest(BaseModel):
    parsed_text: str
    gold_text: str


class EvaluateJudgeResponse(BaseModel):
    model_name: str
    judge_score: int
    judge_feedback: str


class FullGsEvalResponse(BaseModel):
    token_level_eval: TokenLevelEval
    x_eval: XEval
    judge_score: float


class AddWebResourceRequest(BaseModel):
    url: str
    html_text: str


class AddGoldStandardRequest(BaseModel):
    url: str
    gold_text: str


class UrlOnlyRequest(BaseModel):
    url: str


class StatusOkResponse(BaseModel):
    status: str


class DomainAvgEval(BaseModel):
    token_level_eval: dict
    x_eval: dict


class DomainAvgJudge(BaseModel):
    judge_score: float


class DbStatsResponse(BaseModel):
    web_resources: dict[str, int]
    gold_standard: dict[str, int]
    avg_eval: dict[str, DomainAvgEval]
    avg_eval_judge: dict[str, DomainAvgJudge]


class SystemStatusResponse(BaseModel):
    backend: str
    database: str
    ollama: str
