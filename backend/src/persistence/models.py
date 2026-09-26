"""ORM models. Import every model module here so Alembic autogenerate sees the full metadata."""

from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from persistence.database import Base


# ---------------------------------------------------------------------------
# Seed bookkeeping (SPRINT-00)
# ---------------------------------------------------------------------------


class SeedRun(Base):
    """Records which synthetic seed datasets were applied, keeping seeding idempotent."""

    __tablename__ = "seed_run"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    version: Mapped[int] = mapped_column(nullable=False)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# SPRINT-01 / SPRINT-04 domain models
# ---------------------------------------------------------------------------


class Client(Base):
    """An organisation that owns one or more Assessments."""

    __tablename__ = "client"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    assessments: Mapped[list["Assessment"]] = relationship(
        "Assessment", back_populates="client", cascade="all, delete-orphan"
    )


class AssessmentStatus(str, Enum):
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Assessment(Base):
    """A scoped Clean Core analysis for a specific SAP source system owned by a Client."""

    __tablename__ = "assessment"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("client.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sap_source_system: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=AssessmentStatus.CREATED.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    client: Mapped["Client"] = relationship("Client", back_populates="assessments")
    scans: Mapped[list["SourceScan"]] = relationship(
        "SourceScan", back_populates="assessment", cascade="all, delete-orphan"
    )
    sap_objects: Mapped[list["SAPObject"]] = relationship(
        "SAPObject", back_populates="assessment", cascade="all, delete-orphan"
    )
    dependencies: Mapped[list["SAPObjectDependency"]] = relationship(
        "SAPObjectDependency", back_populates="assessment", cascade="all, delete-orphan"
    )
    atc_runs: Mapped[list["ATCRun"]] = relationship(
        "ATCRun", back_populates="assessment", cascade="all, delete-orphan"
    )
    atc_findings: Mapped[list["ATCFinding"]] = relationship(
        "ATCFinding", back_populates="assessment", cascade="all, delete-orphan",
        foreign_keys="ATCFinding.assessment_id",
    )
    technical_findings: Mapped[list["TechnicalFinding"]] = relationship(
        "TechnicalFinding", back_populates="assessment", cascade="all, delete-orphan"
    )
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(
        "PipelineRun", back_populates="assessment", cascade="all, delete-orphan"
    )
    evidence_datasets: Mapped[list["EvidenceDataset"]] = relationship(
        "EvidenceDataset", back_populates="assessment", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# SPRINT-02 domain models
# ---------------------------------------------------------------------------


class ScanStatus(str, Enum):
    PENDING = "pending"
    SCANNING = "scanning"
    COMPLETED = "completed"
    FAILED = "failed"


class ArtifactCategory(str, Enum):
    ABAP_SOURCE = "abap_source"
    XML_METADATA = "xml_metadata"
    CDS = "cds"
    DDIC = "ddic"
    CONFIGURATION = "configuration"
    DOCUMENTATION = "documentation"
    OTHER = "other"


class SourceScan(Base):
    """A directory scan job for an assessment; tracks progress and persists discovered files."""

    __tablename__ = "source_scan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessment.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=ScanStatus.PENDING.value
    )
    total_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scanned_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="scans")
    files: Mapped[list["SourceFile"]] = relationship(
        "SourceFile", back_populates="scan", cascade="all, delete-orphan"
    )


