"""
PL/SQL Standards Analyzer Agent.

This module implements the main agent that orchestrates the analysis of
PL/SQL code against defined programming standards using the Anthropic API.
"""

import anthropic
from .tools import (
    check_naming_conventions,
    check_error_handling,
    check_documentation,
    check_code_quality,
    check_performance,
    check_security,
    check_file_type_context,
    get_code_summary,
    set_code_context,
)
from .standards import FILE_TYPE_RULES

SYSTEM_PROMPT = """You are a PL/SQL code standards expert specializing in Oracle database development.
Your task is to perform a comprehensive analysis of PL/SQL code for compliance with programming standards.

When analyzing code, you must:
1. Call ALL available analysis tools to cover every aspect of quality
2. Start with get_code_summary to understand the code structure
3. Call check_file_type_context FIRST (before other checks) — it tells you which rules
   apply to this file type and which should be skipped
4. Run all specialized checks (naming, documentation, error handling, quality, performance, security)
   but ONLY report violations for rules that apply to the detected file type
5. Synthesize findings into a clear, actionable compliance report

Your final report must include:
- **Executive Summary**: Overall compliance score (0-100%) and risk level (LOW/MEDIUM/HIGH/CRITICAL)
- **File Type**: Identified object type (.pkb/.pks/.prc/.fnc/.trg) and applicable rule scope
- **Code Structure Overview**: What the code contains (procedures, functions, packages)
- **Findings by Category**: Organized sections for each type of issue
- **Prioritized Action Items**: Issues sorted by severity (CRITICAL → HIGH → MEDIUM → LOW)
- **Positive Observations**: What the code does well (if anything)
- **Recommendations**: Specific, actionable improvements

Format violations clearly with:
- Severity level: [CRITICAL] [HIGH] [MEDIUM] [LOW]
- Line number reference
- Clear explanation of WHY this violates the standard
- Suggested fix

Important: If check_file_type_context marks a rule category as NOT APPLICABLE for the file type,
do not report violations from that category. Focus on rules that matter for the object type.

Be thorough but constructive. The goal is to help developers improve their code quality."""


def analyze_plsql_code(code: str, verbose: bool = False, file_type: str = ".sql") -> str:
    """
    Analyze PL/SQL code for standards compliance using an AI agent.

    Args:
        code: The PL/SQL source code to analyze.
        verbose: If True, print intermediate tool results to stdout.
        file_type: File extension indicating the object type (.pkb, .pks, .prc, .fnc, .trg).

    Returns:
        A comprehensive compliance report as a string.
    """
    client = anthropic.Anthropic()

    tools = [
        get_code_summary,
        check_file_type_context,
        check_naming_conventions,
        check_error_handling,
        check_documentation,
        check_code_quality,
        check_performance,
        check_security,
    ]

    # Describe the file type context in the initial message
    ext = file_type.lower().strip()
    if not ext.startswith("."):
        ext = "." + ext
    type_info = FILE_TYPE_RULES.get(ext, FILE_TYPE_RULES[".sql"])
    file_type_hint = (
        f"File type: **{ext}** — {type_info['description']}\n"
        f"Start by calling check_file_type_context(code=..., file_type='{ext}') "
        f"to see which rules apply.\n\n"
    )

    messages = [
        {
            "role": "user",
            "content": (
                f"Please analyze the following PL/SQL code for compliance with programming standards. "
                f"Run all available analysis tools and provide a comprehensive report.\n\n"
                f"{file_type_hint}"
                f"```sql\n{code}\n```"
            ),
        }
    ]

    # Store code in module-level context so tools work even if the model omits the argument
    set_code_context(code)

    if verbose:
        print("Starting PL/SQL Standards Analysis...\n")
        print("=" * 60)

    # Agentic loop using tool runner
    runner = client.beta.messages.tool_runner(
        model="claude-opus-4-6",
        max_tokens=8192,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        tools=tools,
        messages=messages,
    )

    final_message = None
    for message in runner:
        final_message = message
        if verbose:
            for block in message.content:
                if hasattr(block, "type"):
                    if block.type == "text" and block.text:
                        print(block.text)
                    elif block.type == "tool_use":
                        print(f"\n[Running: {block.name}]")
                    elif block.type == "tool_result":
                        print(f"[Tool result received]")

    if final_message is None:
        return "Error: No response received from the agent."

    # Extract the final text response
    report_parts = []
    for block in final_message.content:
        if hasattr(block, "type") and block.type == "text":
            report_parts.append(block.text)

    return "\n".join(report_parts) if report_parts else "No report generated."


def analyze_file(file_path: str, verbose: bool = False) -> str:
    """
    Analyze a PL/SQL file for standards compliance.

    Args:
        file_path: Path to the PL/SQL file to analyze.
        verbose: If True, print intermediate results.

    Returns:
        A comprehensive compliance report as a string.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()
    except FileNotFoundError:
        return f"Error: File '{file_path}' not found."
    except UnicodeDecodeError:
        try:
            with open(file_path, "r", encoding="latin-1") as f:
                code = f.read()
        except Exception as e:
            return f"Error reading file: {e}"

    if not code.strip():
        return "Error: The file is empty."

    import os
    file_type = os.path.splitext(file_path)[1].lower() or ".sql"
    return analyze_plsql_code(code, verbose=verbose, file_type=file_type)
