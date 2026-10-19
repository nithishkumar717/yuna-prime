"""Human-readable accessibility reports for CI/CD and developer documentation."""

from __future__ import annotations

import io
from typing import Any, Dict


class AccessibilityReportGenerator:
    """Generates human-readable accessibility audit reports (Text/Markdown) suitable for CI/CD."""

    @classmethod
    def generate_text_report(cls, audit_results: Dict[str, Any]) -> str:
        """Generate a plain-text human-readable accessibility report."""
        out = io.StringIO()
        theme_name = audit_results.get("theme_name", "unknown")
        wcag_level = audit_results.get("wcag_level", "AA")
        issues = audit_results.get("issues", [])
        passes = audit_results.get("passes", [])

        out.write("======================================================================\n")
        out.write(f"ACCESSIBILITY AUDIT REPORT: Theme '{theme_name}'\n")
        out.write(f"WCAG Compliance Target: Level {wcag_level}\n")
        out.write("======================================================================\n\n")

        total_checks = len(passes) + len(issues)
        out.write("Audit Summary:\n")
        out.write(f"  - Total Checks: {total_checks}\n")
        out.write(f"  - Passed:       {len(passes)}\n")
        out.write(f"  - Failed:       {len(issues)}\n\n")

        if issues:
            out.write("----------------------------------------------------------------------\n")
            out.write("ISSUES DETECTED:\n")
            out.write("----------------------------------------------------------------------\n")
            for i, issue in enumerate(issues, 1):
                severity = issue.get("severity", "error").upper()
                msg = issue.get("message", "")
                out.write(f" {i}. [{severity}] {msg}\n")
            out.write("\n")
        else:
            out.write("No accessibility issues detected. Complete compliance achieved!\n\n")

        if passes:
            out.write("----------------------------------------------------------------------\n")
            out.write("PASSED AUDITS:\n")
            out.write("----------------------------------------------------------------------\n")
            for p in passes:
                audit_type = p.get("type", "contrast")
                fg = p.get("foreground", "")
                bg = p.get("background", "")
                ratio = p.get("ratio", 0.0)
                out.write(f"  [PASS] {audit_type.capitalize()}: {fg} on {bg} (Ratio: {ratio}:1)\n")

        return out.getvalue()

    @classmethod
    def generate_markdown_report(cls, audit_results: Dict[str, Any]) -> str:
        """Generate a markdown-formatted accessibility report suitable for PR comments."""
        out = io.StringIO()
        theme_name = audit_results.get("theme_name", "unknown")
        wcag_level = audit_results.get("wcag_level", "AA")
        issues = audit_results.get("issues", [])
        passes = audit_results.get("passes", [])

        out.write(f"# Accessibility Audit Report: Theme `{theme_name}`\n\n")
        out.write(f"**WCAG Compliance Target:** Level {wcag_level}  \n")

        status = "🔴 FAILED" if issues else "🟢 PASSED"
        out.write(f"**Status:** {status}\n\n")

        out.write("## Summary\n\n")
        out.write("| Metric | Count |\n")
        out.write("| --- | --- |\n")
        out.write(f"| Passed Checks | {len(passes)} |\n")
        out.write(f"| Failed Checks | {len(issues)} |\n")
        out.write(f"| Total Audits | {len(passes) + len(issues)} |\n\n")

        if issues:
            out.write("## ⚠️ Issues Found\n\n")
            out.write("| # | Severity | Type | Description | Ratio |\n")
            out.write("| --- | --- | --- | --- | --- |\n")
            for i, issue in enumerate(issues, 1):
                severity = issue.get("severity", "error").upper()
                msg = issue.get("message", "")
                ratio = issue.get("ratio", "-")
                issue_type = issue.get("type", "contrast")
                out.write(f"| {i} | {severity} | {issue_type} | {msg} | {ratio} |\n")
            out.write("\n")
        else:
            out.write("## 🎉 No issues found! All audits passed.\n\n")

        if passes:
            out.write("## ✅ Details of Passed Audits\n\n")
            out.write("| Check Type | Foreground | Background | Actual Ratio |\n")
            out.write("| --- | --- | --- | --- |\n")
            for p in passes:
                audit_type = p.get("type", "contrast")
                fg = p.get("foreground", "")
                bg = p.get("background", "")
                ratio = p.get("ratio", 0.0)
                out.write(f"| {audit_type} | `{fg}` | `{bg}` | {ratio}:1 |\n")
            out.write("\n")

        return out.getvalue()

    @classmethod
    def verify_ci_compliance(cls, audit_results: Dict[str, Any]) -> bool:
        """Returns True if there are no errors in the audit results, suitable for CI/CD gates."""
        issues = audit_results.get("issues", [])
        for issue in issues:
            if issue.get("severity", "error") == "error":
                return False
        return True