class SourceFile(Base):
    """A single file discovered during a source scan, with metadata and artifact category."""

    __tablename__ = "source_file"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(
        ForeignKey("source_scan.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessment.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rel_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mtime: Mapped[float] = mapped_column(Float, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)

    scan: Mapped["SourceScan"] = relationship("SourceScan", back_populates="files")
    sap_objects: Mapped[list["SAPObject"]] = relationship(
        "SAPObject", back_populates="source_file", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# SPRINT-03 domain models
# ---------------------------------------------------------------------------


class SAPObject(Base):
    """A SAP object (class, function module, report, DDIC table, etc.) extracted from a SourceFile."""

    __tablename__ = "sap_object"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessment.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_file_id: Mapped[int] = mapped_column(
        ForeignKey("source_file.id", ondelete="CASCADE"), nullable=False, index=True
    )
    object_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    object_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    # Deterministic identity — f"{object_type.upper()}::{object_name.upper()}", unique per
    # assessment — so reprocessing upserts instead of deleting/recreating the row (ADR-017).
    canonical_key: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    line_start: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attributes: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Most recent parse StageRun that reproduced this object — lets the parse stage's
    # finalize step tell "still present in this scan" apart from objects no longer produced.
    last_seen_stage_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("stage_run.id", ondelete="SET NULL"), nullable=True, index=True
    )
    parsed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("assessment_id", "canonical_key", name="ux_sap_object_assessment_canonical_key"),)

    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="sap_objects")
    source_file: Mapped["SourceFile"] = relationship("SourceFile", back_populates="sap_objects")
    dependencies: Mapped[list["SAPObjectDependency"]] = relationship(
        "SAPObjectDependency", back_populates="source_object", cascade="all, delete-orphan",
        foreign_keys="SAPObjectDependency.source_object_id",
    )
    atc_findings: Mapped[list["ATCFinding"]] = relationship(
        "ATCFinding", back_populates="correlated_object", foreign_keys="ATCFinding.correlated_object_id"
    )
    understanding: Mapped["ObjectUnderstanding | None"] = relationship(
        "ObjectUnderstanding", back_populates="sap_object", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# SPRINT-05 domain models
# ---------------------------------------------------------------------------


class SAPObjectDependency(Base):
    """A deterministic dependency detected between a parsed SAPObject and a target name."""

    __tablename__ = "sap_object_dependency"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessment.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_object_id: Mapped[int] = mapped_column(
        ForeignKey("sap_object.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    dep_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="CERTAIN")
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    source_object: Mapped["SAPObject"] = relationship(
        "SAPObject", back_populates="dependencies", foreign_keys=[source_object_id]
    )
    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="dependencies")


class ATCCheck(Base):
    """Catalog of ATC check types — dynamically discovered during import."""

    __tablename__ = "atc_check"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    check_title: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    findings: Mapped[list["ATCFinding"]] = relationship("ATCFinding", back_populates="atc_check")


class ATCRunStatus(str, Enum):
    ACCEPTED_FULL = "ACCEPTED_FULL"
    ACCEPTED_PARTIAL = "ACCEPTED_PARTIAL"
    REJECTED = "REJECTED"
    IN_PROGRESS = "IN_PROGRESS"


class ATCRun(Base):
    """One ATC XLSX import run for an Assessment."""

    __tablename__ = "atc_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessment.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    selected_worksheet: Mapped[str | None] = mapped_column(String(200), nullable=True)
    original_headers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    canonical_mapping: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    unknown_headers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    missing_known_headers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    importer_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    imported_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ATCRunStatus.IN_PROGRESS.value
    )
    warnings_summary: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="atc_runs")
    findings: Mapped[list["ATCFinding"]] = relationship(
        "ATCFinding", back_populates="atc_run", cascade="all, delete-orphan"
    )


class ATCCorrelationStatus(str, Enum):
    MATCHED_EXACT = "MATCHED_EXACT"
    MATCHED_HEURISTIC = "MATCHED_HEURISTIC"
    UNMATCHED = "UNMATCHED"
    AMBIGUOUS = "AMBIGUOUS"


class ATCFinding(Base):
    """A single ATC finding row imported from an XLSX file."""

    __tablename__ = "atc_finding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    atc_run_id: Mapped[int] = mapped_column(
        ForeignKey("atc_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessment.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    row_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    normalized_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    mapping_warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Canonical nullable fields
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    check_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    check_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    object_name_raw: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    object_type_raw: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exemption_state: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(200), nullable=True)
    package_name_raw: Mapped[str | None] = mapped_column(String(200), nullable=True)
    first_found_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    object_responsible: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_changed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sap_note_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sap_note_short_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    referenced_application_component: Mapped[str | None] = mapped_column(String(200), nullable=True)
    referenced_object_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    referenced_object_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    additional_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    simplification_item_category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    change_category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    change_category_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Correlation
    correlation_status: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    correlated_object_id: Mapped[int | None] = mapped_column(
        ForeignKey("sap_object.id", ondelete="SET NULL"), nullable=True, index=True
    )
    atc_check_id: Mapped[int | None] = mapped_column(
        ForeignKey("atc_check.id", ondelete="SET NULL"), nullable=True, index=True
    )

    atc_run: Mapped["ATCRun"] = relationship("ATCRun", back_populates="findings")
    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="atc_findings")
    correlated_object: Mapped["SAPObject | None"] = relationship(
        "SAPObject", back_populates="atc_findings", foreign_keys=[correlated_object_id]
    )
    atc_check: Mapped["ATCCheck | None"] = relationship("ATCCheck", back_populates="findings")


class TechnicalFindingSource(str, Enum):
    PARSING = "PARSING"
    ATC = "ATC"
    COMBINED = "COMBINED"


