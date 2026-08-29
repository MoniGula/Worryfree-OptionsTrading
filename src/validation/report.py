"""
Human-readable reporting for leak-audit and walk-forward validation runs.

Turns the structured outputs of ``leak_scanner`` and ``walk_forward`` into
a plain-text (Markdown-friendly) report suitable for pasting into the
hackathon write-up's "Results Snapshot" section or logging to a file.
"""

from __future__ import annotations

from src.validation.leak_scanner import LeakAuditReport
from src.validation.walk_forward import WalkForwardResult


def format_leak_audit_report(report: LeakAuditReport, feature_name: str = "feature") -> str:
    """
    Render a ``LeakAuditReport`` as a short Markdown section.

    Parameters
    ----------
    report:
        Result of ``leak_scanner.audit_feature``.
    feature_name:
        Label used in the report header.

    Returns
    -------
    str
        Markdown-formatted report text.
    """
    status = "PASSED" if report.passed else "FAILED"
    lines = [f"### Leak audit — {feature_name}: {status}"]

    if report.errors:
        lines.append("**Errors:**")
        lines.extend(f"- {err}" for err in report.errors)
    if report.warnings:
        lines.append("**Warnings:**")
        lines.extend(f"- {warn}" for warn in report.warnings)
    if not report.errors and not report.warnings:
        lines.append("No issues detected.")

    return "\n".join(lines)


def format_walk_forward_report(result: WalkForwardResult, label: str = "strategy") -> str:
    """
    Render a ``WalkForwardResult`` as a short Markdown section, including
    per-fold scores and the aggregate mean/std across folds.

    Parameters
    ----------
    result:
        Result of ``walk_forward.run_walk_forward``.
    label:
        Label used in the report header (e.g. the strategy or feature name).

    Returns
    -------
    str
        Markdown-formatted report text.
    """
    lines = [f"### Walk-forward validation — {label}"]
    lines.append(f"Folds run: {len(result.fold_scores)}")
    lines.append(f"Mean score: {result.mean_score:.4f}")
    lines.append(f"Score std: {result.score_std:.4f}")
    lines.append("")
    lines.append("| Fold | Train range | Validation range | Score | Error |")
    lines.append("|------|-------------|-------------------|-------|-------|")

    for fold in result.fold_scores:
        score_str = f"{fold['score']:.4f}" if fold["score"] is not None else "-"
        error_str = fold["error"] or "-"
        lines.append(
            f"| {fold['fold']} | {fold['train_range']} | "
            f"{fold['validation_range']} | {score_str} | {error_str} |"
        )

    return "\n".join(lines)


def write_report(path: str, sections: list[str]) -> None:
    """
    Write a list of pre-rendered Markdown report sections to a file.

    Parameters
    ----------
    path:
        Destination file path.
    sections:
        List of Markdown strings (e.g. from ``format_leak_audit_report``
        and ``format_walk_forward_report``) to concatenate and write.
    """
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n\n".join(sections))
        handle.write("\n")
