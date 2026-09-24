#!/usr/bin/env python
"""Local CSV/Excel import script. Usage: python -m app.scripts.import_csv <file_path>"""

import sys
from sqlmodel import Session

from app.db.session import engine
from app.services.importer import import_from_file_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m app.scripts.import_csv <file_path>")
        sys.exit(1)

    file_path = sys.argv[1]
    with Session(engine) as session:
        result = import_from_file_path(session, file_path, created_by="script")
        print(f"Batch ID: {result.batch_id}")
        print(f"Total rows: {result.total}")
        print(f"OK: {result.ok}")
        print(f"Errors: {result.errors}")
        if result.error_rows:
            print("Error rows:")
            for err in result.error_rows:
                print(f"  Row {err.row}: SKU={err.sku} - {err.error}")


if __name__ == "__main__":
    main()