class TechnicalFindingSeverity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class TechnicalFinding(Base):
    """A deterministic technical finding derived from parsing, ATC import, or both."""

    __tablename__ = "technical_finding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessment.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sap_object_id: Mapped[int | None] = mapped_column(
        ForeignKey("sap_object.id", ondelete="SET NULL"), nullable=True, index=True
    )
    atc_finding_id: Mapped[int | None] = mapped_column(
        ForeignKey("atc_finding.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    finding_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="technical_findings")
    sap_object: Mapped["SAPObject | None"] = relationship("SAPObject", foreign_keys=[sap_object_id])
    atc_finding: Mapped["ATCFinding | None"] = relationship("ATCFinding", foreign_keys=[atc_finding_id])


# ---------------------------------------------------------------------------
# SPRINT-06 domain models — durable pipeline execution (ADR-005)
# ---------------------------------------------------------------------------


class PipelineRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class StageRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkItemStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineRunKind(str, Enum):
    SOURCE_PROCESSING = "source_processing"
    EVIDENCE_IMPORT = "evidence_import"


class PipelineRun(Base):
    """A durable, resumable run of a registered stage set (`kind`) for one Assessment —
    either source scan/parse/dependency processing, or a supplemental evidence import."""

    __tablename__ = "pipeline_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessment.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(
        String(30), nullable=False, default=PipelineRunKind.SOURCE_PROCESSING.value, index=True
    )
    source_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    source_scan_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_scan.id", ondelete="SET NULL"), nullable=True
    )
    evidence_dataset_id: Mapped[int | None] = mapped_column(
        ForeignKey("evidence_dataset.id", ondelete="CASCADE"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PipelineRunStatus.PENDING.value
    )
    pause_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="pipeline_runs")
    source_scan: Mapped["SourceScan | None"] = relationship("SourceScan")
    stage_runs: Mapped[list["StageRun"]] = relationship(
        "StageRun",
        back_populates="pipeline_run",
        cascade="all, delete-orphan",
        order_by="StageRun.sequence",
    )


