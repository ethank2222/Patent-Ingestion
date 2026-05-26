from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint

from .extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Patent(db.Model):
    __tablename__ = "patents"

    id = db.Column(db.Integer, primary_key=True)
    publication_number = db.Column(db.String(64), nullable=False, unique=True, index=True)
    application_number = db.Column(db.String(64), nullable=True, index=True)
    kind_code = db.Column(db.String(16), nullable=True)
    doc_type = db.Column(db.String(32), nullable=False, default="application_publication", index=True)

    publication_date = db.Column(db.Date, nullable=True, index=True)
    filing_date = db.Column(db.Date, nullable=True)
    priority_date = db.Column(db.Date, nullable=True)

    title = db.Column(db.Text, nullable=True)
    abstract = db.Column(db.Text, nullable=True)
    assignee = db.Column(db.String(256), nullable=True, index=True)

    inventors_json = db.Column(db.JSON, nullable=False, default=list)
    cpc_codes_json = db.Column(db.JSON, nullable=False, default=list)
    cpc_primary = db.Column(db.String(32), nullable=True, index=True)

    source_system = db.Column(db.String(64), nullable=False, default="uspto_odp")
    source_url = db.Column(db.Text, nullable=True)
    source_hash = db.Column(db.String(128), nullable=False, index=True)

    ingested_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    sections = db.relationship("PatentSection", back_populates="patent", cascade="all, delete-orphan")
    summaries = db.relationship("Summary", back_populates="patent", cascade="all, delete-orphan")

    def to_list_dict(self) -> dict:
        return {
            "publication_number": self.publication_number,
            "application_number": self.application_number,
            "kind_code": self.kind_code,
            "doc_type": self.doc_type,
            "publication_date": self.publication_date.isoformat() if self.publication_date else None,
            "filing_date": self.filing_date.isoformat() if self.filing_date else None,
            "priority_date": self.priority_date.isoformat() if self.priority_date else None,
            "title": self.title,
            "abstract": self.abstract,
            "assignee": self.assignee,
            "inventors": self.inventors_json or [],
            "cpc_codes": self.cpc_codes_json or [],
            "cpc_primary": self.cpc_primary,
            "source_system": self.source_system,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_detail_dict(self) -> dict:
        sections = {s.section_type: s.section_text for s in self.sections}
        payload = self.to_list_dict()
        payload.update(
            {
                "sections": sections,
                "source_url": self.source_url,
                "source_hash": self.source_hash,
                "ingested_at": self.ingested_at.isoformat() if self.ingested_at else None,
            }
        )
        return payload


class PatentSection(db.Model):
    __tablename__ = "patent_text_sections"

    id = db.Column(db.Integer, primary_key=True)
    patent_id = db.Column(db.Integer, db.ForeignKey("patents.id", ondelete="CASCADE"), nullable=False, index=True)
    section_type = db.Column(db.String(64), nullable=False)
    section_text = db.Column(db.Text, nullable=False)
    token_count_estimate = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    patent = db.relationship("Patent", back_populates="sections")

    __table_args__ = (UniqueConstraint("patent_id", "section_type", name="uq_patent_section_type"),)


class Summary(db.Model):
    __tablename__ = "summaries"

    id = db.Column(db.Integer, primary_key=True)
    patent_id = db.Column(db.Integer, db.ForeignKey("patents.id", ondelete="CASCADE"), nullable=False, index=True)
    status = db.Column(db.String(32), nullable=False, default="queued", index=True)

    model_name = db.Column(db.String(128), nullable=False)
    prompt_version = db.Column(db.String(32), nullable=False)
    summary_mode = db.Column(db.String(16), nullable=False, default="deep")
    source_hash_at_generation = db.Column(db.String(128), nullable=False, index=True)
    cache_key = db.Column(db.String(256), nullable=False, unique=True, index=True)

    summary_markdown = db.Column(db.Text, nullable=True)
    summary_json = db.Column(db.JSON, nullable=True)
    quality_score = db.Column(db.Float, nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    generated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    patent = db.relationship("Patent", back_populates="summaries")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "patent_id": self.patent_id,
            "status": self.status,
            "model_name": self.model_name,
            "prompt_version": self.prompt_version,
            "summary_mode": self.summary_mode,
            "summary_markdown": self.summary_markdown,
            "summary_json": self.summary_json,
            "quality_score": self.quality_score,
            "error_message": self.error_message,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SummaryJob(db.Model):
    __tablename__ = "summary_jobs"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(64), nullable=False, unique=True, default=lambda: uuid.uuid4().hex, index=True)
    patent_id = db.Column(db.Integer, db.ForeignKey("patents.id", ondelete="CASCADE"), nullable=False, index=True)
    summary_id = db.Column(db.Integer, db.ForeignKey("summaries.id", ondelete="SET NULL"), nullable=True, index=True)

    status = db.Column(db.String(32), nullable=False, default="queued", index=True)
    requested_by = db.Column(db.String(128), nullable=True)
    cache_hit = db.Column(db.Boolean, nullable=False, default=False)
    latency_ms = db.Column(db.Integer, nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)

    patent = db.relationship("Patent", foreign_keys=[patent_id])
    summary = db.relationship("Summary", foreign_keys=[summary_id])

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "patent_id": self.patent_id,
            "summary_id": self.summary_id,
            "status": self.status,
            "requested_by": self.requested_by,
            "cache_hit": self.cache_hit,
            "latency_ms": self.latency_ms,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }
