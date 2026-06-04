from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False


CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.query_analyzer import QueryAnalysis


# ============================================================
# 1. 상수
# ============================================================

SUPPORTED_AI_COLLEGE_DEPT_CODES = ["aic", "ai_systems", "ax", "fx"]

DEPT_NAME_MAP = {
    "aic": "AI컴퓨팅학과",
    "ai_systems": "AI시스템학과",
    "ax": "AX학과",
    "fx": "AI미래학과",
}

DEPT_ORDER_SQL = "FIELD(dept, 'aic', 'ai_systems', 'ax', 'fx')"


# ============================================================
# 2. 결과 / 설정 dataclass
# ============================================================

@dataclass
class SqlQueryResult:
    """
    SQLTool 조회 결과 객체.

    이 클래스는 sql_tool.py 내부에서 직접 관리한다.
    context_builder.py는 이 객체를 정의하지 않고 rows/table_name만 읽는다.
    """

    table_name: str | None = None
    rows: list[dict[str, Any]] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    conditions: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    warnings: list[str] = field(default_factory=list)

    status: str = "ok"
    query: str | None = None
    params: Any | None = None
    sql_task_hint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def row_count(self) -> int:
        return len(self.rows or [])

    @property
    def results(self) -> list[dict[str, Any]]:
        return self.rows

    def is_empty(self) -> bool:
        return self.row_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "table_name": self.table_name,
            "rows": self.rows,
            "columns": self.columns,
            "conditions": self.conditions,
            "row_count": self.row_count,
            "message": self.message,
            "warnings": self.warnings,
            "status": self.status,
            "query": self.query,
            "params": self.params,
            "sql_task_hint": self.sql_task_hint,
            "metadata": self.metadata,
        }

    def to_debug_dict(self) -> dict[str, Any]:
        return self.to_dict()


@dataclass
class SQLToolConfig:
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "kaist_ai"
    charset: str = "utf8mb4"
    max_rows: int = 300

    @classmethod
    def from_env(cls) -> "SQLToolConfig":
        load_dotenv()

        def env_first(*names: str, default: str = "") -> str:
            for name in names:
                value = os.getenv(name)
                if value not in {None, ""}:
                    return str(value)
            return default

        return cls(
            host=env_first("KAIST_SQL_HOST", "MYSQL_HOST", "DB_HOST", default="127.0.0.1"),
            port=int(env_first("KAIST_SQL_PORT", "MYSQL_PORT", "DB_PORT", default="3306")),
            user=env_first("KAIST_SQL_USER", "MYSQL_USER", "DB_USER", default="root"),
            password=env_first("KAIST_SQL_PASSWORD", "MYSQL_PASSWORD", "DB_PASSWORD", default=""),
            database=env_first("KAIST_SQL_DATABASE", "MYSQL_DATABASE", "DB_NAME", default="kaist_ai"),
            charset=env_first("KAIST_SQL_CHARSET", "MYSQL_CHARSET", default="utf8mb4"),
            max_rows=int(env_first("KAIST_SQL_MAX_ROWS", default="300")),
        )


# ============================================================
# 3. SQLTool
# ============================================================

class SQLTool:
    TABLE_HINT_MAP = {
        "courses": "course",
        "course": "course",
        "professors": "person",
        "people": "person",
        "person": "person",
        "office_contacts": "office_contacts",
        "department_offices": "department_offices",
        "admissions": "admission",
        "admission": "admission",
        "events": "event",
        "event": "event",
        "assets": "asset",
        "asset": "asset",
        "departments": "department",
        "department": "department",
        "kaist_profile": "kaist_profile",
        "kaist_statistics": "kaist_statistics",
        "kaist_links": "kaist_links",
        "department_homepage": "department_homepage",
        "department_homepages": "department_homepage",
        "requirements": "department_requirement",
        "department_requirements": "department_requirement",
        "department_requirement": "department_requirement",
    }

    def __init__(self, config: SQLToolConfig | None = None) -> None:
        self.config = config or SQLToolConfig.from_env()
        self.driver_name = self._select_driver()

    # ------------------------------------------------------------
    # public API
    # ------------------------------------------------------------

    def query(self, analysis: QueryAnalysis) -> SqlQueryResult:
        task_hint = getattr(analysis, "sql_task_hint", None)
        table_hint = getattr(analysis, "sql_table_hint", None)
        table_name = self.TABLE_HINT_MAP.get(table_hint, table_hint)
    
        try:
            if table_name == "course":
                return self._query_courses(analysis)
    
            if table_name == "office_contacts":
                return self._query_office_contacts(analysis)
    
            if task_hint == "admission_lookup":
                return self._query_admissions(analysis)
    
            if task_hint == "event_lookup":
                return self._query_events(analysis)
    
            if task_hint == "asset_lookup":
                return self._query_assets(analysis)
    
            if task_hint == "kaist_profile_lookup":
                return self._query_kaist_profile(analysis)
    
            if task_hint == "kaist_statistics_lookup":
                return self._query_kaist_statistics(analysis)
    
            if task_hint == "kaist_link_lookup":
                return self._query_kaist_links(analysis)
    
            if task_hint == "department_homepage_lookup":
                return self._query_department_homepages(analysis)
    
            if task_hint == "requirement_lookup":
                return self._query_requirements(analysis)
    
            if task_hint == "department_overview" or table_name == "department":
                return self._query_departments(analysis)
    
            normalized_table = self.TABLE_HINT_MAP.get(str(table_hint), None)
    
            if normalized_table == "course":
                return self._query_courses(analysis)
    
            if normalized_table == "person":
                return self._query_people(analysis)
    
            if normalized_table == "admission":
                return self._query_admissions(analysis)
    
            if normalized_table == "event":
                return self._query_events(analysis)
    
            if normalized_table == "asset":
                return self._query_assets(analysis)
    
            if normalized_table == "kaist_profile":
                return self._query_kaist_profile(analysis)
    
            if normalized_table == "kaist_statistics":
                return self._query_kaist_statistics(analysis)
    
            if normalized_table == "kaist_links":
                return self._query_kaist_links(analysis)
    
            if normalized_table == "department_homepage":
                return self._query_department_homepages(analysis)
    
            if normalized_table == "department_requirement":
                return self._query_requirements(analysis)
    
            return SqlQueryResult(
                table_name=normalized_table or table_hint,
                rows=[],
                columns=[],
                conditions=getattr(analysis, "sql_conditions", {}),
                message=f"지원하지 않는 SQL task입니다: {task_hint}",
                warnings=[f"unsupported sql_task_hint: {task_hint}"],
                status="unsupported_task",
                sql_task_hint=task_hint,
            )
    
        except Exception as exc:
            return SqlQueryResult(
                table_name=table_name or table_hint,
                rows=[],
                columns=[],
                conditions=getattr(analysis, "sql_conditions", {}),
                message="SQL 조회 중 오류가 발생했습니다.",
                warnings=[f"{type(exc).__name__}: {exc}"],
                status="sql_error",
                sql_task_hint=task_hint,
            )

    def _connect(self) -> Any:
        if self.driver_name == "pymysql":
            import pymysql
            return pymysql.connect(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
                charset=self.config.charset,
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
            )

        if self.driver_name == "mysql_connector":
            import mysql.connector
            return mysql.connector.connect(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
                charset=self.config.charset,
                use_unicode=True,
                autocommit=True,
            )

        raise RuntimeError(f"지원하지 않는 MySQL driver입니다: {self.driver_name}")

    def _fetch_all(
        self,
        conn: Any,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        if self.driver_name == "pymysql":
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]

        if self.driver_name == "mysql_connector":
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            finally:
                cursor.close()

        return []

    def _table_exists(self, conn: Any, table_name: str) -> bool:
        sql = """
        SELECT COUNT(*) AS cnt
        FROM information_schema.tables
        WHERE table_schema = %s
          AND table_name = %s
        """
        rows = self._fetch_all(conn, sql, (self.config.database, table_name))
        return bool(rows and rows[0].get("cnt", 0) > 0)

    def _columns(self, rows: list[dict[str, Any]]) -> list[str]:
        if not rows:
            return []
        return list(rows[0].keys())

    def _limit(self) -> int:
        return max(1, int(self.config.max_rows))

    # ------------------------------------------------------------
    # condition helpers
    # ------------------------------------------------------------

    def _target_dept_codes(self, analysis: QueryAnalysis) -> list[str]:
        if analysis.department_code:
            return [analysis.department_code]

        if analysis.department_codes:
            return [
                code for code in analysis.department_codes
                if code in SUPPORTED_AI_COLLEGE_DEPT_CODES
            ]

        return SUPPORTED_AI_COLLEGE_DEPT_CODES.copy()

    def _dept_where_clause(
        self,
        analysis: QueryAnalysis,
        alias: str | None = None,
    ) -> tuple[str, list[Any]]:
        dept_codes = self._target_dept_codes(analysis)
        col = f"{alias}.dept" if alias else "dept"

        if len(dept_codes) == 1:
            return f"{col} = %s", [dept_codes[0]]

        placeholders = ", ".join(["%s"] * len(dept_codes))
        return f"{col} IN ({placeholders})", list(dept_codes)

    def _dept_name_keywords(self, analysis: QueryAnalysis) -> list[str]:
        dept_codes = self._target_dept_codes(analysis)
        names = [DEPT_NAME_MAP.get(code) for code in dept_codes]
        return [name for name in names if name]

    def _result(
        self,
        table_name: str | None,
        rows: list[dict[str, Any]],
        analysis: QueryAnalysis,
        message: str,
        warnings: list[str] | None = None,
        query: str | None = None,
        params: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SqlQueryResult:
        return SqlQueryResult(
            table_name=table_name,
            rows=rows,
            columns=self._columns(rows),
            conditions=analysis.sql_conditions,
            message=message,
            warnings=warnings or [],
            status="ok",
            query=query,
            params=params,
            sql_task_hint=analysis.sql_task_hint,
            metadata=metadata or {},
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
            message=f"테이블이 존재하지 않습니다: {table_name}",
            warnings=[f"missing table: {table_name}"],
            status="missing_table",
            sql_task_hint=analysis.sql_task_hint,
        )

    # ------------------------------------------------------------
    # query methods
    # ------------------------------------------------------------

    def _query_courses(self, analysis: QueryAnalysis) -> SqlQueryResult:
        table_name = "course"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            where_clause, params = self._dept_where_clause(analysis, alias="c")

            sql = f"""
            SELECT
                c.record_id,
                c.course_id,
                c.dept,
                d.dept_name,
                c.course_level,
                c.course_code,
                c.course_code_norm,
                c.course_name,
                c.course_type,
                c.credit,
                c.course_description,
                c.source_url,
                c.crawled_at,
                c.source_sheet
            FROM course AS c
            LEFT JOIN department AS d
              ON d.dept = c.dept
            WHERE {where_clause}
            ORDER BY FIELD(c.dept, 'aic', 'ai_systems', 'ax', 'fx'),
                     c.course_level,
                     c.course_code,
                     c.course_name
            LIMIT %s
            """

            final_params = tuple(params + [self._limit()])
            rows = self._fetch_all(conn, sql, final_params)

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="교과목 조회가 완료되었습니다.",
            query=sql,
            params=final_params,
        )

    def _query_people(self, analysis: QueryAnalysis) -> SqlQueryResult:
        table_name = "person"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            where_clause, params = self._dept_where_clause(analysis, alias="p")

            sql = f"""
            SELECT
                p.record_id,
                p.dept,
                d.dept_name,
                p.name,
                p.name_ko,
                p.name_en,
                p.role,
                p.role_normalized,
                p.faculty_group,
                p.email,
                p.phone,
                p.office,
                p.research_area,
                p.homepage,
                p.source_url,
                p.crawled_at,
                p.source_sheet
            FROM person AS p
            LEFT JOIN department AS d
              ON d.dept = p.dept
            WHERE {where_clause}
            ORDER BY FIELD(p.dept, 'aic', 'ai_systems', 'ax', 'fx'),
                     p.role_normalized,
                     p.name
            LIMIT %s
            """

            final_params = tuple(params + [self._limit()])
            rows = self._fetch_all(conn, sql, final_params)

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="교수진/구성원 조회가 완료되었습니다.",
            query=sql,
            params=final_params,
        )

    def _query_office_contacts(self, analysis: QueryAnalysis) -> SqlQueryResult:
        rows: list[dict[str, Any]] = []
        warnings: list[str] = []

        with self._connect() as conn:
            # 1. department_offices
            if self._table_exists(conn, "department_offices"):
                dept_names = self._dept_name_keywords(analysis)

                office_where_parts = []
                office_params: list[Any] = []

                for name in dept_names:
                    office_where_parts.append("program_name LIKE %s")
                    office_params.append(f"%{name}%")

                if office_where_parts:
                    office_where = " OR ".join(office_where_parts)
                else:
                    office_where = "1=1"

                sql_office = f"""
                SELECT
                    'department_offices' AS source_table,
                    NULL AS dept,
                    program_name AS dept_name,
                    phone,
                    website,
                    building_location,
                    NULL AS email,
                    NULL AS office,
                    source_page AS source_url,
                    source
                FROM department_offices
                WHERE {office_where}
                LIMIT %s
                """
                rows.extend(
                    self._fetch_all(
                        conn,
                        sql_office,
                        tuple(office_params + [self._limit()]),
                    )
                )
            else:
                warnings.append("department_offices 테이블이 없습니다.")

            # 2. asset contact_info
            if self._table_exists(conn, "asset"):
                where_clause, params = self._dept_where_clause(analysis, alias="a")
                sql_asset = f"""
                SELECT
                    'asset' AS source_table,
                    a.dept,
                    d.dept_name,
                    NULL AS phone,
                    a.url AS website,
                    NULL AS building_location,
                    NULL AS email,
                    NULL AS office,
                    a.source_url,
                    a.text AS contact_text,
                    a.content_type,
                    a.topic
                FROM asset AS a
                LEFT JOIN department AS d
                  ON d.dept = a.dept
                WHERE {where_clause}
                  AND (
                        a.content_type IN ('contact_info', 'link')
                        OR a.text LIKE '%연락%'
                        OR a.text LIKE '%전화%'
                        OR a.text LIKE '%문의%'
                        OR a.text LIKE '%사무실%'
                        OR a.text LIKE '%행정%'
                  )
                LIMIT %s
                """
                rows.extend(
                    self._fetch_all(
                        conn,
                        sql_asset,
                        tuple(params + [self._limit()]),
                    )
                )
            else:
                warnings.append("asset 테이블이 없습니다.")

            # 3. person 연락처
            if self._table_exists(conn, "person"):
                where_clause, params = self._dept_where_clause(analysis, alias="p")
                sql_person = f"""
                SELECT
                    'person' AS source_table,
                    p.dept,
                    d.dept_name,
                    p.phone,
                    p.homepage AS website,
                    NULL AS building_location,
                    p.email,
                    p.office,
                    p.source_url,
                    p.name,
                    p.role,
                    p.role_normalized
                FROM person AS p
                LEFT JOIN department AS d
                  ON d.dept = p.dept
                WHERE {where_clause}
                  AND (
                        p.email IS NOT NULL AND p.email <> ''
                        OR p.phone IS NOT NULL AND p.phone <> ''
                        OR p.office IS NOT NULL AND p.office <> ''
                        OR p.homepage IS NOT NULL AND p.homepage <> ''
                  )
                LIMIT %s
                """
                rows.extend(
                    self._fetch_all(
                        conn,
                        sql_person,
                        tuple(params + [self._limit()]),
                    )
                )
            else:
                warnings.append("person 테이블이 없습니다.")

        rows = self._dedupe_rows(rows)

        return self._result(
            table_name=table_name,
            rows=df.to_dict("records"),
            columns=list(df.columns),
            analysis=analysis,
            message="연락처/학과사무실 조회가 완료되었습니다.",
            warnings=warnings,
        )

    def _query_admissions(self, analysis: QueryAnalysis) -> SqlQueryResult:
        table_name = "admission"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            where_clause, params = self._dept_where_clause(analysis, alias="a")

            sql = f"""
            SELECT
                a.admission_id,
                a.record_id,
                a.dept,
                d.dept_name,
                a.admission_type,
                a.admission_type_norm,
                a.page_title,
                a.section_title,
                a.title,
                a.content,
                a.schedule_date,
                a.schedule_date_raw,
                a.min_gpa,
                a.source_url,
                a.crawled_at,
                a.source_sheet
            FROM admission AS a
            LEFT JOIN department AS d
              ON d.dept = a.dept
            WHERE {where_clause}
            ORDER BY FIELD(a.dept, 'aic', 'ai_systems', 'ax', 'fx'),
                     a.admission_type_norm,
                     a.schedule_date,
                     a.title
            LIMIT %s
            """

            final_params = tuple(params + [self._limit()])
            rows = self._fetch_all(conn, sql, final_params)

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="입학 정보 조회가 완료되었습니다.",
            query=sql,
            params=final_params,
        )

    def _query_events(self, analysis: QueryAnalysis) -> SqlQueryResult:
        table_name = "event"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            where_clause, params = self._dept_where_clause(analysis, alias="e")

            sql = f"""
            SELECT
                e.record_id,
                e.dept,
                d.dept_name,
                e.event_type,
                e.page_title,
                e.title,
                e.event_date,
                e.summary,
                e.content,
                e.source_url,
                e.crawled_at
            FROM event AS e
            LEFT JOIN department AS d
              ON d.dept = e.dept
            WHERE {where_clause}
            ORDER BY FIELD(e.dept, 'aic', 'ai_systems', 'ax', 'fx'),
                     e.event_date DESC,
                     e.title
            LIMIT %s
            """

            final_params = tuple(params + [self._limit()])
            rows = self._fetch_all(conn, sql, final_params)

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="행사/공지 조회가 완료되었습니다.",
            query=sql,
            params=final_params,
        )

    def _query_assets(self, analysis: QueryAnalysis) -> SqlQueryResult:
        table_name = "asset"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            where_clause, params = self._dept_where_clause(analysis, alias="a")

            sql = f"""
            SELECT
                a.asset_id,
                a.record_id,
                a.dept,
                d.dept_name,
                a.category,
                a.topic,
                a.priority,
                a.content_type,
                a.asset_type,
                a.text,
                a.url,
                a.filename,
                a.source_url,
                a.crawled_at,
                a.is_vector_candidate
            FROM asset AS a
            LEFT JOIN department AS d
              ON d.dept = a.dept
            WHERE {where_clause}
            ORDER BY FIELD(a.dept, 'aic', 'ai_systems', 'ax', 'fx'),
                     a.content_type,
                     a.topic
            LIMIT %s
            """

            final_params = tuple(params + [self._limit()])
            rows = self._fetch_all(conn, sql, final_params)

        return self._result(
            table_name="course",
            rows=df.to_dict("records"),
            columns=list(df.columns),
            analysis=analysis,
            message="웹 자산/링크 조회가 완료되었습니다.",
            query=sql,
            params=final_params,
        )

    def _query_departments(self, analysis: QueryAnalysis) -> SqlQueryResult:
        table_name = "department"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            sql = """
            SELECT
                dept,
                dept_name
            FROM department
            WHERE dept IN ('aic', 'ai_systems', 'ax', 'fx')
            ORDER BY FIELD(dept, 'aic', 'ai_systems', 'ax', 'fx')
            """
            rows = self._fetch_all(conn, sql)

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="학과 목록 조회가 완료되었습니다.",
            query=sql,
            params=(),
        )

    def _query_kaist_profile(self, analysis: QueryAnalysis) -> SqlQueryResult:
        table_name = "kaist_profile"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            sql = """
            SELECT
                item,
                content,
                note,
                source_url,
                source
            FROM kaist_profile
            LIMIT %s
            """
            params = (self._limit(),)
            rows = self._fetch_all(conn, sql, params)

        return self._result(
            table_name="office_contacts",
            rows=df.to_dict("records"),
            columns=list(df.columns),
            analysis=analysis,
            message="KAIST 기본 정보 조회가 완료되었습니다.",
            query=sql,
            params=params,
        )

    def _query_kaist_statistics(self, analysis: QueryAnalysis) -> SqlQueryResult:
        table_name = "kaist_statistics"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            sql = """
            SELECT
                stat_group,
                level,
                value_raw,
                value_number,
                note,
                source
            FROM kaist_statistics
            LIMIT %s
            """
            params = (self._limit(),)
            rows = self._fetch_all(conn, sql, params)

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="KAIST 통계 정보 조회가 완료되었습니다.",
            query=sql,
            params=params,
        )

    def _query_kaist_links(self, analysis: QueryAnalysis) -> SqlQueryResult:
        table_name = "kaist_links"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            sql = """
            SELECT
                link_name,
                url,
                note,
                source
            FROM kaist_links
            LIMIT %s
            """
            params = (self._limit(),)
            rows = self._fetch_all(conn, sql, params)

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="KAIST 공식 링크 조회가 완료되었습니다.",
            query=sql,
            params=params,
        )

    def _query_department_homepages(self, analysis: QueryAnalysis) -> SqlQueryResult:
        table_name = "department_homepage"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            dept_codes = self._target_dept_codes(analysis)

            if len(dept_codes) == 1:
                where_clause = "h.dept = %s"
                params = [dept_codes[0]]
            else:
                placeholders = ", ".join(["%s"] * len(dept_codes))
                where_clause = f"h.dept IN ({placeholders})"
                params = list(dept_codes)

            sql = f"""
            SELECT
                h.dept,
                h.dept_name,
                h.homepage_url,
                h.admission_url,
                h.faculty_url,
                h.curriculum_url,
                h.source
            FROM department_homepage AS h
            WHERE {where_clause}
            ORDER BY FIELD(h.dept, 'aic', 'ai_systems', 'ax', 'fx')
            LIMIT %s
            """

            final_params = tuple(params + [self._limit()])
            rows = self._fetch_all(conn, sql, final_params)

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="학과별 홈페이지 조회가 완료되었습니다.",
            query=sql,
            params=final_params,
        )

    def _query_requirements(self, analysis: QueryAnalysis) -> SqlQueryResult:
        table_name = "department_requirement"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            where_clause, params = self._dept_where_clause(analysis, alias="r")

            sql = f"""
            SELECT
                r.requirement_id,
                r.dept,
                r.dept_name,
                r.program,
                r.requirement_type,
                r.requirement_name,
                r.description,
                r.credits,
                r.source_url,
                r.note
            FROM department_requirement AS r
            WHERE {where_clause}
            ORDER BY FIELD(r.dept, 'aic', 'ai_systems', 'ax', 'fx'),
                     r.program,
                     r.requirement_type,
                     r.requirement_name
            LIMIT %s
            """

            final_params = tuple(params + [self._limit()])
            rows = self._fetch_all(conn, sql, final_params)

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="학과별 요건 조회가 완료되었습니다.",
            query=sql,
            params=final_params,
        )

    # ------------------------------------------------------------
    # utility
    # ------------------------------------------------------------

    def _dedupe_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()

        for row in rows:
            key = "|".join(
                str(row.get(k, ""))
                for k in [
                    "source_table",
                    "dept",
                    "dept_name",
                    "phone",
                    "website",
                    "email",
                    "office",
                    "source_url",
                    "contact_text",
                    "name",
                ]
            )

            if key in seen:
                continue

            seen.add(key)
            deduped.append(row)

        return deduped


# ============================================================
# 4. 수동 테스트
# ============================================================

if __name__ == "__main__":
    from src.rag.query_analyzer import QuestionAnalyzer

    analyzer = QuestionAnalyzer()
    tool = SQLTool()

    questions = [
        "AI대학 학과별 홈페이지 URL을 정리해줘.",
        "AI컴퓨팅학과 교수진을 알려줘.",
        "AI컴퓨팅학과의 교육과정을 알려줘.",
        "KAIST 대표 번호 알려줘.",
        "AI컴퓨팅학과의 졸업 요건이 문서에 나와 있어?",
        "AI컴퓨팅학과의 연락처가 문서에 나와 있어?",
    ]

    for question in questions:
        analysis = analyzer.analyze(question)
        result = tool.query(analysis)

        print("=" * 100)
        print("Q:", question)
        print("route:", analysis.route)
        print("intent:", analysis.intent)
        print("sql_task:", analysis.sql_task_hint)
        print("table:", result.table_name)
        print("rows:", len(result.rows))
        print("columns:", result.columns[:10])
        print("message:", result.message)
        print("warnings:", result.warnings)

        if result.rows:
            print("first_row:", result.rows[0])