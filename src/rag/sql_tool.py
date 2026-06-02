from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "pymysql이 설치되어 있지 않습니다. 아래 명령어로 설치하세요.\n"
        "python -m pip install pymysql python-dotenv"
    ) from exc


CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.query_analyzer import QueryAnalysis
from src.rag.context_builder import SqlQueryResult


@dataclass
class SQLToolConfig:
    """
    MySQL 기반 SQLTool 설정입니다.

    .env 예시:
        KAIST_MYSQL_HOST=127.0.0.1
        KAIST_MYSQL_PORT=3306
        KAIST_MYSQL_USER=root
        KAIST_MYSQL_PASSWORD=비밀번호
        KAIST_MYSQL_DATABASE=kaist_ai
        KAIST_SQL_MAX_ROWS=100
    """

    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "kaist_ai"
    charset: str = "utf8mb4"
    max_rows: int = 100
    connect_timeout: int = 5

    @classmethod
    def from_env(cls) -> "SQLToolConfig":
        load_dotenv()

        return cls(
            host=os.getenv("KAIST_MYSQL_HOST", "127.0.0.1"),
            port=int(os.getenv("KAIST_MYSQL_PORT", "3306")),
            user=os.getenv("KAIST_MYSQL_USER", "root"),
            password=os.getenv("KAIST_MYSQL_PASSWORD", ""),
            database=os.getenv("KAIST_MYSQL_DATABASE", "kaist_ai"),
            charset="utf8mb4",
            max_rows=int(os.getenv("KAIST_SQL_MAX_ROWS", "100")),
            connect_timeout=int(os.getenv("KAIST_MYSQL_CONNECT_TIMEOUT", "5")),
        )

SUPPORTED_AI_COLLEGE_DEPT_CODES = ("aic", "ai_systems", "ax", "fx")

