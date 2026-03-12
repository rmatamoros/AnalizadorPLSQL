"""
PL/SQL Analysis Tools.

Each function is a static analysis tool that checks a specific aspect of PL/SQL code.
These tools are registered with the Anthropic beta tool runner.
"""

import re
from anthropic import beta_tool
from .standards import RULE_SEVERITY


def _find_line_number(code: str, pattern: str, flags: int = re.IGNORECASE) -> list[int]:
    """Return line numbers where pattern matches."""
    lines = code.split("\n")
    results = []
    for i, line in enumerate(lines, 1):
        if re.search(pattern, line, flags):
            results.append(i)
    return results


def _extract_blocks(code: str) -> dict:
    """Extract procedure, function, and package blocks with their starting line numbers."""
    blocks = {"procedures": [], "functions": [], "packages": []}

    lines = code.split("\n")
    # Find PROCEDURE declarations
    for i, line in enumerate(lines, 1):
        stripped = line.strip().upper()
        if re.match(r"(CREATE\s+(OR\s+REPLACE\s+)?)?PROCEDURE\s+", stripped):
            name_match = re.search(r"PROCEDURE\s+(\w+)", line, re.IGNORECASE)
            if name_match:
                blocks["procedures"].append((name_match.group(1), i))
        elif re.match(r"(CREATE\s+(OR\s+REPLACE\s+)?)?FUNCTION\s+", stripped):
            name_match = re.search(r"FUNCTION\s+(\w+)", line, re.IGNORECASE)
            if name_match:
                blocks["functions"].append((name_match.group(1), i))
        elif re.match(r"(CREATE\s+(OR\s+REPLACE\s+)?)?PACKAGE\s+", stripped):
            name_match = re.search(r"PACKAGE\s+(?:BODY\s+)?(\w+)", line, re.IGNORECASE)
            if name_match:
                blocks["packages"].append((name_match.group(1), i))

    return blocks


@beta_tool
def check_naming_conventions(code: str) -> str:
    """
    Analyze PL/SQL code for naming convention violations.

    Checks that variables use vPascalCase format (e.g., vCodEmpresa, vFecha),
    parameters use pPascalCase format (e.g., pCodEmpresa, pCentroD, pFecha),
    constants use c_/gc_ prefix, cursors use cur_ prefix, and exceptions
    use e_/ex_ prefix.

    Args:
        code: The PL/SQL source code to analyze.
    """
    violations = []

    lines = code.split("\n")

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        upper = stripped.upper()

        # Skip comments
        if stripped.startswith("--") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        # Check variable declarations (look for := or the IS/AS declaration section)
        # Variables declared without proper prefix
        var_match = re.match(
            r"(\w+)\s+(?:VARCHAR2|NUMBER|DATE|BOOLEAN|INTEGER|PLS_INTEGER|BINARY_INTEGER|CLOB|BLOB|CHAR)\s*[\(;]",
            stripped,
            re.IGNORECASE,
        )
        if var_match:
            var_name = var_match.group(1).lower()
            reserved = {
                "in", "out", "return", "is", "as", "begin", "end", "if", "then",
                "else", "elsif", "loop", "while", "for", "cursor", "procedure",
                "function", "package", "type", "subtype", "pragma",
            }
            if var_name not in reserved and not re.match(r"^v[A-Z]", var_match.group(1)):
                violations.append({
                    "line": i,
                    "severity": RULE_SEVERITY["variables"],
                    "rule": "naming_conventions.variables",
                    "message": f"Variable '{var_match.group(1)}' should use vPascalCase format (e.g., vCodEmpresa, vFecha, vCentroD)",
                    "code_snippet": stripped[:80],
                })

        # Check parameter declarations (PROCEDURE/FUNCTION signature lines)
        param_match = re.match(
            r"(\w+)\s+(?:IN\s+OUT|IN|OUT)\s+(?:NOCOPY\s+)?\w+",
            stripped,
            re.IGNORECASE,
        )
        if param_match:
            param_name = param_match.group(1)
            reserved = {"return", "is", "as", "procedure", "function"}
            if param_name.lower() not in reserved and not re.match(r"^p[A-Z]", param_name):
                violations.append({
                    "line": i,
                    "severity": RULE_SEVERITY["parameters"],
                    "rule": "naming_conventions.parameters",
                    "message": f"Parameter '{param_name}' should use pPascalCase format (e.g., pCodEmpresa, pCentroD, pFecha)",
                    "code_snippet": stripped[:80],
                })

        # Check cursor declarations
        cur_match = re.match(r"CURSOR\s+(\w+)", stripped, re.IGNORECASE)
        if cur_match:
            cur_name = cur_match.group(1).lower()
            if not re.match(r"^(cur_|c_)", cur_name):
                violations.append({
                    "line": i,
                    "severity": RULE_SEVERITY["cursors"],
                    "rule": "naming_conventions.cursors",
                    "message": f"Cursor '{cur_match.group(1)}' should use prefix cur_ or c_",
                    "code_snippet": stripped[:80],
                })

        # Check exception declarations
        exc_match = re.match(r"(\w+)\s+EXCEPTION\s*;", stripped, re.IGNORECASE)
        if exc_match:
            exc_name = exc_match.group(1).lower()
            if not re.match(r"^(e_|ex_)", exc_name):
                violations.append({
                    "line": i,
                    "severity": RULE_SEVERITY["exceptions"],
                    "rule": "naming_conventions.exceptions",
                    "message": f"Exception '{exc_match.group(1)}' should use prefix e_ or ex_",
                    "code_snippet": stripped[:80],
                })

        # Check constant declarations
        const_match = re.match(r"(\w+)\s+CONSTANT\s+", stripped, re.IGNORECASE)
        if const_match:
            const_name = const_match.group(1).lower()
            if not re.match(r"^(c_|gc_|g_c_)", const_name):
                violations.append({
                    "line": i,
                    "severity": RULE_SEVERITY["constants"],
                    "rule": "naming_conventions.constants",
                    "message": f"Constant '{const_match.group(1)}' should use prefix c_ or gc_",
                    "code_snippet": stripped[:80],
                })

    if not violations:
        return "PASS: No naming convention violations found."

    result = f"VIOLATIONS FOUND: {len(violations)} naming convention issue(s):\n\n"
    for v in violations:
        result += f"  [{v['severity']}] Line {v['line']}: {v['message']}\n"
        result += f"    Code: {v['code_snippet']}\n\n"
    return result


