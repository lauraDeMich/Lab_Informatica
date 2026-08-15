"""
Modelli Pydantic per l'intero backend.

Contiene sia gli schemi "di dominio" (ParsedPage per l'Obiettivo 1,
GoldStandardEntry per l'Obiettivo 2) sia gli schemi di richiesta/risposta
per ogni endpoint REST dell'Obiettivo 6. I nomi dei campi rispettano
esattamente quanto richiesto dalla specifica del progetto, perché saranno
testati automaticamente.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# --------------------------------------------------------------------- #
# Obiettivo 1 / 2: schemi di dominio
# --------------------------------------------------------------------- #
class ParsedPage(BaseModel):
    """Output strutturato del parsing di una singola pagina web (Obiettivo 1)."""

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
    """Singola entry del Gold Standard (Obiettivo 2)."""

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


# --------------------------------------------------------------------- #
# Obiettivo 6: request/response per gli endpoint REST
# --------------------------------------------------------------------- #
class ParseRequest(BaseModel):
    url: str
    # html_text: usato dalla specifica Esonero 1 (POST /parse parsa
    # direttamente l'HTML fornito, senza toccare il DB).
    html_text: str | None = None
    # local: usato dalla specifica Progetto Finale (POST /parse con
    # local=true recupera l'HTML gia' salvato nel DB per quell'url).
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
    status: str  # "ok" oppure "error"


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
