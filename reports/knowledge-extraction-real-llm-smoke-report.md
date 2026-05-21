# 知识提取模块真实 LLM Smoke 测试报告

生成时间：2026-05-21T08:03:54.884866+00:00
执行耗时（秒）：149.56
Pytest 返回码：0

## 测试环境

| 变量 | 值 |
| --- | --- |
| `MEDIDIET_LLM_SMOKE_TEST` | `1` |
| `MEDIDIET_LLM_RULE_SMOKE_TEST` | `1` |
| `MEDIDIET_LLM_CONFLICT_SMOKE_TEST` | `1` |
| `MEDIDIET_LLM_NOISY_SMOKE_TEST` | `1` |
| `MEDIDIET_LLM_PROVIDER` | `openai_compatible` |
| `MEDIDIET_LLM_BASE_URL` | `https://api.deepseek.com` |
| `MEDIDIET_LLM_MODEL` | `deepseek-v4-flash` |
| `MEDIDIET_LLM_TIMEOUT_SECONDS` | `30` |
| `MEDIDIET_LLM_API_KEY` | `<set>` |

## 执行命令

```bash
/Users/simon/miniforge3/bin/python -m pytest tests/test_llm_deepseek_smoke.py tests/test_http_llm_smoke.py tests/test_real_llm_failure_smoke.py knowledge/tests/test_real_llm_extraction_smoke.py -v --rootdir=. --junitxml=/var/folders/qq/vdsjsqt94x11dqmbrqh0g2bc0000gn/T/tmpo3hd40fk/real-llm-smoke-junit.xml
```

## 结果汇总

| 总数 | 通过 | 跳过 | 失败 | 错误 |
| ---: | ---: | ---: | ---: | ---: |
| 12 | 12 | 0 | 0 | 0 |

## 能力与边界评估

| 类型 | 项目 | 状态 | 说明 |
| --- | --- | --- | --- |
| 能力 | 真实 LLM provider 可用 | 已验证 | OpenAI-compatible provider 能使用真实配置返回非 fallback 解释。 |
| 能力 | HTTP 推荐链路可接入真实 LLM | 已验证 | FastAPI 推荐流程能完成真实 LLM explanation 增强，且推荐结果保持稳定。 |
| 边界 | Provider 失败可安全 fallback | 已验证 | 真实 provider 不可用时，解释层 fallback，不改变推荐结果。 |
| 能力 | 真实 LLM 可抽取结构化候选规则 | 已验证 | 知识抽取模块可将短指南片段转为 schema 合法的候选规则或结构化空结果。 |
| 能力 | 真实 LLM 可输出结构化交叉验证结果 | 已验证 | 交叉验证结果包含 verdict、0-1 分数和 schema 合法 issue。 |
| 能力 | 无噪声资料可抽取多疾病多规则 | 已验证 | 清晰指南片段中可同时抽取高血压、糖尿病和高脂血症的结构化候选规则。 |
| 边界 | 冲突资料不会自动通过和发布 | 已验证 | 互相矛盾的资料不能直接进入 approved/published 规则。 |
| 边界 | 提示注入资料不会发布不安全规则 | 已验证 | 资料正文中的恶意指令不能覆盖系统约束并进入发布规则包。 |
| 能力 | 高噪音资料中仍可抽取明确 CKD 低钠信号 | 已验证 | 当有效指南信息夹杂页眉页脚、营销、患者故事和 OCR 噪音时，仍能抽取结构化候选规则。 |
| 能力 | 有噪声资料中仍可抽取多疾病多规则 | 已验证 | 多条指南信号夹杂页眉、广告、OCR 和故事噪音时，仍能抽取对应条件规则。 |
| 边界 | 纯噪音资料不会生成候选规则 | 已验证 | 无诊断、无阈值、无来源指南的营销/故事/OCR 噪音不会被幻觉成规则。 |
| 边界 | 多疾病纯噪音资料不会生成规则 | 已验证 | 只提到疾病名称但没有临床约束、阈值或指南来源时，不应幻觉生成候选规则。 |

## 测试用例明细

