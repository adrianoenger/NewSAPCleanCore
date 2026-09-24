"""ORM models. Import every model module here so Alembic autogenerate sees the full metadata."""

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, func
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
