import os
import glob
from .connection import get_db_connection, is_mock_mode


class DatabaseMigrator:
    def __init__(self, migrations_dir: str = None):
        if migrations_dir is None:
            migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
        self.migrations_dir = migrations_dir

    def run_migrations(self) -> list:
        applied = []
        if not os.path.exists(self.migrations_dir):
            return applied

        sql_files = sorted(glob.glob(os.path.join(self.migrations_dir, '*.sql')))
        if not sql_files:
            return applied

        conn = get_db_connection()

        try:
            with conn.cursor() as cur:
                # Ensure migration tracking table exists
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version VARCHAR(50) PRIMARY KEY,
                        description TEXT NOT NULL,
                        applied_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cur.execute("SELECT version FROM schema_migrations;")
                applied_rows = cur.fetchall()
                applied_versions = {row[0] for row in applied_rows}

                for filepath in sql_files:
                    filename = os.path.basename(filepath)
                    version = filename.split('_')[0]
                    if version in applied_versions:
                        continue

                    with open(filepath, 'r', encoding='utf-8') as f:
                        sql_content = f.read()

                    if is_mock_mode():
                        # SQLite wrapper executescript or statement loop
                        for stmt in sql_content.split(';'):
                            stmt_clean = stmt.strip()
                            if stmt_clean:
                                cur.execute(stmt_clean)
                    else:
                        cur.execute(sql_content)

                    cur.execute(
                        "INSERT INTO schema_migrations (version, description) VALUES (%s, %s);",
                        (version, filename)
                    )
                    applied.append(version)

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

        return applied


if __name__ == "__main__":
    migrator = DatabaseMigrator()
    res = migrator.run_migrations()
    print(f"Migrations executed: {res}")
