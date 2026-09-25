"""ORM models. Import every model module here so Alembic autogenerate sees the full metadata."""

from datetime import date, datetime
from enum import Enum

from sqlalchemy import JSON, BigInteger, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
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
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    line_start: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attributes: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    parsed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="sap_objects")
    source_file: Mapped["SourceFile"] = relationship("SourceFile", back_populates="sap_objects")
    dependencies: Mapped[list["SAPObjectDependency"]] = relationship(
        "SAPObjectDependency", back_populates="source_object", cascade="all, delete-orphan",
        foreign_keys="SAPObjectDependency.source_object_id",
    )
    atc_findings: Mapped[list["ATCFinding"]] = relationship(
        "ATCFinding", back_populates="correlated_object", foreign_keys="ATCFinding.correlated_object_id"
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
