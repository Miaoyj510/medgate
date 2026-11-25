"""目录层：导入、校验与查询（增量 1.2 覆盖导入与校验）。"""

from .importer import ImportReport, RowIssue, import_aliases, import_catalog, read_rows

__all__ = ["ImportReport", "RowIssue", "import_aliases", "import_catalog", "read_rows"]
