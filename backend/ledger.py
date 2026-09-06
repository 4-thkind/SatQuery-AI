"""Evidence ledger. Spec section 13.3.

SQLite, stdlib only. Every answer and every tool execution is written here, so a
number shown weeks ago can still be traced to the pixels that produced it.
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
import uuid
from datetime import datetime, timezone

from .schemas import AnswerPayload

DB_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "ledger.db"

DDL = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS turns (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    created_at TEXT NOT NULL,
    query TEXT NOT NULL,
    intent TEXT,
    verdict TEXT,
    scene_ids TEXT,
    narration TEXT,
    headline TEXT,
    confidence REAL,
    tier TEXT,
    duration_ms REAL
);
CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id TEXT NOT NULL REFERENCES turns(id),
    step_id TEXT NOT NULL,
    tool TEXT NOT NULL,
    ok INTEGER NOT NULL,
    value TEXT,
    unit TEXT,
    arithmetic TEXT,
    reproduce TEXT,
    caveats TEXT,
    provenance TEXT,
    upstream TEXT,
    duration_ms REAL
);
CREATE INDEX IF NOT EXISTS idx_evidence_turn ON evidence(turn_id);
CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id);
"""


def connect(path: pathlib.Path | str = DB_PATH) -> sqlite3.Connection:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(DDL)
    return con


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record(con: sqlite3.Connection, session_id: str, payload: AnswerPayload) -> str:
    """Write one answer plus its evidence rows. Returns the turn id."""
    turn_id = f"EVT-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:4].upper()}"
    con.execute("INSERT OR IGNORE INTO sessions VALUES (?,?)", (session_id, _now()))
    con.execute(
        "INSERT INTO turns VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (turn_id, session_id, _now(), payload.query, payload.intent, payload.verdict,
         json.dumps(payload.scene_ids), payload.narration,
         json.dumps(payload.headline) if payload.headline else None,
         payload.confidence.score if payload.confidence else None,
         payload.tier, payload.duration_ms),
    )
    con.executemany(
        "INSERT INTO evidence (turn_id, step_id, tool, ok, value, unit, arithmetic,"
        " reproduce, caveats, provenance, upstream, duration_ms)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [(turn_id, e.step_id, e.tool, int(e.ok), json.dumps(e.value), e.unit,
          e.arithmetic, e.reproduce, json.dumps(e.caveats),
          json.dumps(e.provenance), json.dumps(e.upstream), e.duration_ms)
         for e in payload.evidence],
    )
    con.commit()
    return turn_id


def get_turn(con: sqlite3.Connection, turn_id: str) -> dict | None:
    row = con.execute("SELECT * FROM turns WHERE id=?", (turn_id,)).fetchone()
    if not row:
        return None
    ev = con.execute("SELECT * FROM evidence WHERE turn_id=? ORDER BY id",
                     (turn_id,)).fetchall()
    out = dict(row)
    out["scene_ids"] = json.loads(out["scene_ids"] or "[]")
    out["headline"] = json.loads(out["headline"]) if out["headline"] else None
    out["evidence"] = [
        {**dict(e), "value": json.loads(e["value"]) if e["value"] else None,
         "caveats": json.loads(e["caveats"] or "[]"),
         "provenance": json.loads(e["provenance"] or "{}"),
         "upstream": json.loads(e["upstream"] or "[]")}
        for e in ev
    ]
    return out


def recent(con: sqlite3.Connection, limit: int = 20) -> list[dict]:
    rows = con.execute(
        "SELECT id, created_at, query, intent, verdict, headline, confidence"
        " FROM turns ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)).fetchall()
    return [{**dict(r), "headline": json.loads(r["headline"]) if r["headline"] else None}
            for r in rows]


def _demo() -> None:
    """Runnable check: an answer must survive a round trip with its arithmetic."""
    import tempfile
    from .pipeline import answer

    with tempfile.TemporaryDirectory() as d:
        con = connect(pathlib.Path(d) / "t.db")
        p = answer("How much area is flooded?", "bihar_post_flood")
        tid = record(con, "sess-1", p)

        got = get_turn(con, tid)
        assert got["verdict"] == "ANSWER"
        assert json.loads(got["headline"] if isinstance(got["headline"], str)
                          else json.dumps(got["headline"]))["value"] == p.headline["value"]
        assert len(got["evidence"]) == len(p.evidence)

        # The arithmetic string must survive: it is the point of the ledger.
        area = [e for e in got["evidence"] if e["tool"] == "measure_area"][0]
        assert "px x" in area["arithmetic"] and "ha" in area["arithmetic"]
        assert area["provenance"]["pixel_area_m2"] == 100.0

        # An ABSTAIN is recorded too -- refusals are evidence.
        record(con, "sess-1", answer("burn scar area", "forest_burn"))
        assert len(recent(con)) == 2
        assert get_turn(con, "nope") is None

        print(f"ledger: ok  {tid} with {len(got['evidence'])} evidence rows")
        print(f"  {area['arithmetic']}")
        con.close()      # Windows will not delete an open .db at teardown


if __name__ == "__main__":
    _demo()
