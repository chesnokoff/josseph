from __future__ import annotations

import logging

from josseph.utils import next_logfile, setup_trace


def test_setup_trace_registers_trace_level_and_method():
    setup_trace()

    assert logging.getLevelName(logging.TRACE) == "TRACE"
    assert callable(logging.getLogger("josseph").trace)


def test_next_logfile_uses_highest_available_suffix(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "josseph-0001.log").write_text("", encoding="utf-8")
    (log_dir / "josseph-0007.log").write_text("", encoding="utf-8")

    assert next_logfile(log_dir, "josseph") == log_dir / "josseph-0008.log"