@beta_tool
def check_error_handling(code: str) -> str:
    """
    Analyze PL/SQL code for error handling compliance.

    Checks for missing EXCEPTION blocks, silent exception swallowing
    (WHEN OTHERS THEN NULL), missing error logging, and improper
    exception handling patterns.

    Args:
        code: The PL/SQL source code to analyze.
    """
    violations = []
    blocks = _extract_blocks(code)

    # Normalize code for analysis
    code_upper = code.upper()

    # Check for WHEN OTHERS THEN NULL (silent exception swallow)
    when_others_null = re.finditer(
        r"WHEN\s+OTHERS\s+THEN\s*\n?\s*(NULL\s*;|--[^\n]*\n\s*NULL\s*;)",
        code_upper,
    )
    for match in when_others_null:
        line_num = code[:match.start()].count("\n") + 1
        violations.append({
            "line": line_num,
            "severity": RULE_SEVERITY["no_silent_exceptions"],
            "rule": "error_handling.no_silent_exceptions",
            "message": "Silent exception handler found: WHEN OTHERS THEN NULL — exceptions must be logged or re-raised",
        })

    # Check for WHEN OTHERS without RAISE or logging
    when_others_matches = list(re.finditer(r"WHEN\s+OTHERS\s+THEN", code_upper))
    for match in when_others_matches:
        # Get the handler body (next ~5 lines)
        start = match.end()
        end = min(start + 500, len(code_upper))
        handler_body = code_upper[start:end]

        # Check if handler re-raises or logs
        has_raise = bool(re.search(r"\bRAISE\b|\bRAISE_APPLICATION_ERROR\b", handler_body[:200]))
        has_logging = bool(re.search(
            r"\bSQLERRM\b|\bSQLCODE\b|\bLOG\b|\bDBMS_OUTPUT\b|\bINSERT\b",
            handler_body[:300],
        ))

        # Find where this handler ends (next WHEN or END)
        next_boundary = re.search(r"\bWHEN\b|\bEND\b", handler_body)
        if next_boundary:
            handler_body = handler_body[:next_boundary.start()]

        is_null_handler = bool(re.match(r"\s*NULL\s*;", handler_body))

        if not has_raise and not has_logging and not is_null_handler:
            line_num = code[:match.start()].count("\n") + 1
            violations.append({
                "line": line_num,
                "severity": "MEDIUM",
                "rule": "error_handling.error_logging",
                "message": "WHEN OTHERS handler does not appear to log the error (SQLERRM/SQLCODE) or re-raise",
            })

    # Check procedures/functions for missing EXCEPTION blocks
    all_blocks = blocks["procedures"] + blocks["functions"]
    for block_name, block_line in all_blocks:
        # Find the block in code (case-insensitive search around the declared line)
        lines = code.split("\n")
        block_start = block_line - 1
        block_end = len(lines)

        # Find the END for this block
        depth = 0
        found_begin = False
        found_exception = False
        block_code = []

        for j in range(block_start, min(block_start + 500, len(lines))):
            line_upper = lines[j].strip().upper()
            block_code.append(line_upper)

            if re.search(r"\bBEGIN\b", line_upper) and not line_upper.startswith("--"):
                found_begin = True
                depth += 1
            if re.search(r"\bEXCEPTION\b", line_upper) and not line_upper.startswith("--"):
                found_exception = True
            if found_begin and re.search(r"\bEND\b", line_upper) and not line_upper.startswith("--"):
                depth -= 1
                if depth <= 0:
                    block_end = j
                    break

        if found_begin and not found_exception:
            violations.append({
                "line": block_line,
                "severity": RULE_SEVERITY["exception_block"],
                "rule": "error_handling.exception_block",
                "message": f"Procedure/Function '{block_name}' (line {block_line}) is missing an EXCEPTION block",
            })

    if not violations:
        return "PASS: No error handling violations found."

    result = f"VIOLATIONS FOUND: {len(violations)} error handling issue(s):\n\n"
    for v in violations:
        result += f"  [{v['severity']}] Line {v['line']}: {v['message']}\n\n"
    return result


