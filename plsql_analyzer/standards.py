"""
PL/SQL Programming Standards Definitions.

This module defines the rules and conventions used to evaluate PL/SQL code quality.
"""

STANDARDS = {
    "naming_conventions": {
        "description": "Naming conventions for PL/SQL identifiers",
        "rules": {
            "variables": (
                "Local variables must use prefix 'v' followed by PascalCase"
                " (e.g., vCodEmpresa, vCentroD, vFecha)"
            ),
            "parameters": (
                "Parameters must use prefix 'p' followed by PascalCase"
                " (e.g., pCodEmpresa, pCentroD, pFecha)"
            ),
            "constants": "Constants must use prefix 'c_' or 'gc_' (e.g., c_max_retries, gc_schema)",
            "cursors": "Cursors must use prefix 'cur_' or 'c_' (e.g., cur_employees)",
            "exceptions": "Custom exceptions must use prefix 'e_' or 'ex_' (e.g., e_invalid_data)",
            "types": "User-defined types must use suffix '_t' or '_type' (e.g., employee_rec_t)",
            "records": "Records must use suffix '_rec' or '_r' (e.g., employee_rec)",
            "procedures": "Procedures should follow verb_noun pattern (e.g., update_salary, get_employee)",
            "packages": "Package names should be meaningful nouns (e.g., pkg_hr, pkg_finance)",
        }
    },
    "documentation": {
        "description": "Documentation and comments requirements",
        "rules": {
            "header": (
                "Every procedure/function/package must have a header comment with: "
                "Author, Date, Description, Parameters (for procs/funcs), Returns (for funcs)"
            ),
            "inline_comments": "Complex logic blocks must have inline comments",
            "comment_density": "At least 5% of non-blank lines must be descriptive comments (-- or /* */)",
            "parameter_docs": "Each parameter must be documented with its purpose and valid values",
            "modification_log": "Significant changes should be logged in the header with date and author",
            "version_history": (
                "Package/package body must include a '-- HISTORIA:' block immediately after the "
                "package header, with entries in descending order (newest first) following the format: "
                "'-- H<N>   - <initials> - DD-MM-YYYY', each entry followed by a ticket reference "
                "(e.g., '--        TI-2685 - Title') and one or more description lines. "
                "Example: -- H1   - RM - 23-09-2025 / --        TI-2685 - Title / --        Action taken."
            ),
            "parameter_logging": (
                "Every procedure and function must include a <<PARAMETROS>> labeled block that "
                "registers each input parameter via PAPARAMETROSBITACORA.Parametro(pNombre => '<name>', "
                "pValor => <value>, pParametros => vDetParam). Each declared parameter must appear "
                "in its own numbered comment (-- 01 - pParam) followed by the Parametro() call. "
                "Example: -- 01 - pNoCia / vDetParam := PAPARAMETROSBITACORA.Parametro(pNombre => 'pNoCia', "
                "pValor => TO_CHAR(pNoCia), pParametros => vDetParam);"
            ),
        }
    },
    "error_handling": {
        "description": "Exception handling standards",
        "rules": {
            "exception_block": "Every procedure and function must have an EXCEPTION block",
            "no_silent_exceptions": (
                "WHEN OTHERS THEN NULL is forbidden — exceptions must be logged or re-raised"
            ),
            "specific_exceptions": (
                "Use specific exception names (NO_DATA_FOUND, TOO_MANY_ROWS) before WHEN OTHERS"
            ),
            "error_logging": "Errors should be logged with SQLERRM, SQLCODE, and context information",
            "reraise": "WHEN OTHERS should re-raise with RAISE or use RAISE_APPLICATION_ERROR",
            "error_logging_standard": (
                "Every WHEN OTHERS handler must call ManejoError.InsertarBitacoraError() "
                "passing pCodSistema, pDetalleError (with SQLERRM), and pDetParametros. "
                "Example: pDetError := 'Error en <procedure>. ' || SQLERRM; "
                "ManejoError.InsertarBitacoraError(pCodSistema => <sys>, "
                "pDetalleError => pDetError, pDetParametros => vDetParam);"
            ),
        }
    },
    "code_quality": {
        "description": "Code quality and maintainability rules",
        "rules": {
            "no_select_star": "SELECT * is forbidden — always list columns explicitly",
            "use_type_anchoring": (
                "Use %TYPE and %ROWTYPE for variable declarations instead of hardcoded types"
            ),
            "no_magic_numbers": "Hardcoded literal values must be replaced with named constants",
            "no_magic_strings": "Hardcoded string literals (beyond simple messages) should use constants",
            "line_length": "Lines should not exceed 120 characters",
            "indentation": "Use consistent 2 or 3-space indentation throughout",
            "no_duplicate_code": "Repeated logic blocks should be extracted into separate procedures/functions",
            "no_duplicate_error_messages": (
                "Each procedure/function must have a unique error message in its EXCEPTION handler — "
                "copy-pasted messages hide which procedure actually failed"
            ),
            "end_label_required": (
                "Every PROCEDURE and FUNCTION must close with END <name>; (not just END;) "
                "to improve readability in large packages"
            ),
            "no_dead_code_blocks": (
                "Commented-out code blocks longer than 10 lines must be removed — "
                "use version control history instead of leaving dead code in source"
            ),
        }
    },
    "performance": {
        "description": "Performance best practices",
        "rules": {
            "bulk_operations": (
                "Use BULK COLLECT + FORALL for processing large datasets instead of row-by-row"
            ),
            "cursor_for_loop": (
                "Prefer cursor FOR loops over OPEN/FETCH/CLOSE when bulk operations are not needed"
            ),
            "no_function_in_where": (
                "Avoid calling functions on indexed columns in WHERE clauses (prevents index use)"
            ),
            "limit_bulk_collect": (
                "Use LIMIT clause with BULK COLLECT to avoid excessive memory consumption"
            ),
            "avoid_implicit_conversions": (
                "Ensure data types match to avoid implicit conversions that hurt performance"
            ),
        }
    },
    "transaction_control": {
        "description": "Transaction management rules",
        "rules": {
            "commit_placement": (
                "COMMIT/ROLLBACK should only appear in top-level procedures or explicit transaction managers"
            ),
            "no_commit_in_loops": "Never place COMMIT inside loops — batch commits cause issues",
            "savepoints": "Use SAVEPOINTs for complex multi-step operations to allow partial rollback",
            "autonomous_transactions": (
                "Use PRAGMA AUTONOMOUS_TRANSACTION carefully and only for logging/auditing"
            ),
        }
    },
    "security": {
        "description": "Security and data protection standards",
        "rules": {
            "no_dynamic_sql_injection": (
                "Dynamic SQL must use bind variables — never concatenate user input into SQL strings"
            ),
            "privilege_management": "Procedures should use AUTHID CURRENT_USER where appropriate",
            "sensitive_data": "Sensitive data (passwords, SSN, etc.) must not be logged or displayed",
        }
    },
}

