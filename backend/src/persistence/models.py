"""ORM models. Import every model module here so Alembic autogenerate sees the full metadata."""

from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, func
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
# SPRINT-01 domain models
# ---------------------------------------------------------------------------


class Client(Base):
    """An organisation that owns one or more SAP systems being assessed."""

    __tablename__ = "client"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    systems: Mapped[list["SAPSystem"]] = relationship(
        "SAPSystem", back_populates="client", cascade="all, delete-orphan"
    )


class SAPSystem(Base):
    """A specific SAP installation belonging to a Client."""

    __tablename__ = "sap_system"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("client.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sid: Mapped[str | None] = mapped_column(String(10), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    client: Mapped["Client"] = relationship("Client", back_populates="systems")
    assessments: Mapped[list["Assessment"]] = relationship(
        "Assessment", back_populates="sap_system", cascade="all, delete-orphan"
    )


class AssessmentStatus(str, Enum):
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Assessment(Base):
    """A scoped analysis run for a specific SAP system."""

    __tablename__ = "assessment"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sap_system_id: Mapped[int] = mapped_column(
        ForeignKey("sap_system.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=AssessmentStatus.CREATED.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    sap_system: Mapped["SAPSystem"] = relationship("SAPSystem", back_populates="assessments")
    scans: Mapped[list["SourceScan"]] = relationship(
        "SourceScan", back_populates="assessment", cascade="all, delete-orphan"
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
