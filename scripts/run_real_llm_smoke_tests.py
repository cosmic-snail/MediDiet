from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree


DEFAULT_TEST_TARGETS = [
    "tests/test_llm_deepseek_smoke.py",
    "tests/test_http_llm_smoke.py",
    "tests/test_real_llm_failure_smoke.py",
    "knowledge/tests/test_real_llm_extraction_smoke.py",
]

ENV_KEYS = [
    "MEDIDIET_LLM_SMOKE_TEST",
    "MEDIDIET_LLM_RULE_SMOKE_TEST",
    "MEDIDIET_LLM_CONFLICT_SMOKE_TEST",
    "MEDIDIET_LLM_NOISY_SMOKE_TEST",
    "MEDIDIET_LLM_PROVIDER",
    "MEDIDIET_LLM_BASE_URL",
    "MEDIDIET_LLM_MODEL",
    "MEDIDIET_LLM_TIMEOUT_SECONDS",
]

SENSITIVE_ENV_KEYS = ["MEDIDIET_LLM_API_KEY"]

CAPABILITY_BY_TEST = {
    "test_real_provider_returns_non_empty_explanation": (
        "能力",
        "真实 LLM provider 可用",
        "OpenAI-compatible provider 能使用真实配置返回非 fallback 解释。",
    ),
    "test_http_recommendation_returns_real_llm_explanation": (
        "能力",
        "HTTP 推荐链路可接入真实 LLM",
        "FastAPI 推荐流程能完成真实 LLM explanation 增强，且推荐结果保持稳定。",
    ),
    "test_real_llm_provider_error_uses_fallback_without_changing_result": (
        "边界",
        "Provider 失败可安全 fallback",
        "真实 provider 不可用时，解释层 fallback，不改变推荐结果。",
    ),
    "test_real_llm_extracts_structured_rule_from_ckd_guideline": (
        "能力",
        "真实 LLM 可抽取结构化候选规则",
        "知识抽取模块可将短指南片段转为 schema 合法的候选规则或结构化空结果。",
    ),
    "test_real_llm_validation_returns_structured_scores": (
        "能力",
        "真实 LLM 可输出结构化交叉验证结果",
        "交叉验证结果包含 verdict、0-1 分数和 schema 合法 issue。",
    ),
    "test_real_llm_multi_rule_clean_documents_extract_multiple_conditions": (
        "能力",
        "无噪声资料可抽取多疾病多规则",
        "清晰指南片段中可同时抽取高血压、糖尿病和高脂血症的结构化候选规则。",
    ),
    "test_real_llm_conflicting_sources_do_not_auto_approve_or_publish": (
        "边界",
        "冲突资料不会自动通过和发布",
        "互相矛盾的资料不能直接进入 approved/published 规则。",
    ),
    "test_real_llm_prompt_injection_source_is_not_approved_or_published": (
        "边界",
        "提示注入资料不会发布不安全规则",
        "资料正文中的恶意指令不能覆盖系统约束并进入发布规则包。",
    ),
    "test_real_llm_noisy_documents_extract_ckd_sodium_signal": (
        "能力",
        "高噪音资料中仍可抽取明确 CKD 低钠信号",
        "当有效指南信息夹杂页眉页脚、营销、患者故事和 OCR 噪音时，仍能抽取结构化候选规则。",
    ),
    "test_real_llm_multi_rule_noisy_documents_extract_multiple_conditions": (
        "能力",
        "有噪声资料中仍可抽取多疾病多规则",
        "多条指南信号夹杂页眉、广告、OCR 和故事噪音时，仍能抽取对应条件规则。",
    ),
    "test_real_llm_noise_only_document_does_not_create_rules": (
        "边界",
        "纯噪音资料不会生成候选规则",
        "无诊断、无阈值、无来源指南的营销/故事/OCR 噪音不会被幻觉成规则。",
    ),
    "test_real_llm_multi_rule_noise_only_documents_do_not_create_rules": (
        "边界",
        "多疾病纯噪音资料不会生成规则",
        "只提到疾病名称但没有临床约束、阈值或指南来源时，不应幻觉生成候选规则。",
    ),
}


@dataclass(frozen=True)
class TestCaseResult:
    name: str
    classname: str
    status: str
    time_seconds: float
    message: str


def _load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE lines from a dotenv file without overriding env."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _status_for_case(case: ElementTree.Element) -> tuple[str, str]:
    skipped = case.find("skipped")
    failure = case.find("failure")
    error = case.find("error")
    if skipped is not None:
        return "SKIPPED", skipped.get("message", "")
    if failure is not None:
        return "FAILED", failure.get("message", "")
    if error is not None:
        return "ERROR", error.get("message", "")
    return "PASSED", ""


def _parse_junit(path: Path) -> list[TestCaseResult]:
    root = ElementTree.parse(path).getroot()
    cases: list[TestCaseResult] = []
    for case in root.iter("testcase"):
        status, message = _status_for_case(case)
        cases.append(
            TestCaseResult(
                name=case.get("name", ""),
                classname=case.get("classname", ""),
                status=status,
                time_seconds=float(case.get("time", "0") or 0),
                message=message,
            )
        )
    return cases


def _env_snapshot() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for key in ENV_KEYS:
        rows.append((key, os.getenv(key, "<unset>")))
    for key in SENSITIVE_ENV_KEYS:
        rows.append((key, "<set>" if os.getenv(key) else "<unset>"))
    return rows


def _capability_status(cases: list[TestCaseResult], test_name: str) -> str:
    matched = [case for case in cases if case.name == test_name]
    if not matched:
        return "NOT RUN"
    statuses = {case.status for case in matched}
    if statuses == {"PASSED"}:
        return "已验证"
    if statuses == {"SKIPPED"}:
        return "未验证"
    if "FAILED" in statuses or "ERROR" in statuses:
        return "失败"
    return ", ".join(sorted(statuses))


def _case_status_label(status: str) -> str:
    return {
        "PASSED": "通过",
        "SKIPPED": "跳过",
        "FAILED": "失败",
        "ERROR": "错误",
    }.get(status, status)


def _write_report(
    report_path: Path,
    *,
    cases: list[TestCaseResult],
    pytest_return_code: int,
    command: list[str],
    stdout: str,
    stderr: str,
    started_at: datetime,
    finished_at: datetime,
) -> None:
    total = len(cases)
    passed = sum(1 for case in cases if case.status == "PASSED")
    skipped = sum(1 for case in cases if case.status == "SKIPPED")
    failed = sum(1 for case in cases if case.status == "FAILED")
    errors = sum(1 for case in cases if case.status == "ERROR")

    lines = [
        "# 知识提取模块真实 LLM Smoke 测试报告",
        "",
        f"生成时间：{finished_at.isoformat()}",
        f"执行耗时（秒）：{(finished_at - started_at).total_seconds():.2f}",
        f"Pytest 返回码：{pytest_return_code}",
        "",
        "## 测试环境",
        "",
        "| 变量 | 值 |",
        "| --- | --- |",
    ]
    for key, value in _env_snapshot():
        lines.append(f"| `{key}` | `{value}` |")

    lines.extend(
        [
            "",
            "## 执行命令",
            "",
            "```bash",
            " ".join(command),
            "```",
            "",
            "## 结果汇总",
            "",
            "| 总数 | 通过 | 跳过 | 失败 | 错误 |",
            "| ---: | ---: | ---: | ---: | ---: |",
            f"| {total} | {passed} | {skipped} | {failed} | {errors} |",
            "",
            "## 能力与边界评估",
            "",
            "| 类型 | 项目 | 状态 | 说明 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for test_name, (kind, item, meaning) in CAPABILITY_BY_TEST.items():
        lines.append(
            f"| {kind} | {item} | {_capability_status(cases, test_name)} | {meaning} |"
        )

    lines.extend(
        [
            "",
            "## 测试用例明细",
            "",
            "| 测试 | 状态 | 耗时（秒） | 信息 |",
            "| --- | --- | ---: | --- |",
        ]
    )
    for case in cases:
        message = (case.message or "").replace("\n", " ").replace("|", "\\|")
        lines.append(
            f"| `{case.classname}::{case.name}` | {_case_status_label(case.status)} | "
            f"{case.time_seconds:.2f} | {message} |"
        )

    lines.extend(
        [
            "",
            "## 报告解读",
            "",
            "- `已验证` 表示对应真实 LLM smoke 测试在本次执行中通过。",
            "- `未验证` 表示测试被跳过，通常是因为缺少真实 LLM 环境变量或专项开关。",
            "- `失败` 表示测试暴露了 provider、schema、安全边界或发布边界问题，需要人工复核。",
            "- 默认 PR CI 应保持真实 LLM 测试跳过；手动 smoke 或 nightly external 才应启用真实 LLM 环境变量。",
            "",
            "## Pytest 输出",
            "",
            "```text",
            stdout.strip()[-6000:],
            "```",
        ]
    )
    if stderr.strip():
        lines.extend(["", "## Pytest 标准错误", "", "```text", stderr.strip()[-3000:], "```"])

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run opt-in real LLM smoke tests and write a Markdown report."
    )
    parser.add_argument(
        "--report",
        default="reports/knowledge-extraction-real-llm-smoke-report.md",
        help="Markdown report path.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Dotenv file to load before running tests. Existing environment wins.",
    )
    parser.add_argument(
        "--pytest-arg",
        action="append",
        default=[],
        help="Additional argument passed through to pytest. Can be repeated.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    _load_dotenv(repo_root / args.env_file)

    report_path = Path(args.report)
    with tempfile.TemporaryDirectory() as tmpdir:
        junit_path = Path(tmpdir) / "real-llm-smoke-junit.xml"
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH")
        smoke_pythonpath = "src:knowledge/src"
        env["PYTHONPATH"] = (
            f"{smoke_pythonpath}:{existing_pythonpath}"
            if existing_pythonpath
            else smoke_pythonpath
        )
        command = [
            sys.executable,
            "-m",
            "pytest",
            *DEFAULT_TEST_TARGETS,
            "-v",
            "--rootdir=.",
            f"--junitxml={junit_path}",
            *args.pytest_arg,
        ]

        started_at = datetime.now(timezone.utc)
        completed = subprocess.run(
            command,
            cwd=repo_root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        finished_at = datetime.now(timezone.utc)

        cases = _parse_junit(junit_path) if junit_path.exists() else []
        _write_report(
            report_path,
            cases=cases,
            pytest_return_code=completed.returncode,
            command=command,
            stdout=completed.stdout,
            stderr=completed.stderr,
            started_at=started_at,
            finished_at=finished_at,
        )

    print(f"Report written to {report_path}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