@beta_tool
def check_documentation(code: str) -> str:
    """
    Analyze PL/SQL code for documentation and comment standards.

    Checks that procedures, functions, and packages have proper header
    comments with Author, Date, Description, Parameters, and Returns sections.

    Args:
        code: The PL/SQL source code to analyze.
    """
    violations = []
    blocks = _extract_blocks(code)
    lines = code.split("\n")

    all_blocks = (
        [("PROCEDURE", name, line) for name, line in blocks["procedures"]] +
        [("FUNCTION", name, line) for name, line in blocks["functions"]] +
        [("PACKAGE", name, line) for name, line in blocks["packages"]]
    )

    for block_type, block_name, block_line in all_blocks:
        # Check the 20 lines before the declaration for a header comment
        start = max(0, block_line - 20)
        end = block_line
        context_lines = lines[start:end]
        context = "\n".join(context_lines).upper()

        has_header_comment = "--" in context or "/*" in context
        has_author = bool(re.search(r"\bAUTHOR\b|\bAUTOR\b|\bCREADO\s*POR\b", context))
        has_date = bool(re.search(r"\bDATE\b|\bFECHA\b|\bCREATED\b|\bCREADO\b", context))
        has_description = bool(re.search(
            r"\bDESCRIPTION\b|\bDESCRIPCION\b|\bPURPOSE\b|\bOBJETO\b|\bOBJETIVO\b",
            context,
        ))
        has_params = bool(re.search(r"\bPARAM|\bPARAMETER\b", context))

        missing = []
        if not has_header_comment:
            missing.append("header comment block")
        else:
            if not has_author:
                missing.append("Author")
            if not has_date:
                missing.append("Date/Fecha")
            if not has_description:
                missing.append("Description/Descripcion")
            if block_type in ("PROCEDURE", "FUNCTION") and not has_params:
                missing.append("Parameters documentation")

        if missing:
            violations.append({
                "line": block_line,
                "severity": RULE_SEVERITY["header"],
                "rule": "documentation.header",
                "message": (
                    f"{block_type} '{block_name}' (line {block_line}) "
                    f"is missing: {', '.join(missing)}"
                ),
            })

    if not violations:
        return "PASS: Documentation standards are met."

    result = f"VIOLATIONS FOUND: {len(violations)} documentation issue(s):\n\n"
    for v in violations:
        result += f"  [{v['severity']}] Line {v['line']}: {v['message']}\n\n"
    return result