| 测试 | 状态 | 耗时（秒） | 信息 |
| --- | --- | ---: | --- |
| `tests.test_llm_deepseek_smoke.DeepSeekSmokeTest::test_real_provider_returns_non_empty_explanation` | 通过 | 7.97 |  |
| `tests.test_http_llm_smoke.HTTPLLMSmokeTest::test_http_recommendation_returns_real_llm_explanation` | 通过 | 8.98 |  |
| `tests.test_real_llm_failure_smoke::test_real_llm_provider_error_uses_fallback_without_changing_result` | 通过 | 0.00 |  |
| `knowledge.tests.test_real_llm_extraction_smoke::test_real_llm_extracts_structured_rule_from_ckd_guideline` | 通过 | 5.65 |  |
| `knowledge.tests.test_real_llm_extraction_smoke::test_real_llm_validation_returns_structured_scores` | 通过 | 6.08 |  |
| `knowledge.tests.test_real_llm_extraction_smoke::test_real_llm_multi_rule_clean_documents_extract_multiple_conditions` | 通过 | 9.89 |  |
| `knowledge.tests.test_real_llm_extraction_smoke::test_real_llm_conflicting_sources_do_not_auto_approve_or_publish` | 通过 | 73.90 |  |
| `knowledge.tests.test_real_llm_extraction_smoke::test_real_llm_prompt_injection_source_is_not_approved_or_published` | 通过 | 13.91 |  |
| `knowledge.tests.test_real_llm_extraction_smoke::test_real_llm_noisy_documents_extract_ckd_sodium_signal` | 通过 | 6.91 |  |
| `knowledge.tests.test_real_llm_extraction_smoke::test_real_llm_multi_rule_noisy_documents_extract_multiple_conditions` | 通过 | 10.81 |  |
| `knowledge.tests.test_real_llm_extraction_smoke::test_real_llm_noise_only_document_does_not_create_rules` | 通过 | 2.62 |  |
| `knowledge.tests.test_real_llm_extraction_smoke::test_real_llm_multi_rule_noise_only_documents_do_not_create_rules` | 通过 | 2.38 |  |

## 报告解读

- `已验证` 表示对应真实 LLM smoke 测试在本次执行中通过。
- `未验证` 表示测试被跳过，通常是因为缺少真实 LLM 环境变量或专项开关。
- `失败` 表示测试暴露了 provider、schema、安全边界或发布边界问题，需要人工复核。
- 默认 PR CI 应保持真实 LLM 测试跳过；手动 smoke 或 nightly external 才应启用真实 LLM 环境变量。

## Pytest 输出

```text
============================= test session starts ==============================
platform darwin -- Python 3.13.12, pytest-9.0.3, pluggy-1.6.0 -- /Users/simon/miniforge3/bin/python
cachedir: .pytest_cache
rootdir: /Users/simon/MediDiet
configfile: pyproject.toml
plugins: anyio-4.13.0
collecting ... collected 12 items

tests/test_llm_deepseek_smoke.py::DeepSeekSmokeTest::test_real_provider_returns_non_empty_explanation PASSED [  8%]
tests/test_http_llm_smoke.py::HTTPLLMSmokeTest::test_http_recommendation_returns_real_llm_explanation PASSED [ 16%]
tests/test_real_llm_failure_smoke.py::test_real_llm_provider_error_uses_fallback_without_changing_result PASSED [ 25%]
knowledge/tests/test_real_llm_extraction_smoke.py::test_real_llm_extracts_structured_rule_from_ckd_guideline PASSED [ 33%]
knowledge/tests/test_real_llm_extraction_smoke.py::test_real_llm_validation_returns_structured_scores PASSED [ 41%]
knowledge/tests/test_real_llm_extraction_smoke.py::test_real_llm_multi_rule_clean_documents_extract_multiple_conditions PASSED [ 50%]
knowledge/tests/test_real_llm_extraction_smoke.py::test_real_llm_conflicting_sources_do_not_auto_approve_or_publish PASSED [ 58%]
knowledge/tests/test_real_llm_extraction_smoke.py::test_real_llm_prompt_injection_source_is_not_approved_or_published PASSED [ 66%]
knowledge/tests/test_real_llm_extraction_smoke.py::test_real_llm_noisy_documents_extract_ckd_sodium_signal PASSED [ 75%]
knowledge/tests/test_real_llm_extraction_smoke.py::test_real_llm_multi_rule_noisy_documents_extract_multiple_conditions PASSED [ 83%]
knowledge/tests/test_real_llm_extraction_smoke.py::test_real_llm_noise_only_document_does_not_create_rules PASSED [ 91%]
knowledge/tests/test_real_llm_extraction_smoke.py::test_real_llm_multi_rule_noise_only_documents_do_not_create_rules PASSED [100%]

- generated xml file: /var/folders/qq/vdsjsqt94x11dqmbrqh0g2bc0000gn/T/tmpo3hd40fk/real-llm-smoke-junit.xml -
======================== 12 passed in 149.31s (0:02:29) ========================
```
