"""SQL syntax highlighter with Catppuccin Mocha color palette."""

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)


class SQLHighlighter(QSyntaxHighlighter):
    """SQL syntax highlighter with keyword, string, number, and comment highlighting."""

    KEYWORDS = {
        "SELECT",
        "FROM",
        "WHERE",
        "JOIN",
        "LEFT",
        "RIGHT",
        "INNER",
        "OUTER",
        "FULL",
        "INSERT",
        "INTO",
        "VALUES",
        "UPDATE",
        "SET",
        "DELETE",
        "CREATE",
        "ALTER",
        "DROP",
        "TABLE",
        "INDEX",
        "VIEW",
        "DATABASE",
        "SCHEMA",
        "IF",
        "NOT",
        "EXISTS",
        "AND",
        "OR",
        "IN",
        "IS",
        "NULL",
        "AS",
        "ON",
        "ORDER",
        "BY",
        "GROUP",
        "HAVING",
        "LIMIT",
        "OFFSET",
        "UNION",
        "ALL",
        "INTERSECT",
        "EXCEPT",
        "EXISTS",
        "BETWEEN",
        "LIKE",
        "ILIKE",
        "CASE",
        "WHEN",
        "THEN",
        "ELSE",
        "END",
        "BEGIN",
        "COMMIT",
        "ROLLBACK",
        "TRANSACTION",
        "GRANT",
        "REVOKE",
        "PRIMARY",
        "FOREIGN",
        "KEY",
        "REFERENCES",
        "CONSTRAINT",
        "DEFAULT",
        "CASCADE",
        "RESTRICT",
        "UNIQUE",
        "CHECK",
        "DISTINCT",
        "ASC",
        "DESC",
        "NULLS",
        "FIRST",
        "LAST",
        "WITH",
        "RECURSIVE",
        "OVER",
        "PARTITION",
        "WINDOW",
        "ROWS",
        "RANGE",
        "PRECEDING",
        "FOLLOWING",
        "CURRENT",
        "ROW",
        "UNBOUNDED",
        "NATURAL",
        "CROSS",
        "USING",
        "NATURAL_JOIN",
        "RETURNING",
        "ON_CONFLICT",
        "DO",
        "NOTHING",
        "INSTEAD",
        "OF",
        "EACH",
        "ROW",
        "TRIGGER",
        "FUNCTION",
        "PROCEDURE",
        "RETURNS",
        "LANGUAGE",
        "PLPGSQL",
        "BODY",
    }

    DATA_TYPES = {
        "INT",
        "INTEGER",
        "SMALLINT",
        "BIGINT",
        "SERIAL",
        "BIGSERIAL",
        "FLOAT",
        "DOUBLE",
        "REAL",
        "DECIMAL",
        "NUMERIC",
        "PRECISION",
        "CHAR",
        "VARCHAR",
        "TEXT",
        "BOOLEAN",
        "DATE",
        "TIME",
        "TIMESTAMP",
        "TIMESTAMPTZ",
        "INTERVAL",
        "BLOB",
        "BYTEA",
        "JSON",
        "JSONB",
        "JSONPATH",
        "UUID",
        "ARRAY",
        "MONEY",
        "XML",
        "POINT",
        "LINE",
        "CIDR",
        "INET",
        "MACADDR",
        "BIT",
        "VARBIT",
        "OID",
        "REGCLASS",
        "REGTYPE",
        "VOID",
    }

    FUNCTIONS = {
        "COUNT",
        "SUM",
        "AVG",
        "MAX",
        "MIN",
        "COALESCE",
        "NULLIF",
        "GREATEST",
        "LEAST",
        "CONCAT",
        "CONCAT_WS",
        "SUBSTRING",
        "SUBSTR",
        "TRIM",
        "LTRIM",
        "RTRIM",
        "UPPER",
        "LOWER",
        "LENGTH",
        "CHAR_LENGTH",
        "OCTET_LENGTH",
        "BIT_LENGTH",
        "POSITION",
        "REPLACE",
        "OVERLAY",
        "FORMAT",
        "INITCAP",
        "LEFT",
        "RIGHT",
        "LPAD",
        "RPAD",
        "NOW",
        "CURRENT_TIMESTAMP",
        "CURRENT_DATE",
        "CURRENT_TIME",
        "LOCALTIME",
        "LOCALTIMESTAMP",
        "EXTRACT",
        "DATE_PART",
        "DATE_TRUNC",
        "AGE",
        "MAKE_DATE",
        "MAKE_TIME",
        "MAKE_TIMESTAMP",
        "TO_TIMESTAMP",
        "TO_DATE",
        "TO_CHAR",
        "TO_NUMBER",
        "CAST",
        "CONVERT",
        "ROUND",
        "FLOOR",
        "CEIL",
        "CEILING",
        "ABS",
        "MOD",
        "POWER",
        "SQRT",
        "RANDOM",
        "GENERATE_SERIES",
        "UNNEST",
        "ARRAY_LENGTH",
        "ARRAY_AGG",
        "STRING_AGG",
        "JSON_BUILD_OBJECT",
        "JSON_BUILD_ARRAY",
        "JSON_OBJECT_AGG",
        "JSON_ARRAY_LENGTH",
        "ROW_NUMBER",
        "RANK",
        "DENSE_RANK",
        "NTILE",
        "LAG",
        "LEAD",
        "FIRST_VALUE",
        "LAST_VALUE",
        "NTH_VALUE",
        "COVAR_POP",
        "COVAR_SAMP",
        "CORR",
        "STDDEV",
        "STDDEV_POP",
        "STDDEV_SAMP",
        "VARIANCE",
        "VAR_POP",
        "VAR_SAMP",
    }

    def __init__(self, parent: QTextDocument) -> None:
        super().__init__(parent)
        self._highlighting_rules: list[tuple[re.Pattern, QTextCharFormat]] = []
        self._setup_highlighting_rules()

    def _setup_highlighting_rules(self) -> None:
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#cba6f7"))
        keyword_format.setFontWeight(QFont.Weight.Bold)

        datatype_format = QTextCharFormat()
        datatype_format.setForeground(QColor("#f9e2af"))
        datatype_format.setFontWeight(QFont.Weight.Bold)

        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#89b4fa"))

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#a6e3a1"))

        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#fab387"))

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6c7086"))
        comment_format.setFontItalic(True)

        operator_format = QTextCharFormat()
        operator_format.setForeground(QColor("#89dceb"))

        keyword_pattern = (
            r"\b(" + "|".join(re.escape(k) for k in self.KEYWORDS) + r")\b"
        )
        self._highlighting_rules.append(
            (re.compile(keyword_pattern, re.IGNORECASE), keyword_format)
        )

        datatype_pattern = (
            r"\b(" + "|".join(re.escape(d) for d in self.DATA_TYPES) + r")\b"
        )
        self._highlighting_rules.append(
            (re.compile(datatype_pattern, re.IGNORECASE), datatype_format)
        )

        function_pattern = (
            r"\b(" + "|".join(re.escape(f) for f in self.FUNCTIONS) + r")\b(?=\s*\()"
        )
        self._highlighting_rules.append(
            (re.compile(function_pattern, re.IGNORECASE), function_format)
        )

        string_pattern = r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\""
        self._highlighting_rules.append((re.compile(string_pattern), string_format))

        number_pattern = r"\b-?\d+(\.\d+)?\b"
        self._highlighting_rules.append((re.compile(number_pattern), number_format))

        comment_pattern = r"--[^\n]*|/\*[\s\S]*?\*/"
        self._highlighting_rules.append((re.compile(comment_pattern), comment_format))

        operator_pattern = r"[=!<>]=?|&&|\|\||[+\-*/%<>=]"
        self._highlighting_rules.append((re.compile(operator_pattern), operator_format))

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self._highlighting_rules:
            iterator = pattern.finditer(text)
            for match in iterator:
                start = match.start()
                length = match.end() - match.start()
                self.setFormat(start, length, fmt)

        self.setCurrentBlockState(0)

        in_comment = self._highlight_block_comment(text)
        if not in_comment:
            pass

    def _highlight_block_comment(self, text: str) -> bool:
        if self.previousBlockState() == 1:
            start = 0
            end = text.find("*/")
            if end == -1:
                self.setFormat(0, len(text), self._comment_format())
                return True
            else:
                self.setFormat(0, end + 2, self._comment_format())
                self.setCurrentBlockState(0)
                return False

        start = text.find("/*")
        if start == -1:
            return False

        end = text.find("*/", start + 2)
        if end == -1:
            self.setFormat(start, len(text) - start, self._comment_format())
            self.setCurrentBlockState(1)
            return True
        else:
            self.setFormat(start, end + 2 - start, self._comment_format())
            return False

    def _comment_format(self) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#6c7086"))
        fmt.setFontItalic(True)
        return fmt
