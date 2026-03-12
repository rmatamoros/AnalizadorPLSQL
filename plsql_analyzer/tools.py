"""
PL/SQL Analysis Tools.

Each function is a static analysis tool that checks a specific aspect of PL/SQL code.
These tools are registered with the Anthropic beta tool runner.
"""

import re
from anthropic import beta_tool
from .standards import RULE_SEVERITY, FILE_TYPE_RULES


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

    # --- Rule: Standard error logging via ManejoError.InsertarBitacoraError ---
    # Every WHEN OTHERS handler must call ManejoError.InsertarBitacoraError()
    # with pCodSistema, pDetalleError (containing SQLERRM), and pDetParametros.
    _INSERTAR_BITACORA_RE = re.compile(
        r"ManejoError\s*\.\s*InsertarBitacoraError\s*\(",
        re.IGNORECASE,
    )
    _PDET_ERROR_RE = re.compile(r"\bpDetError\b", re.IGNORECASE)

    for match in re.finditer(r"WHEN\s+OTHERS\s+THEN", code, re.IGNORECASE):
        line_num = code[: match.start()].count("\n") + 1
        # Extract handler body: from THEN up to next WHEN or END (max 800 chars)
        body_start = match.end()
        body_end = min(body_start + 800, len(code))
        raw_body = code[body_start:body_end]
        # Trim at the next handler boundary
        boundary = re.search(r"\bWHEN\b|\bEND\b", raw_body, re.IGNORECASE)
        handler_body = raw_body[: boundary.start()] if boundary else raw_body

        has_insertar = bool(_INSERTAR_BITACORA_RE.search(handler_body))
        has_pdet_error = bool(_PDET_ERROR_RE.search(handler_body))

        if not has_insertar:
            missing_parts = []
            if not has_pdet_error:
                missing_parts.append("pDetError assignment with SQLERRM")
            missing_parts.append("ManejoError.InsertarBitacoraError() call")
            violations.append({
                "line": line_num,
                "severity": RULE_SEVERITY["error_logging_standard"],
                "rule": "error_handling.error_logging_standard",
                "message": (
                    f"WHEN OTHERS handler at line {line_num} is missing: "
                    f"{' and '.join(missing_parts)}. "
                    f"Expected pattern: pDetError := 'Error en <proc>. ' || SQLERRM; "
                    f"ManejoError.InsertarBitacoraError(pCodSistema => ..., "
                    f"pDetalleError => pDetError, pDetParametros => vDetParam);"
                ),
            })
        elif not has_pdet_error:
            violations.append({
                "line": line_num,
                "severity": "MEDIUM",
                "rule": "error_handling.error_logging_standard",
                "message": (
                    f"WHEN OTHERS handler at line {line_num} calls InsertarBitacoraError "
                    f"but pDetError does not appear to be assigned with SQLERRM before the call. "
                    f"Ensure: pDetError := 'Error en <proc>. ' || SQLERRM;"
                ),
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
    Also verifies that at least 5% of non-blank lines are descriptive comments.

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

    # --- Rule: Version history (HISTORIA block) ---
    # Only check at the package level (PACKAGE BODY or standalone PACKAGE IS/AS)
    _HISTORIA_BLOCK_RE = re.compile(r"--\s*HISTORIA\s*:", re.IGNORECASE)
    _HISTORIA_ENTRY_RE = re.compile(
        r"--\s+H(\d+)\s+-\s+(\w+)\s+-\s+(\d{2}-\d{2}-\d{4})",
        re.IGNORECASE,
    )

    pkg_header = re.search(
        r"CREATE\s+(?:OR\s+REPLACE\s+)?PACKAGE\s+(?:BODY\s+)?(\w+)\s+(?:IS|AS)",
        code,
        re.IGNORECASE,
    )
    if pkg_header:
        pkg_name = pkg_header.group(1)
        pkg_line = code[: pkg_header.start()].count("\n") + 1
        # Search within the first 3 000 characters after the package header
        search_window = code[pkg_header.start(): pkg_header.start() + 3000]

        historia_match = _HISTORIA_BLOCK_RE.search(search_window)
        if not historia_match:
            violations.append({
                "line": pkg_line,
                "severity": RULE_SEVERITY["version_history"],
                "rule": "documentation.version_history",
                "message": (
                    f"Package '{pkg_name}' (line {pkg_line}) is missing a '-- HISTORIA:' "
                    f"version history block. Add it immediately after the package header "
                    f"with entries in format: -- H<N>   - <initials> - DD-MM-YYYY"
                ),
            })
        else:
            historia_abs_line = (
                code[: pkg_header.start() + historia_match.start()].count("\n") + 1
            )
            # Content after the "-- HISTORIA:" marker up to end of search window
            after_historia = search_window[historia_match.end():]

            entries = list(_HISTORIA_ENTRY_RE.finditer(after_historia))

            if not entries:
                violations.append({
                    "line": historia_abs_line,
                    "severity": RULE_SEVERITY["version_history"],
                    "rule": "documentation.version_history",
                    "message": (
                        f"'-- HISTORIA:' block at line {historia_abs_line} has no valid entries. "
                        f"Each entry must follow: -- H<N>   - <initials> - DD-MM-YYYY"
                    ),
                })
            else:
                # Entries must be in descending order (H3, H2, H1, H0 …)
                entry_nums = [int(e.group(1)) for e in entries]
                if entry_nums != sorted(entry_nums, reverse=True):
                    violations.append({
                        "line": historia_abs_line,
                        "severity": RULE_SEVERITY["version_history"],
                        "rule": "documentation.version_history",
                        "message": (
                            f"'-- HISTORIA:' entries starting at line {historia_abs_line} "
                            f"are not in descending order ({entry_nums}). "
                            f"The newest entry (highest H number) must appear first."
                        ),
                    })

                # Each entry must have at least one ticket/detail line after it
                for entry in entries:
                    entry_abs_line = (
                        code[: pkg_header.start() + historia_match.end() + entry.start()]
                        .count("\n") + 1
                    )
                    # Grab text until the next entry header or an empty -- line
                    body_start = entry.end()
                    next_entry = _HISTORIA_ENTRY_RE.search(after_historia[body_start:])
                    body_end = (
                        body_start + next_entry.start()
                        if next_entry
                        else body_start + 500
                    )
                    entry_body = after_historia[body_start:body_end]

                    # A ticket line looks like:  "--        TI-1234 …"  or  "--   TI-1234 …"
                    has_ticket = bool(
                        re.search(r"--\s{2,}\w+-\d+", entry_body)
                    )
                    if not has_ticket:
                        violations.append({
                            "line": entry_abs_line,
                            "severity": "LOW",
                            "rule": "documentation.version_history",
                            "message": (
                                f"History entry H{entry.group(1)} at line {entry_abs_line} "
                                f"is missing a ticket reference line "
                                f"(expected format: --        TI-XXXX - Description)"
                            ),
                        })

    # --- Rule: Parameter logging block (<<PARAMETROS>>) ---
    # Every procedure/function inside a package body must have a <<PARAMETROS>> labeled block
    # that calls PAPARAMETROSBITACORA.Parametro() for each declared parameter.
    _PARAM_BLOCK_RE = re.compile(r"<<\s*PARAMETROS\s*>>", re.IGNORECASE)
    _PARAM_CALL_RE = re.compile(
        r"PAPARAMETROSBITACORA\s*\.\s*Parametro\s*\(\s*pNombre\s*=>\s*'(\w+)'",
        re.IGNORECASE,
    )
    _PARAM_DECL_RE = re.compile(
        r"^\s*(\w+)\s+(?:IN\s+OUT|IN|OUT)\s+(?:NOCOPY\s+)?\w+",
        re.IGNORECASE,
    )

    for block_type, block_name, block_line in all_blocks:
        if block_type not in ("PROCEDURE", "FUNCTION"):
            continue

        # Slice the source from the declaration line onward (up to ~500 lines)
        block_start_idx = sum(len(l) + 1 for l in lines[: block_line - 1])
        block_src = code[block_start_idx: block_start_idx + 15000]

        # Collect declared parameters for this block (signature before BEGIN/IS/AS)
        sig_end = re.search(r"\bBEGIN\b", block_src, re.IGNORECASE)
        if not sig_end:
            continue
        signature_src = block_src[: sig_end.start()]
        declared_params = []
        reserved_words = {"return", "is", "as", "procedure", "function", "begin", "end"}

        # 1. Multi-line style: each parameter on its own line
        for sig_line in signature_src.split("\n"):
            m = _PARAM_DECL_RE.match(sig_line)
            if m and m.group(1).lower() not in reserved_words:
                declared_params.append(m.group(1).lower())

        # 2. Inline style: PROCEDURE foo(pA IN NUMBER, pB IN DATE)
        if not declared_params:
            inline_sig = re.search(
                r"(?:PROCEDURE|FUNCTION)\s+\w+\s*\(([^)]+)\)",
                signature_src,
                re.IGNORECASE | re.DOTALL,
            )
            if inline_sig:
                for part in inline_sig.group(1).split(","):
                    m = re.match(r"\s*(\w+)\s+(?:IN\s+OUT|IN|OUT)", part, re.IGNORECASE)
                    if m and m.group(1).lower() not in reserved_words:
                        declared_params.append(m.group(1).lower())

        if not declared_params:
            # No parameters — nothing to log
            continue

        # Look for the <<PARAMETROS>> block inside the procedure body
        body_src = block_src[sig_end.start():]
        param_block = _PARAM_BLOCK_RE.search(body_src)

        if not param_block:
            violations.append({
                "line": block_line,
                "severity": RULE_SEVERITY["parameter_logging"],
                "rule": "documentation.parameter_logging",
                "message": (
                    f"{block_type} '{block_name}' (line {block_line}) is missing the "
                    f"<<PARAMETROS>> block to register its parameters in "
                    f"PAPARAMETROSBITACORA. Add a labeled BEGIN/END PARAMETROS block "
                    f"after the main BEGIN that calls PAPARAMETROSBITACORA.Parametro() "
                    f"for each of: {', '.join(declared_params)}"
                ),
            })
        else:
            # Collect which parameters are actually registered in the block
            # (search until END PARAMETROS)
            param_block_start = param_block.start()
            end_parametros = re.search(
                r"\bEND\s+PARAMETROS\s*;", body_src[param_block_start:], re.IGNORECASE
            )
            search_end = (
                param_block_start + end_parametros.end()
                if end_parametros
                else param_block_start + 3000
            )
            parametros_body = body_src[param_block_start:search_end]
            logged_params = {
                m.group(1).lower()
                for m in _PARAM_CALL_RE.finditer(parametros_body)
            }

            missing_params = [p for p in declared_params if p not in logged_params]
            if missing_params:
                param_block_line = (
                    code[: block_start_idx + sig_end.start() + param_block_start]
                    .count("\n") + 1
                )
                violations.append({
                    "line": param_block_line,
                    "severity": RULE_SEVERITY["parameter_logging"],
                    "rule": "documentation.parameter_logging",
                    "message": (
                        f"{block_type} '{block_name}': <<PARAMETROS>> block at line "
                        f"{param_block_line} does not log all parameters. "
                        f"Missing: {', '.join(missing_params)}"
                    ),
                })

    # Check comment density (minimum 5% of non-blank lines)
    MIN_COMMENT_DENSITY = 0.05
    non_blank_lines = [l for l in lines if l.strip()]
    comment_lines = [
        l for l in non_blank_lines
        if l.strip().startswith("--") or l.strip().startswith("*") or l.strip().startswith("/*")
    ]
    total_non_blank = len(non_blank_lines)
    if total_non_blank > 0:
        density = len(comment_lines) / total_non_blank
        if density < MIN_COMMENT_DENSITY:
            violations.append({
                "line": 1,
                "severity": RULE_SEVERITY["comment_density"],
                "rule": "documentation.comment_density",
                "message": (
                    f"Comment density is {density:.1%} ({len(comment_lines)} comment lines / "
                    f"{total_non_blank} non-blank lines) — minimum required is {MIN_COMMENT_DENSITY:.0%}. "
                    f"Add descriptive comments explaining the business logic."
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
    magic numbers/strings, line length violations, duplicate error messages
    in exception handlers, missing END labels, and large commented-out
    code blocks (dead code).

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

    # --- Rule: Duplicate error messages in EXCEPTION handlers ---
    # Extract pDetError := '...' and similar error string assignments
    error_msg_pattern = re.finditer(
        r"(?:pDetError|vDetError|v_det_error)\s*:=\s*'([^']{10,})'",
        code,
        re.IGNORECASE,
    )
    error_msg_occurrences: dict = {}
    for match in error_msg_pattern:
        msg = match.group(1).strip().lower()
        line_num = code[:match.start()].count("\n") + 1
        error_msg_occurrences.setdefault(msg, []).append(line_num)

    for msg, occurrences in error_msg_occurrences.items():
        if len(occurrences) > 1:
            lines_str = ", ".join(str(l) for l in occurrences)
            violations.append({
                "line": occurrences[0],
                "severity": RULE_SEVERITY["no_duplicate_error_messages"],
                "rule": "code_quality.no_duplicate_error_messages",
                "message": (
                    f"Duplicate error message found on lines {lines_str}: "
                    f"'{msg[:60]}...' — each procedure must have a unique message "
                    f"identifying it as the error source"
                ),
            })

    # --- Rule: END label required for procedures and functions ---
    blocks = _extract_blocks(code)
    all_named_blocks = blocks["procedures"] + blocks["functions"]
    for block_name, block_line in all_named_blocks:
        # Search for END <name>; (case-insensitive) anywhere after the declaration
        if not re.search(
            r"\bEND\s+" + re.escape(block_name) + r"\s*;",
            code[code.split("\n", block_line)[-1] if block_line > 0 else 0:],
            re.IGNORECASE,
        ):
            violations.append({
                "line": block_line,
                "severity": RULE_SEVERITY["end_label_required"],
                "rule": "code_quality.end_label_required",
                "message": (
                    f"Procedure/Function '{block_name}' (line {block_line}) "
                    f"appears to close with END; instead of END {block_name}; — "
                    f"add the name for readability in large packages"
                ),
            })

    # --- Rule: No dead code blocks (commented-out code > 10 consecutive lines) ---
    DEAD_CODE_THRESHOLD = 10
    CODE_KEYWORDS = re.compile(
        r"\b(SELECT|INSERT|UPDATE|DELETE|MERGE|BEGIN|END|IF|THEN|ELSE|"
        r"LOOP|CURSOR|PROCEDURE|FUNCTION|RETURN|COMMIT|ROLLBACK)\b",
        re.IGNORECASE,
    )

    # Check consecutive -- comment lines containing code keywords
    consecutive_comment_start = None
    consecutive_code_comments = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        is_code_comment = (
            stripped.startswith("--") and
            bool(CODE_KEYWORDS.search(stripped[2:]))
        )
        if is_code_comment:
            if consecutive_comment_start is None:
                consecutive_comment_start = i
            consecutive_code_comments += 1
        else:
            if consecutive_code_comments >= DEAD_CODE_THRESHOLD:
                violations.append({
                    "line": consecutive_comment_start,
                    "severity": RULE_SEVERITY["no_dead_code_blocks"],
                    "rule": "code_quality.no_dead_code_blocks",
                    "message": (
                        f"Dead code block detected: {consecutive_code_comments} consecutive "
                        f"commented-out lines starting at line {consecutive_comment_start} — "
                        f"remove dead code and use version control history instead"
                    ),
                })
            consecutive_comment_start = None
            consecutive_code_comments = 0

    # Check /* ... */ blocks spanning more than DEAD_CODE_THRESHOLD lines
    block_comment_matches = re.finditer(r"/\*.*?\*/", code, re.DOTALL)
    for match in block_comment_matches:
        block_text = match.group(0)
        block_lines = block_text.count("\n") + 1
        if block_lines > DEAD_CODE_THRESHOLD and CODE_KEYWORDS.search(block_text):
            line_num = code[:match.start()].count("\n") + 1
            violations.append({
                "line": line_num,
                "severity": RULE_SEVERITY["no_dead_code_blocks"],
                "rule": "code_quality.no_dead_code_blocks",
                "message": (
                    f"Large commented-out block /* */ detected at line {line_num} "
                    f"({block_lines} lines) — remove dead code and rely on version control"
                ),
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
def check_file_type_context(code: str, file_type: str) -> str:
    """
    Identify file-type-specific rules and run object-type-specific validations.

    Different Oracle object types have different applicable standards:
    - .pkb  Package Body: all rules apply
    - .pks  Package Specification: no executable code, skip error/performance rules
    - .prc  Standalone Procedure: no version_history, must have CREATE OR REPLACE PROCEDURE
    - .fnc  Standalone Function: no version_history, must always return a value
    - .trg  Trigger: no COMMIT/ROLLBACK, no PARAMETROS block, minimal logic

    Args:
        code: The PL/SQL source code to analyze.
        file_type: File extension including the dot (e.g., '.pkb', '.pks', '.prc', '.fnc', '.trg').
    """
    ext = file_type.lower().strip()
    if not ext.startswith("."):
        ext = "." + ext

    # Normalize unknown extensions to .sql
    if ext not in FILE_TYPE_RULES:
        ext = ".sql"

    rules = FILE_TYPE_RULES[ext]
    violations = []
    lines = code.split("\n")

    output = f"FILE TYPE: {ext}  —  {rules['description']}\n"
    output += "=" * 60 + "\n\n"

    # List applicable vs. not-applicable rules
    if rules["applies"] == "all":
        output += "RULE SCOPE: All standard rules apply.\n"
    else:
        output += f"RULE SCOPE: Only the following rule categories apply:\n"
        for r in rules["applies"]:
            output += f"  ✓ {r}\n"

    if rules["not_applicable"]:
        output += "\nNOT APPLICABLE for this file type (skip these checks):\n"
        for r in rules["not_applicable"]:
            output += f"  ✗ {r}\n"

    if rules["additional_checks"]:
        output += "\nADDITIONAL RULES specific to this file type:\n"
        for r in rules["additional_checks"]:
            output += f"  • {r}\n"

    output += "\nFILE-TYPE-SPECIFIC VIOLATIONS:\n"
    output += "-" * 40 + "\n"

    # ── .pks: must NOT contain BEGIN/END executable blocks ──────────────────
    if ext == ".pks":
        begin_matches = [
            i + 1 for i, l in enumerate(lines)
            if re.search(r"^\s*BEGIN\b", l, re.IGNORECASE) and
            not l.strip().startswith("--")
        ]
        if begin_matches:
            violations.append(
                f"[HIGH] Lines {begin_matches}: Package specification (.pks) should not "
                f"contain executable BEGIN blocks — move implementation to the .pkb file."
            )

    # ── .prc: must start with CREATE OR REPLACE PROCEDURE ───────────────────
    if ext == ".prc":
        if not re.search(r"CREATE\s+(OR\s+REPLACE\s+)?PROCEDURE\b", code, re.IGNORECASE):
            violations.append(
                "[MEDIUM] File does not contain CREATE OR REPLACE PROCEDURE. "
                "A .prc file should define exactly one standalone procedure."
            )

    # ── .fnc: must start with CREATE OR REPLACE FUNCTION ────────────────────
    if ext == ".fnc":
        if not re.search(r"CREATE\s+(OR\s+REPLACE\s+)?FUNCTION\b", code, re.IGNORECASE):
            violations.append(
                "[MEDIUM] File does not contain CREATE OR REPLACE FUNCTION. "
                "A .fnc file should define exactly one standalone function."
            )
        # Functions must have at least one RETURN <value> statement in the body
        # (exclude the "RETURN <type>" in the function signature)
        body_match = re.search(r"\bBEGIN\b", code, re.IGNORECASE)
        body_src = code[body_match.start():] if body_match else code
        if not re.search(r"\bRETURN\s+\S", body_src, re.IGNORECASE):
            violations.append(
                "[HIGH] No RETURN <value> statement found in function body. "
                "Every function must return a value on every code path."
            )

    # ── .trg: must NOT contain COMMIT or ROLLBACK ────────────────────────────
    if ext == ".trg":
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("--"):
                continue
            if re.search(r"\bCOMMIT\b", stripped, re.IGNORECASE):
                violations.append(
                    f"[CRITICAL] Line {i}: COMMIT inside a trigger causes ORA-04092. "
                    f"Remove COMMIT or use PRAGMA AUTONOMOUS_TRANSACTION only for "
                    f"logging in a separate procedure."
                )
            if re.search(r"\bROLLBACK\b", stripped, re.IGNORECASE):
                violations.append(
                    f"[CRITICAL] Line {i}: ROLLBACK inside a trigger causes ORA-04092. "
                    f"Remove explicit ROLLBACK — the trigger's parent transaction handles rollback."
                )

        # Trigger must start with CREATE OR REPLACE TRIGGER
        if not re.search(r"CREATE\s+(OR\s+REPLACE\s+)?TRIGGER\b", code, re.IGNORECASE):
            violations.append(
                "[MEDIUM] File does not contain CREATE OR REPLACE TRIGGER. "
                "A .trg file should define exactly one trigger."
            )

        # Warn if trigger body is unusually large (>100 non-blank lines)
        non_blank = [l for l in lines if l.strip() and not l.strip().startswith("--")]
        if len(non_blank) > 100:
            violations.append(
                f"[MEDIUM] Trigger body has {len(non_blank)} non-blank lines — "
                f"triggers should be minimal. Move business logic to a package procedure "
                f"and call it from the trigger."
            )

    if not violations:
        output += "PASS: No file-type-specific violations found.\n"
    else:
        output += "\n".join(violations) + "\n"

    return output


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