FILE_TYPE_RULES = {
    ".pkb": {
        "description": "Oracle Package Body — contains procedure and function implementations",
        "applies": "all",
        "not_applicable": [],
        "additional_checks": [],
    },
    ".pks": {
        "description": "Oracle Package Specification — public interface declarations only, no executable code",
        "applies": [
            "naming_conventions",
            "documentation.header",
            "documentation.version_history",
            "documentation.comment_density",
        ],
        "not_applicable": [
            "error_handling",          # no BEGIN/END executable blocks
            "documentation.parameter_logging",   # no procedure bodies
            "performance",             # no executable code
            "transaction_control",     # no executable code
            "code_quality.no_dead_code_blocks",
            "code_quality.end_label_required",
            "code_quality.no_duplicate_error_messages",
        ],
        "additional_checks": [],
    },
    ".prc": {
        "description": "Oracle Standalone Procedure — a single stored procedure",
        "applies": "all",
        "not_applicable": [
            "documentation.version_history",  # version history is a package-level concern
        ],
        "additional_checks": [
            "Standalone procedures must have CREATE OR REPLACE PROCEDURE at the top",
        ],
    },
    ".fnc": {
        "description": "Oracle Standalone Function — a single stored function",
        "applies": "all",
        "not_applicable": [
            "documentation.version_history",  # version history is a package-level concern
        ],
        "additional_checks": [
            "Standalone functions must have CREATE OR REPLACE FUNCTION at the top",
            "Functions must always return a value on every code path",
        ],
    },
    ".trg": {
        "description": "Oracle Database Trigger — fires automatically on DML or DDL events",
        "applies": [
            "naming_conventions",
            "documentation.header",
            "documentation.comment_density",
            "error_handling.exception_block",
            "error_handling.no_silent_exceptions",
            "error_handling.error_logging_standard",
            "code_quality.no_select_star",
            "security",
        ],
        "not_applicable": [
            "documentation.version_history",    # not a package
            "documentation.parameter_logging",  # triggers have no explicit parameters
            "transaction_control.no_commit_in_loops",
            "performance.bulk_operations",
        ],
        "additional_checks": [
            "Triggers must NEVER contain COMMIT or ROLLBACK (causes ORA-04092)",
            "Avoid complex logic in triggers — delegate to package procedures",
            "PRAGMA AUTONOMOUS_TRANSACTION only allowed for audit/error logging",
            "Triggers on high-volume tables must be minimal to avoid performance impact",
        ],
    },
    ".sql": {
        "description": "Generic SQL/PL/SQL script — apply all rules; object type inferred from content",
        "applies": "all",
        "not_applicable": [],
        "additional_checks": [],
    },
}

SEVERITY_LEVELS = {
    "CRITICAL": "Must be fixed — security risk or data integrity issue",
    "HIGH": "Should be fixed — significant quality or reliability issue",
    "MEDIUM": "Recommended fix — code quality and maintainability issue",
    "LOW": "Minor improvement — style or convention issue",
}

RULE_SEVERITY = {
    # Security - Critical
    "no_dynamic_sql_injection": "CRITICAL",
    "sensitive_data": "CRITICAL",
    # Error handling - High
    "no_silent_exceptions": "HIGH",
    "exception_block": "HIGH",
    "no_select_star": "HIGH",
    "no_commit_in_loops": "HIGH",
    # Code quality - Medium
    "use_type_anchoring": "MEDIUM",
    "no_magic_numbers": "MEDIUM",
    "no_magic_strings": "MEDIUM",
    "bulk_operations": "MEDIUM",
    "limit_bulk_collect": "MEDIUM",
    "header": "MEDIUM",
    "comment_density": "MEDIUM",
    "parameter_docs": "MEDIUM",
    "error_logging": "MEDIUM",
    "specific_exceptions": "MEDIUM",
    # Naming and style - Low/Medium
    "variables": "LOW",
    "parameters": "LOW",
    "constants": "LOW",
    "cursors": "LOW",
    "exceptions": "LOW",
    "line_length": "LOW",
    "indentation": "LOW",
    "inline_comments": "LOW",
    "commit_placement": "MEDIUM",
    "autonomous_transactions": "MEDIUM",
    "error_logging_standard": "HIGH",
    "no_duplicate_error_messages": "MEDIUM",
    "end_label_required": "LOW",
    "no_dead_code_blocks": "LOW",
    "version_history": "MEDIUM",
    "parameter_logging": "MEDIUM",
}
