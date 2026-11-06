"""Pydantic schemas for research.json and content.json - the contracts between workflow steps.

The agent (Claude, in session) writes these files; save_research.py and check_content.py validate
them against these models so every later tool can rely on the shape.
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- research.json ----------------------------------------------------------------
class Fact(Strict):
    fact: str
    source_url: str
    verified_source: Optional[bool] = None


class Statistic(Strict):
    label: str
    value: float
    unit: str
    year: Optional[str] = None
    context: str
    source_url: str
    verified_source: Optional[bool] = None


class TimelineItem(Strict):
    date: str
    event: str
    source_url: str
    verified_source: Optional[bool] = None


class QuoteItem(Strict):
    quote: str
    speaker: str
    role: Optional[str] = None
    source_url: str
    verified_source: Optional[bool] = None


class Trend(Strict):
    trend: str
    detail: str
    source_url: str
    verified_source: Optional[bool] = None


class Findings(Strict):
    summary: str
    key_facts: List[Fact]
    statistics: List[Statistic]
    timeline: List[TimelineItem]
    quotes: List[QuoteItem]
    trends: List[Trend]
    business_implications: List[str]


class Research(Strict):
    topic: str
    slug: Optional[str] = None
    audience: str
    researched_on: str
    findings: Findings
    citations: Optional[List[str]] = None
    url_checks: Optional[dict] = None


# ---------- content.json -----------------------------------------------------------------
class Stat(Strict):
    value: str
    unit: Optional[str] = None
    label: str
    note: Optional[str] = None


class Event(Strict):
    date: str
    title: str
    detail: Optional[str] = None


class Column(Strict):
    heading: str
    items: List[str]


class Dataset(Strict):
    label: str
    data: List[float]
    highlight_index: Optional[int] = None


class Chart(Strict):
    kind: Literal["bar", "hbar", "line", "doughnut"]
    unit: Optional[str] = None
    labels: List[str]
    datasets: List[Dataset]
    height: Optional[int] = None


class Infographic(Strict):
    id: str
    type: Literal["stats", "chart", "timeline", "comparison", "quote", "ai"]
    theme: Literal["dark", "light"]
    eyebrow: Optional[str] = None
    title: str
    subtitle: Optional[str] = None
    alt: str
    source: str
    stats: Optional[List[Stat]] = None
    chart: Optional[Chart] = None
    events: Optional[List[Event]] = None
    left: Optional[Column] = None
    right: Optional[Column] = None
    quote: Optional[str] = None
    speaker: Optional[str] = None
    role: Optional[str] = None
    prompt: Optional[str] = None
    aspect: Optional[Literal["16:9", "4:3", "3:2", "1:1"]] = None
    caption: Optional[str] = None


class Section(Strict):
    heading: str
    body: List[str]
    infographic: Optional[str] = None


class FocusArea(Strict):
    name: Literal["Real Estate", "EduTech", "Digital Services"]
    point: str


class BusinessTakeaway(Strict):
    heading: Optional[str] = None
    body: List[str]
    focus_areas: List[FocusArea]


class Source(Strict):
    n: int
    title: str
    url: str
    publisher: Optional[str] = None


class Newsletter(Strict):
    topic: str
    subject: str
    preview_text: str
    issue_label: Optional[str] = None
    eyebrow: Optional[str] = None
    headline: str
    dek: str
    intro: List[str]
    key_takeaways: List[str]
    sections: List[Section]
    infographics: List[Infographic]
    business_takeaway: BusinessTakeaway
    sources: List[Source]