class StageRun(Base):
    """One stage (scan / parse / detect_dependencies) of a PipelineRun, decomposed into WorkItems."""

    __tablename__ = "stage_run"
    __table_args__ = (UniqueConstraint("pipeline_run_id", "stage_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pipeline_run_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    depends_on: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StageRunStatus.PENDING.value
    )
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    pipeline_run: Mapped["PipelineRun"] = relationship("PipelineRun", back_populates="stage_runs")
    work_items: Mapped[list["WorkItem"]] = relationship(
        "WorkItem", back_populates="stage_run", cascade="all, delete-orphan"
    )


class WorkItem(Base):
    """A single unit of work within a StageRun (e.g. one file or one SAP object)."""

    __tablename__ = "work_item"
    __table_args__ = (UniqueConstraint("stage_run_id", "item_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stage_run_id: Mapped[int] = mapped_column(
        ForeignKey("stage_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_key: Mapped[str] = mapped_column(String(500), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=WorkItemStatus.PENDING.value, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    stage_run: Mapped["StageRun"] = relationship("StageRun", back_populates="work_items")


# ---------------------------------------------------------------------------
# SPRINT-08 domain models — supplemental evidence datasets (ADR-017)
# ---------------------------------------------------------------------------


class EvidenceDatasetType(str, Enum):
    """FUE_USER_VALIDATION was dropped (see ADR-017) — its `.bin` payloads are a proprietary,
    high-entropy compressed format with no available decoder; decoding would mean guessing
    the binary schema, which ADR-017 explicitly prohibits."""

    PANAYA_ETL = "PANAYA_ETL"
    SIGNAVIO_PROCESS_INSIGHTS = "SIGNAVIO_PROCESS_INSIGHTS"
    HANA_SIZING_REPORT = "HANA_SIZING_REPORT"
    SAP_READINESS_CHECK = "SAP_READINESS_CHECK"
    OTHER = "OTHER"


class EvidenceDatasetStatus(str, Enum):
    INSPECTED = "INSPECTED"
    IMPORTING = "IMPORTING"
    IMPORTED_FULL = "IMPORTED_FULL"
    IMPORTED_PARTIAL = "IMPORTED_PARTIAL"
    FAILED = "FAILED"


class EvidenceArtifactRole(str, Enum):
    PRIMARY = "PRIMARY"
    METADATA = "METADATA"
    DATA_CHUNK = "DATA_CHUNK"
    BINARY_PAYLOAD = "BINARY_PAYLOAD"
    OTHER = "OTHER"


class EvidenceCorrelationStatus(str, Enum):
    MATCHED_EXACT = "MATCHED_EXACT"
    MATCHED_HEURISTIC = "MATCHED_HEURISTIC"
    UNMATCHED = "UNMATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EvidenceDataset(Base):
    """One imported supplemental evidence package/version for an Assessment (ADR-017)."""

    __tablename__ = "evidence_dataset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessment.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    importer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    importer_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EvidenceDatasetStatus.INSPECTED.value, index=True
    )
    source_system_hint: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_client_hint: Mapped[str | None] = mapped_column(String(200), nullable=True)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    capabilities: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    warning_summary: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="evidence_datasets")
    artifacts: Mapped[list["EvidenceArtifact"]] = relationship(
        "EvidenceArtifact", back_populates="dataset", cascade="all, delete-orphan"
    )
    records: Mapped[list["EvidenceRecord"]] = relationship(
        "EvidenceRecord", back_populates="dataset", cascade="all, delete-orphan"
    )


class EvidenceArtifact(Base):
    """A physical member/artifact belonging to an EvidenceDataset (e.g. ZIP member, primary XML)."""

    __tablename__ = "evidence_artifact"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("evidence_dataset.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_name: Mapped[str] = mapped_column(String(500), nullable=False)
    artifact_role: Mapped[str] = mapped_column(String(20), nullable=False, default=EvidenceArtifactRole.OTHER.value)
    media_hint: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    dataset: Mapped["EvidenceDataset"] = relationship("EvidenceDataset", back_populates="artifacts")
    records: Mapped[list["EvidenceRecord"]] = relationship("EvidenceRecord", back_populates="artifact")


class EvidenceRecord(Base):
    """A normalized evidence unit extracted by an adapter, with provenance (ADR-017)."""

    __tablename__ = "evidence_record"
    __table_args__ = (UniqueConstraint("dataset_id", "record_fingerprint", name="ux_evidence_record_dataset_fingerprint"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("evidence_dataset.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_id: Mapped[int | None] = mapped_column(
        ForeignKey("evidence_artifact.id", ondelete="SET NULL"), nullable=True, index=True
    )
    record_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    capability: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(500), nullable=False)
    record_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    object_name: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    object_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    package_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    normalized_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_locator: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    dataset: Mapped["EvidenceDataset"] = relationship("EvidenceDataset", back_populates="records")
    artifact: Mapped["EvidenceArtifact | None"] = relationship("EvidenceArtifact", back_populates="records")
    correlations: Mapped[list["EvidenceCorrelation"]] = relationship(
        "EvidenceCorrelation", back_populates="evidence_record", cascade="all, delete-orphan"
    )


class EvidenceCorrelation(Base):
    """Explicit, statused relationship from an EvidenceRecord to a canonical target (ADR-017)."""

    __tablename__ = "evidence_correlation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_record_id: Mapped[int] = mapped_column(
        ForeignKey("evidence_record.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(50), nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rationale: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    evidence_record: Mapped["EvidenceRecord"] = relationship("EvidenceRecord", back_populates="correlations")


# ---------------------------------------------------------------------------
# SPRINT-09 domain models — AI Object Understanding (ADR-006/ADR-012)
# ---------------------------------------------------------------------------


class ObjectUnderstandingStatus(str, Enum):
    COMPLETED = "COMPLETED"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"
    FAILED = "FAILED"


class ObjectUnderstanding(Base):
    """The current AI-produced interpretation of one SAPObject (ADR-012 — structured,
    validated, evidence-bound; provider/prompt/schema provenance always recorded).

    One row per SAPObject: reprocessing upserts in place, mirroring `SAPObject.canonical_key`'s
    own upsert-not-recreate pattern (ADR-017), so a stale result never survives untouched."""

    __tablename__ = "object_understanding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessment.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sap_object_id: Mapped[int] = mapped_column(
        ForeignKey("sap_object.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    functional_purpose: Mapped[str] = mapped_column(Text, nullable=False, default="")
    technical_purpose: Mapped[str] = mapped_column(Text, nullable=False, default="")
    concepts: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Resolved from the model's evidence_refs (ref_id strings) against the ObjectEvidencePackage
    # used at generation time — [{"ref_id","source_type","entity_id"}, ...] so the API/UI can
    # link straight to the cited SourceFile/ATCFinding/EvidenceRecord without reparsing ref_ids.
    evidence_refs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt_capability: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("stage_run.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    assessment: Mapped["Assessment"] = relationship("Assessment")
    sap_object: Mapped["SAPObject"] = relationship("SAPObject", back_populates="understanding")
