# sql functions
import datetime
import os

from dotenv import load_dotenv
import psycopg


def get_connection() -> object:
    return psycopg.connect(
        host=os.getenv("POSTGRES_ADDRESS"),
        dbname=os.getenv("DATABSE"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        options="-c search_path=step_of_faith",
    )


class PostgreSQL:
    def __init__(self) -> None:
        self.read = load_dotenv()

    def add_to_database(self, user_id: int, username: str) -> None:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users VALUES (%(user_id)s, %(username)s);
                """,
                {"user_id": user_id, "username": username},
            )
            cur.execute(
                """
                INSERT INTO seminar_enrollement VALUES 
                (NULL, %(user_id)s, 1),
                (NULL, %(user_id)s, 2);
                """,
                {"user_id": user_id},
            )
            conn.commit()

    def check_user_id(self, user_id: int) -> bool:
        with get_connection().cursor() as cur:
            data = cur.execute("SELECT id FROM users WHERE id = %s", (user_id,)).fetchone()
        return data is not None

    def get_schedule(self, day: int) -> list:
        with get_connection().cursor() as cur:
            return cur.execute("SELECT time, event FROM schedule WHERE day = %s", (day,)).fetchall()

    def get_counselors(self) -> list:
        with get_connection().cursor() as cur:
            return cur.execute(
                """
                    SELECT id, name 
                    FROM counselors
                    ORDER BY id;
                    """
            ).fetchall()

    def get_counselor_info(self, counselor_id: str) -> list:
        with get_connection().cursor() as cur:
            return cur.execute(
                """
                SELECT name, place FROM counselors
                WHERE id = %s;
                """,
                (counselor_id,),
            ).fetchone()

    def get_counselor_timeslots(self, counselor_id: str) -> list:
        with get_connection().cursor() as cur:
            return cur.execute(
                """
                SELECT time FROM counseling
                WHERE counselor_id = %s AND user_id IS NULL
                ORDER BY time;
                """,
                (counselor_id,),
            ).fetchall()

    def book_counseling(self, counselor_id: int, user_id: int, time: str) -> bool:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE counseling
                SET user_id = %s
                WHERE counselor_id = %s
                    AND user_id IS NULL
                    AND time = %s
                """,
                (user_id, counselor_id, time),
            )
            status = cur.rowcount != 0
            if status:
                cur.execute(
                    """
                    UPDATE counseling
                    SET user_id = NULL
                    WHERE NOT (counselor_id = %s AND time = %s)
                        AND user_id = %s
                    """,
                    (counselor_id, time, user_id),
                )
                conn.commit()
            else:
                conn.rollback()
        return status

    def get_my_counseling(self, user_id: int) -> list:
        with get_connection().cursor() as cur:
            return cur.execute(
                """
                    SELECT name, time, place
                    FROM counseling
                    JOIN counselors
                    ON counseling.counselor_id = counselors.id
                    WHERE user_id = %s
                    """,
                (user_id,),
            ).fetchone()

    def cancel_counseling(self, user_id: int) -> None:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE counseling
                SET user_id = NULL WHERE user_id = %s
                """,
                (user_id,),
            )
            conn.commit()

    def get_seminars(self, seminar_number: int) -> list:
        with get_connection().cursor() as cur:
            return cur.execute(
                """
                 WITH se as (select * from seminar_enrollement where seminar_number = %s),
                 seminar_counts AS (
                    SELECT 
                        s.id AS seminar_id, 
                        s.title, 
                        COUNT(se.user_id) AS number_of_people, 
                        rank() OVER (
                        ORDER BY 
                            COUNT(se.user_id) DESC
                        ) AS rn 
                    FROM 
                        seminars s 
                        LEFT JOIN seminar_enrollement se ON s.id = se.seminar_id 
                    GROUP BY 
                        s.id, 
                        s.title 
                    ORDER BY 
                        COUNT(se.user_id) DESC
                ), 
                room_capacities AS (
                    SELECT 
                        room, 
                        capacity, 
                        ROW_NUMBER() OVER (
                        ORDER BY 
                            capacity DESC
                        ) AS rn 
                    FROM 
                        spaces
                    WHERE seminar_number = %s
                ), 
                merged_seminars AS (
                    SELECT 
                        seminar_id, 
                        title 
                    FROM 
                        seminar_counts AS s 
                        JOIN room_capacities AS r ON s.rn = r.rn 
                    WHERE 
                        s.number_of_people < r.capacity
                ) 
                select 
                * 
                from 
                merged_seminars
                order by seminar_id
                """,
                (seminar_number, seminar_number),
            ).fetchall()

    def get_seminar_info(self, seminar_id: int) -> list:
        with get_connection().cursor() as cur:
            return cur.execute(
                """
                SELECT title, description, speaker
                FROM seminars
                WHERE id = %s;
                """,
                (seminar_id,),
            ).fetchone()

    def get_my_seminar(self, seminar_number: int, user_id: int) -> list:
        with get_connection().cursor() as cur:
            return cur.execute(
                """
                SELECT title, description, speaker
                FROM seminar_enrollement enrollement
                LEFT JOIN seminars
                    ON enrollement.seminar_id = seminars.id
                WHERE user_id = %s and seminar_number = %s
                ORDER BY seminar_number; 
                """,
                (user_id, seminar_number),
            ).fetchone()

    def get_seminar_start_time(self, seminar_number: int) -> datetime.time:
        with get_connection().cursor() as cur:
            data = cur.execute(
                """
                SELECT starts_at
                FROM seminar_numbers
                WHERE seminar_number = %s; 
                """,
                (seminar_number,),
            ).fetchone()
            if data is None:
                return None
            return data[0]

    def cancel_my_seminar(self, user_id: int, seminar_number: int) -> None:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE seminar_enrollement
                SET seminar_id = NULL
                WHERE user_id = %s and seminar_number = %s
                """,
                (user_id, seminar_number),
            )
            conn.commit()

    def enroll_for_seminar(self, seminar_number: int, user_id: int, seminar_id: int) -> bool:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                WITH se as (
                    select * from seminar_enrollement 
                    where seminar_number = %(seminar_number)s
                ),

                seminar_counts AS (
                    SELECT 
                        s.id AS seminar_id,
                        COUNT(se.user_id) AS number_of_people,
                        RANK() OVER (ORDER BY COUNT(se.user_id) DESC) AS rn
                    FROM 
                        seminars s
                    LEFT JOIN se 
                    ON s.id = se.seminar_id
                    WHERE se.seminar_number = %(seminar_number)s or se.seminar_number is null
                    GROUP BY s.id
                    ORDER BY COUNT(se.user_id) DESC
                ),
                room_capacities AS (
                    SELECT 
                        room,
                        capacity,
                        ROW_NUMBER() OVER (ORDER BY capacity DESC) AS rn
                    FROM spaces
                    WHERE seminar_number = %(seminar_number)s
                ),
                merged_seminars AS (
                    SELECT 
                        s.seminar_id
                    FROM seminar_counts AS s
                    JOIN room_capacities AS r ON s.rn = r.rn
                    WHERE s.seminar_id = %(seminar_id)s and s.number_of_people < r.capacity
                )
                UPDATE seminar_enrollement
                SET seminar_id = merged_seminars.seminar_id
                FROM merged_seminars
                WHERE user_id = %(user_id)s and seminar_number = %(seminar_number)s;
                """,
                {"seminar_number": seminar_number, "seminar_id": seminar_id, "user_id": user_id},
            )
            return cur.rowcount > 0
