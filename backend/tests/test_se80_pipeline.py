"""Integration test: SE80 HTML export assembly wired into the `parse` pipeline stage
(`pipeline.stages._assemble_se80_class_exports`/`_parse_prepare`/`_parse_process_item`) — the fix
for a real customer export where class/method "Code listing" HTML files parsed to zero SAPObjects
(see `parsing/se80_html.py`'s module docstring)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from sqlalchemy import select, text

from persistence.database import get_session_factory
from persistence.models import (
    Assessment,
    AssessmentStatus,
    Client,
    PipelineRun,
    SAPObject,
    ScanStatus,
    SourceFile,
    SourceScan,
    StageRun,
    WorkItem,
)
from pipeline.stages import _parse_prepare, _parse_process_item

_CLASS_HTML = """\
<html><head><title>ZCALL_WS</title></head><body>
<h2>Code listing for class: ZCALL_WS</h2>
<div class="code">
class ZCALL_WS definition<br />
&nbsp;&nbsp;public<br />
&nbsp;&nbsp;final<br />
&nbsp;&nbsp;create&nbsp;public&nbsp;.<br />
<br />
public section.<br />
&nbsp;&nbsp;methods&nbsp;<a&nbsp;href="public_methods/execute.html">EXECUTE</a>&nbsp;.<br />
</div>
</body></html>
"""

_METHOD_HTML = """\
<html><head><title>EXECUTE</title></head><body>
<h2>Code listing for: EXECUTE</h2>
<div class="code">
METHOD execute.<br />
&nbsp;&nbsp;DATA:&nbsp;l_result&nbsp;TYPE&nbsp;string.<br />
ENDMETHOD.<br />
</div>
</body></html>
"""


def _cleanup(session, assessment_id: int) -> None:
    session.execute(
        text("DELETE FROM client WHERE id = (SELECT client_id FROM assessment WHERE id = :aid)"),
        {"aid": assessment_id},
    )
    session.commit()


def test_se80_class_and_method_html_assemble_into_one_parseable_class() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        class_dir = Path(tmp) / "zcall_ws"
        methods_dir = class_dir / "public_methods"
        methods_dir.mkdir(parents=True)
        (class_dir / "class-zcall_ws.html").write_text(_CLASS_HTML, encoding="utf-8")
        (methods_dir / "execute.html").write_text(_METHOD_HTML, encoding="utf-8")

        with get_session_factory()() as session:
            c = Client(name="Sprint17 SE80 Test Client")
            session.add(c)
            session.flush()
            a = Assessment(client_id=c.id, name="Sprint17 SE80 Test", status=AssessmentStatus.CREATED.value)
            session.add(a)
            session.flush()
            scan = SourceScan(
                assessment_id=a.id, source_path=tmp, status=ScanStatus.COMPLETED.value,
                total_files=2, scanned_files=2,
            )
            session.add(scan)
            session.flush()
            class_sf = SourceFile(
                scan_id=scan.id, assessment_id=a.id, rel_path="zcall_ws/class-zcall_ws.html",
                size_bytes=0, mtime=0.0, sha256="0" * 64, category="abap_source",
            )
            method_sf = SourceFile(
                scan_id=scan.id, assessment_id=a.id, rel_path="zcall_ws/public_methods/execute.html",
                size_bytes=0, mtime=0.0, sha256="1" * 64, category="abap_source",
            )
            session.add_all([class_sf, method_sf])
            session.flush()
            run = PipelineRun(assessment_id=a.id, source_path=tmp, source_scan_id=scan.id, kind="source_processing")
            session.add(run)
            session.flush()
            stage = StageRun(pipeline_run_id=run.id, stage_key="parse", sequence=1, depends_on=["scan"])
            session.add(stage)
            session.commit()

            asmnt_id, run_id, stage_id = a.id, run.id, stage.id
            class_sf_id, method_sf_id = class_sf.id, method_sf.id

        try:
            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                stage = session.get(StageRun, stage_id)
                _parse_prepare(stage, run, session)

            with get_session_factory()() as session:
                items = list(session.scalars(select(WorkItem).where(WorkItem.stage_run_id == stage_id)))
                item_source_file_ids = {i.payload["source_file_id"] for i in items}

                # the raw HTML class/method files never get their own WorkItem — only the
                # assembled .abap file does
                assert class_sf_id not in item_source_file_ids
                assert method_sf_id not in item_source_file_ids
                assert len(items) == 1

                run = session.get(PipelineRun, run_id)
                stage = session.get(StageRun, stage_id)
                for item in items:
                    _parse_process_item(item, stage, run, session)
                session.commit()

            with get_session_factory()() as session:
                objects = list(session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)))
                assert len(objects) == 1
                obj = objects[0]
                assert obj.object_type == "class"
                assert obj.object_name == "ZCALL_WS"
                assert "EXECUTE" in obj.attributes["methods"]

            assembled_path = class_dir / ".assembled" / "ZCALL_WS.abap"
            assert assembled_path.is_file()
            assert "METHOD execute." in assembled_path.read_text(encoding="utf-8")
        finally:
            with get_session_factory()() as session:
                _cleanup(session, asmnt_id)