@beta_tool
def check_code_quality(code: str) -> str:
    """
    Analyze PL/SQL code for general code quality issues.

    Checks for SELECT *, missing type anchoring (%TYPE/%ROWTYPE),
    magic numbers/strings, line length violations, and other
    code quality issues.

    Args:
        code: The PL/SQL source code to analyze.
    """
    violations = []
    lines = code.split("\n")

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        upper = stripped.upper()

        # Skip comments
        if stripped.startswith("--"):
            continue

        # Check for SELECT *
        if re.search(r"\bSELECT\s+\*\b", upper):
            violations.append({
                "line": i,
                "severity": RULE_SEVERITY["no_select_star"],
                "rule": "code_quality.no_select_star",
                "message": "SELECT * found — list columns explicitly for maintainability and performance",
                "code_snippet": stripped[:100],
            })

        # Check line length
        if len(line.rstrip()) > 120:
            violations.append({
                "line": i,
                "severity": RULE_SEVERITY["line_length"],
                "rule": "code_quality.line_length",
                "message": f"Line exceeds 120 characters ({len(line.rstrip())} chars)",
                "code_snippet": line[:80] + "...",
            })

        # Check for hardcoded magic numbers in assignments and conditions
        # Exclude 0, 1, -1 which are commonly acceptable
        magic_num = re.search(
            r"(?<!['\"])\b([2-9]\d{2,}|\d{4,})\b(?!['\"])",
            stripped,
        )
        if magic_num and not re.search(r"CONSTANT|--", stripped, re.IGNORECASE):
            violations.append({
                "line": i,
                "severity": RULE_SEVERITY["no_magic_numbers"],
                "rule": "code_quality.no_magic_numbers",
                "message": f"Magic number '{magic_num.group(1)}' found — consider using a named constant",
                "code_snippet": stripped[:80],
            })

    # Check for variable declarations without %TYPE or %ROWTYPE
    # (looking for hardcoded type declarations)
    type_check_matches = re.finditer(
        r"^\s*(\w+)\s+(VARCHAR2\s*\(\s*\d+\s*\)|NUMBER\s*\(\s*\d+[,\s\d]*\))\s*;",
        code,
        re.IGNORECASE | re.MULTILINE,
    )
    for match in type_check_matches:
        var_name = match.group(1).lower()
        reserved = {"return", "is", "as", "in", "out"}
        if var_name not in reserved:
            line_num = code[:match.start()].count("\n") + 1
            violations.append({
                "line": line_num,
                "severity": RULE_SEVERITY["use_type_anchoring"],
                "rule": "code_quality.use_type_anchoring",
                "message": (
                    f"Variable '{match.group(1)}' uses hardcoded type '{match.group(2)}' — "
                    f"consider using %TYPE or %ROWTYPE for maintainability"
                ),
                "code_snippet": match.group(0).strip()[:80],
            })

    if not violations:
        return "PASS: No code quality violations found."

    result = f"VIOLATIONS FOUND: {len(violations)} code quality issue(s):\n\n"
    for v in violations:
        result += f"  [{v['severity']}] Line {v['line']}: {v['message']}\n"
        if "code_snippet" in v:
            result += f"    Code: {v['code_snippet']}\n"
        result += "\n"
    return result


