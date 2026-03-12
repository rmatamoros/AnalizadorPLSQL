# PL/SQL Standards Analyzer

An AI-powered agent that analyzes PL/SQL code for compliance with Oracle database programming standards. Uses Claude Opus 4.6 with adaptive thinking to provide comprehensive, actionable compliance reports.

## Features

The agent checks **7 categories** of PL/SQL standards:

| Category | Rules Checked |
|---|---|
| **Naming Conventions** | Variable prefixes (v_, l_, p_), constants (c_, gc_), cursors (cur_), exceptions (e_) |
| **Documentation** | Header comments with Author, Date, Description, Parameters |
| **Error Handling** | EXCEPTION blocks, no silent handlers, error logging, proper re-raise |
| **Code Quality** | No SELECT *, %TYPE/%ROWTYPE anchoring, no magic numbers, line length |
| **Performance** | BULK COLLECT/FORALL, LIMIT clause, no COMMIT in loops, row-by-row anti-patterns |
| **Transaction Control** | COMMIT/ROLLBACK placement, SAVEPOINTs |
| **Security** | SQL injection via dynamic SQL, hardcoded credentials, sensitive data exposure |

Each violation is assigned a severity level: **CRITICAL**, **HIGH**, **MEDIUM**, or **LOW**.

## Installation

```bash
pip install -r requirements.txt
```

Requires Python 3.11+ and an Anthropic API key.

## Usage

```bash
# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Analyze a PL/SQL file
python main.py my_package.sql

# Analyze with verbose tool output
python main.py my_package.sql --verbose

# Run the demo with the included bad example
python main.py --demo
```

The report is printed to stdout and also saved as `<filename>_report.txt`.

## Example Output

```
COMPLIANCE REPORT
============================================================
## Executive Summary
- Overall Compliance Score: 35/100
- Risk Level: CRITICAL
- Total Violations: 8 (1 Critical, 3 High, 3 Medium, 1 Low)

## Findings

### CRITICAL Issues
- [CRITICAL] Line 42: SQL injection risk — dynamic SQL uses string concatenation
  Fix: Use bind variables: EXECUTE IMMEDIATE sql_stmt USING p_emp_id

### HIGH Issues
- [HIGH] Line 28: WHEN OTHERS THEN NULL silently swallows exceptions
  Fix: Log with SQLERRM and re-raise using RAISE
...
```

## Project Structure

```
plsql_analyzer/
├── __init__.py
├── agent.py      # Main agent — orchestrates analysis with Claude API
├── standards.py  # Standards definitions and severity mapping
└── tools.py      # Six static analysis tools (registered as beta_tools)

examples/
├── sample.sql      # Well-written PL/SQL (mostly compliant)
└── sample_bad.sql  # PL/SQL with intentional violations (for testing)

main.py            # CLI entry point
requirements.txt
```

## How It Works

1. **Tools** (`tools.py`): Six Python functions decorated with `@beta_tool` perform regex-based static analysis on the PL/SQL code. Each tool checks a specific category and returns structured findings.

2. **Agent** (`agent.py`): The Claude Opus 4.6 model acts as the orchestrator. It calls all analysis tools, receives their results, and synthesizes a comprehensive compliance report using adaptive thinking for nuanced interpretation.

3. **Tool Runner**: Uses the Anthropic SDK's `client.beta.messages.tool_runner()` which automatically handles the agentic loop — Claude calls tools, receives results, and iterates until analysis is complete.

## Extending the Analyzer

To add a new check, create a function in `tools.py` decorated with `@beta_tool`:

```python
@beta_tool
def check_my_new_standard(code: str) -> str:
    """
    Description of what this check does.

    Args:
        code: The PL/SQL source code to analyze.
    """
    # Your analysis logic
    violations = []
    # ... detect issues ...
    return f"VIOLATIONS FOUND: {len(violations)} issue(s):\n..."
```

Then add it to the `tools` list in `agent.py`.