class SQLTool:
    """
    KAIST AI 대학원 RAG Agent용 MySQL 조회 도구입니다.

    역할:
    - QueryAnalysis.sql_task_hint에 따라 MySQL 테이블 조회
    - 조회 결과를 ContextBuilder가 받을 수 있는 SqlQueryResult 형태로 반환
    - RagPipeline에서 sql_retriever=SQLTool() 형태로 바로 연결 가능
    """

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

    # ============================================================
    # RagPipeline 연결용 인터페이스
    # ============================================================

    def search(self, analysis: QueryAnalysis) -> SqlQueryResult:
        return self.query(analysis)

    def __call__(self, analysis: QueryAnalysis) -> SqlQueryResult:
        return self.query(analysis)

    # ============================================================
    # Query router
    # ============================================================

    def query(self, analysis: QueryAnalysis) -> SqlQueryResult:
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

            return self._unsupported_task_result(analysis)

        except pymysql.err.OperationalError as error:
            return self._connection_error_result(analysis, error)

        except Exception as error:
            return SqlQueryResult(
                table_name=self._table_name_from_analysis(analysis),
                rows=[],
                columns=[],
                conditions=analysis.sql_conditions,
                message="SQL 조회 중 오류가 발생했습니다.",
                warnings=[f"{type(error).__name__}: {error}"],
            )

    # ============================================================
    # MySQL connection / metadata helpers
    # ============================================================

    def _connect(self):
        connection = pymysql.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            database=self.config.database,
            charset="utf8mb4",
            use_unicode=True,
            cursorclass=DictCursor,
            autocommit=True,
            connect_timeout=self.config.connect_timeout,
        )

        with connection.cursor() as cursor:
            cursor.execute("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci")
            cursor.execute("SET character_set_connection=utf8mb4")
            cursor.execute("SET character_set_client=utf8mb4")
            cursor.execute("SET character_set_results=utf8mb4")

        return connection

    def _table_exists(self, conn, table_name: str) -> bool:
        sql = """
        SELECT COUNT(*) AS table_count
        FROM information_schema.tables
        WHERE table_schema = %s
          AND table_name = %s
        """
        with conn.cursor() as cursor:
            cursor.execute(sql, (self.config.database, table_name))
            row = cursor.fetchone()

        return bool(row and int(row.get("table_count", 0)) > 0)

    def _columns(self, conn, table_name: str) -> set[str]:
        """
        MySQL information_schema의 컬럼명 key가 환경에 따라
        column_name / COLUMN_NAME 으로 들어올 수 있으므로 안전하게 처리합니다.
        """
        sql = """
        SELECT COLUMN_NAME AS column_name
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
        ORDER BY ORDINAL_POSITION
        """
        with conn.cursor() as cursor:
            cursor.execute(sql, (self.config.database, table_name))
            rows = cursor.fetchall()

        columns: set[str] = set()

        for row in rows:
            column_name = (
                row.get("column_name")
                or row.get("COLUMN_NAME")
                or row.get("Column_name")
            )

            if column_name:
                columns.add(str(column_name))

        return columns

    def _fetch_all(
        self,
        conn,
        sql: str,
        params: tuple[Any, ...],
    ) -> list[dict[str, Any]]:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def _limit(self) -> int:
        return max(1, int(self.config.max_rows))

    def _dept_condition(
        self,
        alias: str,
        dept: str | None,
        params: list[Any],
    ) -> str:
        if dept:
            params.append(dept)
            return f"{alias}.dept = %s"

        placeholders = ", ".join(["%s"] * len(SUPPORTED_AI_COLLEGE_DEPT_CODES))
        params.extend(SUPPORTED_AI_COLLEGE_DEPT_CODES)

        return f"{alias}.dept IN ({placeholders})"

    def _build_select_columns(
        self,
        alias: str,
        available_columns: set[str],
        preferred_columns: list[str],
    ) -> list[str]:
        select_columns = []

        for column in preferred_columns:
            if column in available_columns:
                select_columns.append(f"{alias}.{column}")

        if not select_columns:
            select_columns.append(f"{alias}.*")

        return select_columns

    def _build_order_clause(
        self,
        alias: str,
        available_columns: set[str],
        preferred_columns: list[str],
    ) -> str:
        order_columns = [
            f"{alias}.{column}"
            for column in preferred_columns
            if column in available_columns
        ]

        if not order_columns:
            return "1"

        return ", ".join(order_columns)

    # ============================================================
    # Query methods
    # ============================================================

    def _query_courses(self, analysis: QueryAnalysis) -> SqlQueryResult:
        table_name = "course"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            course_columns = self._columns(conn, table_name)
            has_department = self._table_exists(conn, "department")
            has_course_track = self._table_exists(conn, "course_track")
            has_track = self._table_exists(conn, "track")

            params: list[Any] = []
            where_clause = self._dept_condition("c", analysis.department_code, params)

            if has_department and has_course_track and has_track and "record_id" in course_columns:
                sql = f"""
                SELECT
                    c.record_id,
                    c.dept,
                    d.dept_name,
                    c.course_code,
                    c.course_name,
                    c.course_type,
                    c.credit,
                    GROUP_CONCAT(t.track_name ORDER BY t.track_name SEPARATOR ', ') AS track_names
                FROM course AS c
                LEFT JOIN department AS d
                    ON d.dept = c.dept
                LEFT JOIN course_track AS ct
                    ON ct.course_id = c.record_id
                LEFT JOIN track AS t
                    ON t.track_id = ct.track_id
                WHERE {where_clause}
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
                LIMIT %s
                """
            elif has_department and "dept" in course_columns:
                sql = f"""
                SELECT
                    c.*,
                    d.dept_name
                FROM course AS c
                LEFT JOIN department AS d
                    ON d.dept = c.dept
                WHERE {where_clause}
                ORDER BY
                    c.dept,
                    c.course_code,
                    c.course_name
                LIMIT %s
                """
            else:
                sql = f"""
                SELECT *
                FROM course AS c
                WHERE {where_clause}
                LIMIT %s
                """

            params.append(self._limit())
            rows = self._fetch_all(conn, sql, tuple(params))

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="교과목 조회가 완료되었습니다.",
        )

    def _query_people(self, analysis: QueryAnalysis) -> SqlQueryResult:
        table_name = "person"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            person_columns = self._columns(conn, table_name)
            has_department = self._table_exists(conn, "department")

            params: list[Any] = []
            where_clause = self._dept_condition("p", analysis.department_code, params)

            preferred_columns = [
                "record_id",
                "dept",
                "name",
                "role",
                "role_normalized",
                "email",
                "phone",
                "office",
                "homepage",
                "research_area",
            ]

            select_columns = self._build_select_columns(
                alias="p",
                available_columns=person_columns,
                preferred_columns=preferred_columns,
            )

            if has_department and "dept" in person_columns:
                select_clause = ",\n                    ".join(
                    [
                        *select_columns,
                        "d.dept_name",
                    ]
                )

                sql = f"""
                SELECT
                    {select_clause}
                FROM person AS p
                LEFT JOIN department AS d
                    ON d.dept = p.dept
                WHERE {where_clause}
                ORDER BY
                    p.dept,
                    p.role_normalized,
                    p.name
                LIMIT %s
                """
            else:
                select_clause = ",\n                    ".join(select_columns)

                sql = f"""
                SELECT
                    {select_clause}
                FROM person AS p
                WHERE {where_clause}
                LIMIT %s
                """

            params.append(self._limit())
            rows = self._fetch_all(conn, sql, tuple(params))

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="교수/구성원 조회가 완료되었습니다.",
        )

    def _query_office_contacts(self, analysis: QueryAnalysis) -> SqlQueryResult:
        """
        학과 사무실/연락처 질문 처리.

        asset 테이블의 contact_info, email, phone, office, location 성격 데이터와
        person 테이블의 email/phone/office 정보를 함께 조회합니다.
        """
        asset_table = "asset"
        person_table = "person"

        rows: list[dict[str, Any]] = []
        warnings: list[str] = []

        with self._connect() as conn:
            has_department = self._table_exists(conn, "department")
            has_asset = self._table_exists(conn, asset_table)
            has_person = self._table_exists(conn, person_table)

            if not has_asset and not has_person:
                return SqlQueryResult(
                    table_name="asset/person",
                    rows=[],
                    columns=[],
                    conditions=analysis.sql_conditions,
                    message="연락처 조회에 필요한 테이블을 찾을 수 없습니다.",
                    warnings=[
                        "asset 또는 person 테이블이 MySQL DB에 생성되어 있는지 확인하세요.",
                    ],
                )

            if has_asset:
                asset_columns = self._columns(conn, asset_table)
                params: list[Any] = []

                conditions = [self._dept_condition("a", analysis.department_code, params)]
                contact_conditions = []

                if "content_type" in asset_columns:
                    contact_conditions.append("a.content_type = 'contact_info'")

                if "asset_type" in asset_columns:
                    contact_conditions.append(
                        "("
                        "a.asset_type IN ('phone', 'email', 'contact', 'location', 'office') "
                        "OR a.asset_type LIKE '%%phone%%' "
                        "OR a.asset_type LIKE '%%email%%' "
                        "OR a.asset_type LIKE '%%contact%%' "
                        "OR a.asset_type LIKE '%%office%%' "
                        "OR a.asset_type LIKE '%%location%%'"
                        ")"
                    )

                if "topic" in asset_columns:
                    contact_conditions.append(
                        "("
                        "a.topic LIKE '%%Contact%%' "
                        "OR a.topic LIKE '%%연락%%' "
                        "OR a.topic LIKE '%%사무실%%' "
                        "OR a.topic LIKE '%%전화%%' "
                        ")"
                    )

                if "text" in asset_columns:
                    contact_conditions.append(
                        "("
                        "a.text LIKE '%%전화%%' "
                        "OR a.text LIKE '%%연락처%%' "
                        "OR a.text LIKE '%%사무실%%' "
                        "OR a.text LIKE '%%행정실%%' "
                        "OR a.text LIKE '%%위치%%' "
                        "OR a.text LIKE '%%office%%' "
                        "OR a.text LIKE '%%contact%%' "
                        "OR a.text LIKE '%%phone%%'"
                        ")"
                    )

                if contact_conditions:
                    conditions.append("(" + " OR ".join(contact_conditions) + ")")

                where_clause = " AND ".join(conditions)

                if has_department and "dept" in asset_columns:
                    sql = f"""
                    SELECT
                        'asset' AS result_source,
                        a.dept,
                        d.dept_name,
                        a.category,
                        a.topic,
                        a.content_type,
                        a.asset_type,
                        a.text AS contact_text,
                        a.url,
                        a.source_url
                    FROM asset AS a
                    LEFT JOIN department AS d
                        ON d.dept = a.dept
                    WHERE {where_clause}
                    ORDER BY
                        a.dept,
                        a.topic
                    LIMIT %s
                    """
                else:
                    sql = f"""
                    SELECT
                        'asset' AS result_source,
                        a.*
                    FROM asset AS a
                    WHERE {where_clause}
                    LIMIT %s
                    """

                params.append(self._limit())
                rows.extend(self._fetch_all(conn, sql, tuple(params)))

            if has_person and analysis.department_code and not rows:
                person_columns = self._columns(conn, person_table)
                params = []

                conditions = [self._dept_condition("p", analysis.department_code, params)]
                person_contact_conditions = []

                if "email" in person_columns:
                    person_contact_conditions.append("(p.email IS NOT NULL AND p.email <> '')")

                if "phone" in person_columns:
                    person_contact_conditions.append("(p.phone IS NOT NULL AND p.phone <> '')")

                if "office" in person_columns:
                    person_contact_conditions.append("(p.office IS NOT NULL AND p.office <> '')")

                if person_contact_conditions:
                    conditions.append("(" + " OR ".join(person_contact_conditions) + ")")
                else:
                    warnings.append(
                        "person 테이블에 email/phone/office 컬럼이 없어 person 연락처 조회를 제한했습니다."
                    )

                where_clause = " AND ".join(conditions)

                if has_department and "dept" in person_columns:
                    sql = f"""
                    SELECT
                        'person' AS result_source,
                        p.record_id,
                        p.dept,
                        d.dept_name,
                        p.name,
                        p.role,
                        p.role_normalized,
                        p.email,
                        p.phone,
                        p.office,
                        p.homepage
                    FROM person AS p
                    LEFT JOIN department AS d
                        ON d.dept = p.dept
                    WHERE {where_clause}
                    ORDER BY
                        p.dept,
                        p.name
                    LIMIT %s
                    """
                else:
                    sql = f"""
                    SELECT
                        'person' AS result_source,
                        p.*
                    FROM person AS p
                    WHERE {where_clause}
                    LIMIT %s
                    """

                params.append(self._limit())
                rows.extend(self._fetch_all(conn, sql, tuple(params)))

        return self._result(
            table_name="office_contacts",
            rows=rows[: self._limit()],
            analysis=analysis,
            message="학과 사무실/연락처 정보 조회가 완료되었습니다.",
            warnings=warnings,
        )

    def _query_admissions(self, analysis: QueryAnalysis) -> SqlQueryResult:
        table_name = "admission"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            admission_columns = self._columns(conn, table_name)
            has_department = self._table_exists(conn, "department")

            params: list[Any] = []
            where_clause = self._dept_condition("a", analysis.department_code, params)

            preferred_columns = [
                "record_id",
                "dept",
                "admission_type",
                "admission_type_norm",
                "title",
                "content",
                "schedule_date",
                "schedule_date_raw",
                "min_gpa",
                "source_url",
                "url",
                "missing_fields",
            ]

            select_columns = self._build_select_columns(
                alias="a",
                available_columns=admission_columns,
                preferred_columns=preferred_columns,
            )

            order_clause = self._build_order_clause(
                alias="a",
                available_columns=admission_columns,
                preferred_columns=["dept", "admission_type", "title"],
            )

            if has_department and "dept" in admission_columns:
                select_clause = ",\n                    ".join(
                    [
                        *select_columns,
                        "d.dept_name",
                    ]
                )

                sql = f"""
                SELECT
                    {select_clause}
                FROM admission AS a
                LEFT JOIN department AS d
                    ON d.dept = a.dept
                WHERE {where_clause}
                ORDER BY
                    {order_clause}
                LIMIT %s
                """
            else:
                select_clause = ",\n                    ".join(select_columns)

                sql = f"""
                SELECT
                    {select_clause}
                FROM admission AS a
                WHERE {where_clause}
                ORDER BY
                    {order_clause}
                LIMIT %s
                """

            params.append(self._limit())
            rows = self._fetch_all(conn, sql, tuple(params))

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="입학 정보 조회가 완료되었습니다.",
        )

    def _query_events(self, analysis: QueryAnalysis) -> SqlQueryResult:
        table_name = "event"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            event_columns = self._columns(conn, table_name)
            has_department = self._table_exists(conn, "department")

            params: list[Any] = []
            where_clause = self._dept_condition("e", analysis.department_code, params)

            preferred_columns = [
                "record_id",
                "dept",
                "event_type",
                "title",
                "event_date",
                "location",
                "content",
                "source_url",
                "url",
                "missing_fields",
            ]

            select_columns = self._build_select_columns(
                alias="e",
                available_columns=event_columns,
                preferred_columns=preferred_columns,
            )

            order_clause = self._build_order_clause(
                alias="e",
                available_columns=event_columns,
                preferred_columns=["event_date", "title"],
            )

            if has_department and "dept" in event_columns:
                select_clause = ",\n                    ".join(
                    [
                        *select_columns,
                        "d.dept_name",
                    ]
                )

                sql = f"""
                SELECT
                    {select_clause}
                FROM event AS e
                LEFT JOIN department AS d
                    ON d.dept = e.dept
                WHERE {where_clause}
                ORDER BY
                    {order_clause}
                LIMIT %s
                """
            else:
                select_clause = ",\n                    ".join(select_columns)

                sql = f"""
                SELECT
                    {select_clause}
                FROM event AS e
                WHERE {where_clause}
                ORDER BY
                    {order_clause}
                LIMIT %s
                """

            params.append(self._limit())
            rows = self._fetch_all(conn, sql, tuple(params))

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="행사 정보 조회가 완료되었습니다.",
        )

    def _query_assets(self, analysis: QueryAnalysis) -> SqlQueryResult:
        table_name = "asset"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            asset_columns = self._columns(conn, table_name)
            has_department = self._table_exists(conn, "department")

            params: list[Any] = []
            where_clause = self._dept_condition("a", analysis.department_code, params)

            order_clause = self._build_order_clause(
                alias="a",
                available_columns=asset_columns,
                preferred_columns=["dept", "asset_type", "topic"],
            )

            if has_department and "dept" in asset_columns:
                sql = f"""
                SELECT
                    a.*,
                    d.dept_name
                FROM asset AS a
                LEFT JOIN department AS d
                    ON d.dept = a.dept
                WHERE {where_clause}
                ORDER BY
                    {order_clause}
                LIMIT %s
                """
            else:
                sql = f"""
                SELECT *
                FROM asset AS a
                WHERE {where_clause}
                ORDER BY
                    {order_clause}
                LIMIT %s
                """

            params.append(self._limit())
            rows = self._fetch_all(conn, sql, tuple(params))

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="자료/링크 조회가 완료되었습니다.",
        )

    def _query_departments(self, analysis: QueryAnalysis) -> SqlQueryResult:
        table_name = "department"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            department_columns = self._columns(conn, table_name)

            params: list[Any] = []
            where_clause = self._dept_condition("d", analysis.department_code, params)

            order_clause = self._build_order_clause(
                alias="d",
                available_columns=department_columns,
                preferred_columns=["dept", "dept_name"],
            )

            sql = f"""
            SELECT *
            FROM department AS d
            WHERE {where_clause}
            ORDER BY
                {order_clause}
            LIMIT %s
            """

            params.append(self._limit())
            rows = self._fetch_all(conn, sql, tuple(params))

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="학과 정보 조회가 완료되었습니다.",
        )

    def _query_kaist_profile(self, analysis: QueryAnalysis) -> SqlQueryResult:
        table_name = "kaist_profile"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            rows = self._fetch_all(
                conn=conn,
                sql=f"""
                SELECT *
                FROM {table_name}
                LIMIT %s
                """,
                params=(self._limit(),),
            )

        rows = self._filter_rows_by_alias(
            rows=rows,
            key_column="item",
            question=analysis.normalized_question,
            aliases={
                "학교명": ["학교명", "이름", "한국과학기술원"],
                "영문약자": ["영문약자", "약자"],
                "영문명": ["영문명", "영어 이름", "영어명", "korea advanced"],
                "창립일": ["창립일", "설립일", "개교일", "언제 설립"],
                "색상": ["색상", "상징색", "컬러"],
                "주소": ["주소", "위치", "어디"],
                "대표 번호": ["대표 번호", "대표번호", "전화", "전화번호"],
                "대표 팩스번호": ["팩스", "팩스번호"],
                "설립이념": ["설립이념", "이념", "역사", "설립 배경"],
            },
        )

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="KAIST 기본 정보 조회가 완료되었습니다.",
        )

    def _query_kaist_statistics(self, analysis: QueryAnalysis) -> SqlQueryResult:
        table_name = "kaist_statistics"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            rows = self._fetch_all(
                conn=conn,
                sql=f"""
                SELECT *
                FROM {table_name}
                LIMIT %s
                """,
                params=(self._limit(),),
            )

        rows = self._filter_kaist_statistics_rows(
            rows=rows,
            question=analysis.normalized_question,
        )

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="KAIST 통계 정보 조회가 완료되었습니다.",
        )

    def _query_kaist_links(self, analysis: QueryAnalysis) -> SqlQueryResult:
        table_name = "kaist_links"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            rows = self._fetch_all(
                conn=conn,
                sql=f"""
                SELECT *
                FROM {table_name}
                LIMIT %s
                """,
                params=(self._limit(),),
            )

        rows = self._filter_rows_by_alias(
            rows=rows,
            key_column="link_name",
            question=analysis.normalized_question,
            aliases={
                "URL": ["공식 홈페이지", "홈페이지", "url", "웹사이트"],
                "캠퍼스맵": ["캠퍼스맵", "캠퍼스 맵", "지도"],
                "셔틀버스 실시간 위치 확인": ["셔틀버스", "셔틀", "버스"],
                "도서관": ["도서관", "library"],
                "문화행사": ["문화행사", "행사"],
                "홍보동영상(2분, 2025)": ["홍보동영상", "동영상", "영상"],
                "학사일정": ["학사일정", "일정", "캘린더"],
            },
        )

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="KAIST 공식 링크 조회가 완료되었습니다.",
        )

    def _filter_rows_by_alias(
        self,
        rows: list[dict[str, Any]],
        key_column: str,
        question: str,
        aliases: dict[str, list[str]],
    ) -> list[dict[str, Any]]:
        matched_keys = [
            key
            for key, keywords in aliases.items()
            if any(keyword.lower() in question.lower() for keyword in keywords)
        ]

        if not matched_keys:
            return rows

        return [
            row
            for row in rows
            if str(row.get(key_column, "")) in matched_keys
        ]

    def _filter_kaist_statistics_rows(
        self,
        rows: list[dict[str, Any]],
        question: str,
    ) -> list[dict[str, Any]]:
        group_aliases = {
            "졸업생": ["졸업생", "졸업자", "동문"],
            "재학생": ["재학생", "학생 수", "학생수", "재학"],
            "교직원": ["교직원", "교수", "직원"],
        }
        level_aliases = {
            "전체": ["전체", "총", "모두"],
            "학사": ["학사", "학부"],
            "석사": ["석사"],
            "석박통합": ["석박통합", "석박사통합"],
            "박사": ["박사"],
            "교수": ["교수"],
            "직원": ["직원"],
        }

        groups = self._matched_alias_keys(question, group_aliases)
        levels = self._matched_alias_keys(question, level_aliases)
        filtered_rows = rows

        if groups:
            filtered_rows = [
                row
                for row in filtered_rows
                if str(row.get("stat_group", "")) in groups
            ]

        if levels:
            filtered_rows = [
                row
                for row in filtered_rows
                if str(row.get("level", "")) in levels
            ]

        if not filtered_rows and groups:
            filtered_rows = [
                row
                for row in rows
                if str(row.get("stat_group", "")) in groups
            ]

        return filtered_rows

    def _matched_alias_keys(
        self,
        question: str,
        aliases: dict[str, list[str]],
    ) -> list[str]:
        normalized_question = "".join(question.lower().split())

        return [
            key
            for key, keywords in aliases.items()
            if any(
                keyword.lower() in question.lower()
                or "".join(keyword.lower().split()) in normalized_question
                for keyword in keywords
            )
        ]

    def _query_department_homepages(self, analysis: QueryAnalysis) -> SqlQueryResult:
        """
        학과별 대표 홈페이지 URL 조회.

        사용 예:
        - AI대학 학과별 홈페이지 URL을 정리해줘.
        - AI컴퓨팅학과 홈페이지 알려줘.
        - AX학과 사이트 알려줘.
        """
        table_name = "department_homepage"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            params: list[Any] = []

            if analysis.department_code:
                where_clause = "h.dept = %s"
                params.append(analysis.department_code)
            else:
                placeholders = ", ".join(["%s"] * len(SUPPORTED_AI_COLLEGE_DEPT_CODES))
                where_clause = f"h.dept IN ({placeholders})"
                params.extend(SUPPORTED_AI_COLLEGE_DEPT_CODES)

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

            params.append(self._limit())
            rows = self._fetch_all(conn, sql, tuple(params))

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="학과별 홈페이지 조회가 완료되었습니다.",
        )

    def _query_requirements(self, analysis: QueryAnalysis) -> SqlQueryResult:
        """
        학과별 졸업/수료/논문/이수 요건 조회.

        현재 데이터가 비어 있을 수 있다.
        이 경우 빈 결과를 반환하고, answer_generator에서
        '제공된 자료에서 확인할 수 없습니다'로 답변하게 한다.
        """
        table_name = "department_requirement"

        with self._connect() as conn:
            if not self._table_exists(conn, table_name):
                return self._missing_table_result(table_name, analysis)

            params: list[Any] = []

            if analysis.department_code:
                where_clause = "r.dept = %s"
                params.append(analysis.department_code)
            else:
                placeholders = ", ".join(["%s"] * len(SUPPORTED_AI_COLLEGE_DEPT_CODES))
                where_clause = f"r.dept IN ({placeholders})"
                params.extend(SUPPORTED_AI_COLLEGE_DEPT_CODES)

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
            ORDER BY
                FIELD(r.dept, 'aic', 'ai_systems', 'ax', 'fx'),
                r.program,
                r.requirement_type,
                r.requirement_name
            LIMIT %s
            """

            params.append(self._limit())
            rows = self._fetch_all(conn, sql, tuple(params))

        return self._result(
            table_name=table_name,
            rows=rows,
            analysis=analysis,
            message="학과별 요건 조회가 완료되었습니다.",
        )

    # ============================================================
    # Result helpers
    # ============================================================

    def _result(
        self,
        table_name: str,
        rows: list[dict[str, Any]],
        analysis: QueryAnalysis,
        message: str,
        warnings: list[str] | None = None,
    ) -> SqlQueryResult:
        columns = list(rows[0].keys()) if rows else []
        final_warnings = list(warnings or [])

        if not rows and analysis.department_code:
            final_warnings.append(
                f"{table_name} 테이블에서 dept='{analysis.department_code}' 조건에 맞는 행이 없습니다."
            )

        return SqlQueryResult(
            table_name=table_name,
            rows=rows,
            columns=columns,
            conditions=analysis.sql_conditions,
            message=message,
            warnings=final_warnings,
        )

    def _connection_error_result(
        self,
        analysis: QueryAnalysis,
        error: Exception,
    ) -> SqlQueryResult:
        return SqlQueryResult(
            table_name=self._table_name_from_analysis(analysis),
            rows=[],
            columns=[],
            conditions=analysis.sql_conditions,
            message="MySQL 연결 또는 조회 중 오류가 발생했습니다.",
            warnings=[
                f"{type(error).__name__}: {error}",
                f"host={self.config.host}",
                f"port={self.config.port}",
                f"user={self.config.user}",
                f"database={self.config.database}",
                "MySQL 서버 실행 여부, .env 접속 정보, DB 생성 여부를 확인하세요.",
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
            message=f"MySQL 테이블을 찾을 수 없습니다: {table_name}",
            warnings=[
                f"`{self.config.database}` 데이터베이스에 `{table_name}` 테이블이 생성되어 있는지 확인하세요.",
                "01_schema.sql 실행 여부를 확인하세요.",
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
