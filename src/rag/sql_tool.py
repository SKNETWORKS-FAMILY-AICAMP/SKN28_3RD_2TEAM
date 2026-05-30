from __future__ import annotations

import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.query_analyzer import QueryAnalysis
from src.rag.context_builder import SqlQueryResult


@dataclass
class SQLToolConfig:
    project_root: Path = PROJECT_ROOT
    db_relative_path: Path = Path("data") / "database" / "kaist_ai.db"
    max_rows: int = 100

    @property
    def db_path(self) -> Path:
        env_path = os.getenv("KAIST_SQL_DB_PATH")

        if env_path:
            return Path(env_path)

        return self.project_root / self.db_relative_path


class SQLTool:
    TABLE_HINT_MAP = {
        "courses": "course",
        "professors": "person",
        "office_contacts": "asset",
        "admissions": "admission",
        "events": "event",
        "assets": "asset",
        "departments": "department",
    }

    def __init__(self, config: SQLToolConfig | None = None) -> None:
        self.config = config or SQLToolConfig()

    def query(
        self,
        analysis: QueryAnalysis,
    ) -> SqlQueryResult:
        if not self.config.db_path.exists():
            return self._missing_db_result(analysis)

        task_hint = analysis.sql_task_hint

        try:
            if task_hint == "course_lookup":
                return self._query_courses(analysis)

            if task_hint == "person_lookup":
                return self._query_people(analysis)

            if task_hint == "office_contact_lookup":
                return self._query_office_contacts(analysis)

            if task_hint == "admission_lookup":
                return self._query_admissions(analysis)

            if task_hint == "event_lookup":
                return self._query_events(analysis)

            if task_hint == "asset_lookup":
                return self._query_assets(analysis)

            if task_hint == "department_overview":
                return self._query_departments(analysis)

            return self._unsupported_task_result(analysis)

        except Exception as error:
            return SqlQueryResult(
                table_name=self._table_name_from_analysis(analysis),
                rows=[],
                columns=[],
                conditions=analysis.sql_conditions,
                message="SQL 조회 중 오류가 발생했습니다.",
                warnings=[f"{type(error).__name__}: {error}"],
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.config.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _query_courses(
        self,
        analysis: QueryAnalysis,
    ) -> SqlQueryResult:
        table_name = "course"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            has_department = self._table_exists(conn, "department")
            has_course_track = self._table_exists(conn, "course_track")
            has_track = self._table_exists(conn, "track")

            if has_department and has_course_track and has_track:
                sql = """
                SELECT
                    c.record_id,
                    c.dept,
                    d.dept_name,
                    c.course_code,
                    c.course_name,
                    c.course_type,
                    c.credit,
                    GROUP_CONCAT(t.track_name, ', ') AS track_names
                FROM course AS c
                LEFT JOIN department AS d
                    ON d.dept = c.dept
                LEFT JOIN course_track AS ct
                    ON ct.course_id = c.record_id
                LEFT JOIN track AS t
                    ON t.track_id = ct.track_id
                WHERE (:dept IS NULL OR c.dept = :dept)
                GROUP BY
                    c.record_id,
                    c.dept,
                    d.dept_name,
                    c.course_code,
                    c.course_name,
                    c.course_type,
                    c.credit
                ORDER BY
                    c.dept,
                    c.course_code,
                    c.course_name
                LIMIT :limit
                """
            elif has_department:
                sql = """
                SELECT
                    c.record_id,
                    c.dept,
                    d.dept_name,
                    c.course_code,
                    c.course_name,
                    c.course_type,
                    c.credit
                FROM course AS c
                LEFT JOIN department AS d
                    ON d.dept = c.dept
                WHERE (:dept IS NULL OR c.dept = :dept)
                ORDER BY
                    c.dept,
                    c.course_code,
                    c.course_name
                LIMIT :limit
                """
            else:
                sql = """
                SELECT *
                FROM course
                WHERE (:dept IS NULL OR dept = :dept)
                LIMIT :limit
                """

            rows = self._fetch_all(
                conn=conn,
                sql=sql,
                params={
                    "dept": analysis.department_code,
                    "limit": self.config.max_rows,
                },
            )

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="교과목 조회가 완료되었습니다.",
        )

    def _query_people(
        self,
        analysis: QueryAnalysis,
    ) -> SqlQueryResult:
        table_name = "person"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            has_department = self._table_exists(conn, "department")

            if has_department:
                sql = """
                SELECT
                    p.record_id,
                    p.dept,
                    d.dept_name,
                    p.name,
                    p.role_normalized,
                    p.email,
                    p.research_area
                FROM person AS p
                LEFT JOIN department AS d
                    ON d.dept = p.dept
                WHERE (:dept IS NULL OR p.dept = :dept)
                ORDER BY
                    p.dept,
                    p.role_normalized,
                    p.name
                LIMIT :limit
                """
            else:
                sql = """
                SELECT *
                FROM person
                WHERE (:dept IS NULL OR dept = :dept)
                LIMIT :limit
                """

            rows = self._fetch_all(
                conn=conn,
                sql=sql,
                params={
                    "dept": analysis.department_code,
                    "limit": self.config.max_rows,
                },
            )

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="교수/구성원 조회가 완료되었습니다.",
        )

    def _query_office_contacts(
        self,
        analysis: QueryAnalysis,
    ) -> SqlQueryResult:
        table_name = "asset"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            asset_columns = self._columns(conn, table_name)

            conditions = []
            params: dict[str, Any] = {
                "dept": analysis.department_code,
                "limit": self.config.max_rows,
            }

            if "dept" in asset_columns:
                conditions.append("(:dept IS NULL OR a.dept = :dept)")

            if "asset_type" in asset_columns:
                conditions.append(
                    "(a.asset_type IN ('phone', 'email', 'contact', 'location') "
                    "OR a.asset_type LIKE '%phone%' "
                    "OR a.asset_type LIKE '%email%')"
                )

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            if self._table_exists(conn, "department") and "dept" in asset_columns:
                sql = f"""
                SELECT
                    a.*,
                    d.dept_name
                FROM asset AS a
                LEFT JOIN department AS d
                    ON d.dept = a.dept
                WHERE {where_clause}
                ORDER BY
                    a.dept,
                    a.asset_type
                LIMIT :limit
                """
            else:
                sql = f"""
                SELECT *
                FROM asset AS a
                WHERE {where_clause}
                LIMIT :limit
                """

            rows = self._fetch_all(
                conn=conn,
                sql=sql,
                params=params,
            )

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="연락처/사무실 관련 자산 조회가 완료되었습니다.",
        )

    def _query_admissions(
        self,
        analysis: QueryAnalysis,
    ) -> SqlQueryResult:
        table_name = "admission"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            has_department = self._table_exists(conn, "department")

            if has_department:
                sql = """
                SELECT
                    a.record_id,
                    a.dept,
                    d.dept_name,
                    a.admission_type,
                    a.title,
                    a.content,
                    a.schedule_date
                FROM admission AS a
                LEFT JOIN department AS d
                    ON d.dept = a.dept
                WHERE (:dept IS NULL OR a.dept = :dept)
                ORDER BY
                    a.dept,
                    a.admission_type,
                    a.title
                LIMIT :limit
                """
            else:
                sql = """
                SELECT *
                FROM admission
                WHERE (:dept IS NULL OR dept = :dept)
                LIMIT :limit
                """

            rows = self._fetch_all(
                conn=conn,
                sql=sql,
                params={
                    "dept": analysis.department_code,
                    "limit": self.config.max_rows,
                },
            )

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="입학 정보 조회가 완료되었습니다.",
        )

    def _query_events(
        self,
        analysis: QueryAnalysis,
    ) -> SqlQueryResult:
        table_name = "event"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            has_department = self._table_exists(conn, "department")

            if has_department:
                sql = """
                SELECT
                    e.record_id,
                    e.dept,
                    d.dept_name,
                    e.event_type,
                    e.title,
                    e.event_date
                FROM event AS e
                LEFT JOIN department AS d
                    ON d.dept = e.dept
                WHERE (:dept IS NULL OR e.dept = :dept)
                ORDER BY
                    e.event_date DESC,
                    e.title
                LIMIT :limit
                """
            else:
                sql = """
                SELECT *
                FROM event
                WHERE (:dept IS NULL OR dept = :dept)
                LIMIT :limit
                """

            rows = self._fetch_all(
                conn=conn,
                sql=sql,
                params={
                    "dept": analysis.department_code,
                    "limit": self.config.max_rows,
                },
            )

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="행사 정보 조회가 완료되었습니다.",
        )

    def _query_assets(
        self,
        analysis: QueryAnalysis,
    ) -> SqlQueryResult:
        table_name = "asset"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            has_department = self._table_exists(conn, "department")

            if has_department:
                sql = """
                SELECT
                    a.*,
                    d.dept_name
                FROM asset AS a
                LEFT JOIN department AS d
                    ON d.dept = a.dept
                WHERE (:dept IS NULL OR a.dept = :dept)
                ORDER BY
                    a.dept,
                    a.asset_type
                LIMIT :limit
                """
            else:
                sql = """
                SELECT *
                FROM asset
                WHERE (:dept IS NULL OR dept = :dept)
                LIMIT :limit
                """

            rows = self._fetch_all(
                conn=conn,
                sql=sql,
                params={
                    "dept": analysis.department_code,
                    "limit": self.config.max_rows,
                },
            )

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="자료/링크 조회가 완료되었습니다.",
        )

    def _query_departments(
        self,
        analysis: QueryAnalysis,
    ) -> SqlQueryResult:
        table_name = "department"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            sql = """
            SELECT *
            FROM department
            WHERE (:dept IS NULL OR dept = :dept)
            ORDER BY dept
            LIMIT :limit
            """

            rows = self._fetch_all(
                conn=conn,
                sql=sql,
                params={
                    "dept": analysis.department_code,
                    "limit": self.config.max_rows,
                },
            )

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="학과 정보 조회가 완료되었습니다.",
        )

    def _fetch_all(
        self,
        conn: sqlite3.Connection,
        sql: str,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def _table_exists(
        self,
        conn: sqlite3.Connection,
        table_name: str,
    ) -> bool:
        cursor = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            """,
            (table_name,),
        )

        return cursor.fetchone() is not None

    def _columns(
        self,
        conn: sqlite3.Connection,
        table_name: str,
    ) -> set[str]:
        cursor = conn.execute(f"PRAGMA table_info({table_name})")

        return {
            row["name"]
            for row in cursor.fetchall()
        }

    def _result(
        self,
        table_name: str,
        rows: list[dict[str, Any]],
        analysis: QueryAnalysis,
        message: str,
        warnings: list[str] | None = None,
    ) -> SqlQueryResult:
        columns = list(rows[0].keys()) if rows else []

        return SqlQueryResult(
            table_name=table_name,
            rows=rows,
            columns=columns,
            conditions=analysis.sql_conditions,
            message=message,
            warnings=warnings or [],
        )

    def _missing_db_result(
        self,
        analysis: QueryAnalysis,
    ) -> SqlQueryResult:
        return SqlQueryResult(
            table_name=self._table_name_from_analysis(analysis),
            rows=[],
            columns=[],
            conditions=analysis.sql_conditions,
            message="SQL DB 파일을 찾을 수 없습니다.",
            warnings=[
                f"DB 경로를 확인하세요: {self.config.db_path}",
                "KAIST_SQL_DB_PATH 환경변수로 DB 경로를 지정할 수 있습니다.",
            ],
        )

    def _missing_table_result(
        self,
        table_name: str,
        analysis: QueryAnalysis,
    ) -> SqlQueryResult:
        return SqlQueryResult(
            table_name=table_name,
            rows=[],
            columns=[],
            conditions=analysis.sql_conditions,
            message=f"SQL 테이블을 찾을 수 없습니다: {table_name}",
            warnings=[
                f"ERD 기준 테이블 `{table_name}`이 DB에 생성되어 있는지 확인하세요.",
            ],
        )

    def _unsupported_task_result(
        self,
        analysis: QueryAnalysis,
    ) -> SqlQueryResult:
        return SqlQueryResult(
            table_name=self._table_name_from_analysis(analysis),
            rows=[],
            columns=[],
            conditions=analysis.sql_conditions,
            message="지원하지 않는 SQL task입니다.",
            warnings=[
                f"sql_task_hint를 확인하세요: {analysis.sql_task_hint}",
            ],
        )

    def _table_name_from_analysis(
        self,
        analysis: QueryAnalysis,
    ) -> str:
        if not analysis.sql_table_hint:
            return "unknown"

        return self.TABLE_HINT_MAP.get(
            analysis.sql_table_hint,
            analysis.sql_table_hint,
        )


def run_examples() -> None:
    from src.rag.query_analyzer import QuestionAnalyzer

    analyzer = QuestionAnalyzer()
    sql_tool = SQLTool()

    questions = [
        "AI시스템학과 교과목 알려줘",
        "AX학과 교수진 이메일 목록 보여줘",
        "KAIST 학과 사무실 전화번호 알려줘",
        "자료 다운로드 링크 알려줘",
        "AI컴퓨팅학과 입학 정보 알려줘",
        "AI컴퓨팅학과 학과설명회 일정 알려줘",
    ]

    for question in questions:
        analysis = analyzer.analyze(question)
        result = sql_tool.query(analysis)

        print("=" * 100)
        print("질문:", question)
        print("route:", analysis.route)
        print("task:", analysis.sql_task_hint)
        print("table:", result.table_name)
        print("message:", result.message)
        print("warnings:", result.warnings)
        print("row_count:", len(result.rows))
        print("columns:", result.columns)
        print("rows_preview:", result.rows[:3])


if __name__ == "__main__":
    run_examples()