@beta_tool
def check_performance(code: str) -> str:
    """
    Analyze PL/SQL code for performance anti-patterns.

    Checks for row-by-row processing that should use BULK COLLECT/FORALL,
    missing LIMIT clause on BULK COLLECT, COMMIT inside loops, and other
    performance issues.

    Args:
        code: The PL/SQL source code to analyze.
    """
    violations = []
    code_upper = code.upper()
    lines = code.split("\n")

    # Check for COMMIT inside loops
    loop_depth = 0
    in_loop = False
    loop_start_lines = []

    for i, line in enumerate(lines, 1):
        upper = line.strip().upper()
        if upper.startswith("--"):
            continue

        # Track loop entry/exit
        if re.search(r"\bLOOP\b", upper) and not re.search(r"END\s+LOOP", upper):
            loop_depth += 1
            loop_start_lines.append(i)
        if re.search(r"END\s+LOOP", upper):
            loop_depth = max(0, loop_depth - 1)
            if loop_start_lines:
                loop_start_lines.pop()

        # COMMIT inside loop
        if loop_depth > 0 and re.search(r"\bCOMMIT\b", upper) and not upper.startswith("--"):
            violations.append({
                "line": i,
                "severity": RULE_SEVERITY["no_commit_in_loops"],
                "rule": "performance.no_commit_in_loops",
                "message": "COMMIT found inside a loop — this causes performance issues and can leave data in inconsistent state",
                "code_snippet": line.strip()[:80],
            })

    # Check for BULK COLLECT without LIMIT
    bulk_collect_matches = re.finditer(r"BULK\s+COLLECT\s+INTO\s+\w+", code_upper)
    for match in bulk_collect_matches:
        # Check if LIMIT appears nearby (within 10 chars after the INTO var)
        context = code_upper[match.start():match.start() + 200]
        if "LIMIT" not in context:
            line_num = code[:match.start()].count("\n") + 1
            violations.append({
                "line": line_num,
                "severity": RULE_SEVERITY["limit_bulk_collect"],
                "rule": "performance.limit_bulk_collect",
                "message": "BULK COLLECT without LIMIT clause — could consume excessive memory for large result sets",
                "code_snippet": code[match.start():match.start() + 60].strip(),
            })

    # Check for row-by-row processing pattern (FETCH inside loop without BULK COLLECT)
    fetch_in_loop = re.finditer(r"FETCH\s+\w+\s+INTO", code_upper)
    for match in fetch_in_loop:
        line_num = code[:match.start()].count("\n") + 1
        # Check if it's inside a loop by examining surrounding context
        surrounding = code_upper[max(0, match.start() - 300):match.start()]
        if re.search(r"\bLOOP\b", surrounding) and "BULK" not in code_upper[match.start() - 50:match.start()]:
            violations.append({
                "line": line_num,
                "severity": RULE_SEVERITY["bulk_operations"],
                "rule": "performance.bulk_operations",
                "message": "Row-by-row FETCH inside loop detected — consider BULK COLLECT + FORALL for better performance",
                "code_snippet": code[match.start():match.start() + 60].strip(),
            })

    if not violations:
        return "PASS: No performance anti-patterns found."

    result = f"VIOLATIONS FOUND: {len(violations)} performance issue(s):\n\n"
    for v in violations:
        result += f"  [{v['severity']}] Line {v['line']}: {v['message']}\n"
        if "code_snippet" in v:
            result += f"    Code: {v['code_snippet']}\n"
        result += "\n"
    return result


@beta_tool
def check_security(code: str) -> str:
    """
    Analyze PL/SQL code for security vulnerabilities.

    Checks for SQL injection risks in dynamic SQL (string concatenation
    instead of bind variables), and identifies patterns that could
    expose sensitive data.

    Args:
        code: The PL/SQL source code to analyze.
    """
    violations = []
    code_upper = code.upper()
    lines = code.split("\n")

    # Check for dynamic SQL with string concatenation (SQL injection risk)
    # Patterns: EXECUTE IMMEDIATE with || concatenation
    dynamic_sql_matches = re.finditer(
        r"EXECUTE\s+IMMEDIATE\s+['\"].*?\|\||EXECUTE\s+IMMEDIATE\s+\w+\s*\|\|",
        code_upper,
    )
    for match in dynamic_sql_matches:
        line_num = code[:match.start()].count("\n") + 1
        violations.append({
            "line": line_num,
            "severity": RULE_SEVERITY["no_dynamic_sql_injection"],
            "rule": "security.no_dynamic_sql_injection",
            "message": (
                "Dynamic SQL with string concatenation detected — use bind variables "
                "(:param) instead of concatenation to prevent SQL injection"
            ),
            "code_snippet": code[match.start():match.start() + 100].strip(),
        })

    # Check for DBMS_SQL with concatenation
    dbms_sql_matches = re.finditer(r"DBMS_SQL\.PARSE\s*\(", code_upper)
    for match in dbms_sql_matches:
        context = code_upper[match.start():match.start() + 300]
        if "||" in context:
            line_num = code[:match.start()].count("\n") + 1
            violations.append({
                "line": line_num,
                "severity": RULE_SEVERITY["no_dynamic_sql_injection"],
                "rule": "security.no_dynamic_sql_injection",
                "message": "DBMS_SQL.PARSE with string concatenation — verify bind variables are used",
                "code_snippet": code[match.start():match.start() + 80].strip(),
            })

    # Check for sensitive data patterns (passwords in clear text, hardcoded credentials)
    sensitive_patterns = [
        (r"PASSWORD\s*:?=\s*'[^']+'", "Hardcoded password detected"),
        (r"PASSWD\s*:?=\s*'[^']+'", "Hardcoded password detected"),
        (r"SECRET\s*:?=\s*'[^']+'", "Hardcoded secret detected"),
        (r"DBMS_OUTPUT\.PUT_LINE.*(?:PASSWORD|PASSWD|SECRET|CREDENTIAL)", "Sensitive data in DBMS_OUTPUT"),
    ]

    for pattern, message in sensitive_patterns:
        for match in re.finditer(pattern, code_upper):
            line_num = code[:match.start()].count("\n") + 1
            violations.append({
                "line": line_num,
                "severity": "CRITICAL",
                "rule": "security.sensitive_data",
                "message": message,
                "code_snippet": code[match.start():match.start() + 60].strip(),
            })

    if not violations:
        return "PASS: No security vulnerabilities found."

    result = f"VIOLATIONS FOUND: {len(violations)} security issue(s):\n\n"
    for v in violations:
        result += f"  [{v['severity']}] Line {v['line']}: {v['message']}\n"
        if "code_snippet" in v:
            result += f"    Code: {v['code_snippet']}\n"
        result += "\n"
    return result


@beta_tool
def get_code_summary(code: str) -> str:
    """
    Generate a structural summary of the PL/SQL code.

    Identifies all procedures, functions, packages, cursors, and
    provides basic metrics like line count and comment density.

    Args:
        code: The PL/SQL source code to analyze.
    """
    lines = code.split("\n")
    total_lines = len(lines)
    blank_lines = sum(1 for l in lines if not l.strip())
    comment_lines = sum(1 for l in lines if l.strip().startswith("--") or l.strip().startswith("*"))
    code_lines = total_lines - blank_lines - comment_lines

    blocks = _extract_blocks(code)

    procedures = blocks["procedures"]
    functions = blocks["functions"]
    packages = blocks["packages"]

    # Find cursors
    cursors = re.findall(r"CURSOR\s+(\w+)", code, re.IGNORECASE)

    # Find exception declarations
    exceptions = re.findall(r"(\w+)\s+EXCEPTION\s*;", code, re.IGNORECASE)

    # Find constants
    constants = re.findall(r"(\w+)\s+CONSTANT\s+", code, re.IGNORECASE)

    # Detect if using BULK COLLECT/FORALL
    uses_bulk = bool(re.search(r"\bBULK\s+COLLECT\b|\bFORALL\b", code, re.IGNORECASE))
    uses_dynamic_sql = bool(re.search(r"\bEXECUTE\s+IMMEDIATE\b|\bDBMS_SQL\b", code, re.IGNORECASE))

    summary = f"""CODE STRUCTURE SUMMARY:
======================
Total Lines     : {total_lines}
Code Lines      : {code_lines}
Comment Lines   : {comment_lines} ({int(comment_lines/total_lines*100) if total_lines else 0}%)
Blank Lines     : {blank_lines}

OBJECTS FOUND:
  Packages     : {len(packages)} — {', '.join(n for n, _ in packages) if packages else 'None'}
  Procedures   : {len(procedures)} — {', '.join(n for n, _ in procedures) if procedures else 'None'}
  Functions    : {len(functions)} — {', '.join(n for n, _ in functions) if functions else 'None'}
  Cursors      : {len(cursors)} — {', '.join(cursors) if cursors else 'None'}
  Exceptions   : {len(exceptions)} — {', '.join(exceptions) if exceptions else 'None'}
  Constants    : {len(constants)} — {', '.join(constants) if constants else 'None'}

FEATURES USED:
  Bulk Operations (BULK COLLECT/FORALL) : {'Yes' if uses_bulk else 'No'}
  Dynamic SQL (EXECUTE IMMEDIATE)       : {'Yes' if uses_dynamic_sql else 'No'}
"""
    return summary
