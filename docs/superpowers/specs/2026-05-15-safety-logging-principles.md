# MediDiet Safety Logging Principles

Date: 2026-05-15
Status: Approved for implementation baseline

## Purpose

MediDiet logs must support safety review, operational debugging, and audit traceability without becoming a hidden business interface or creating excessive log volume.

Program logic must use structured return values such as `SafetyCode(IntEnum)` and typed events. Log text is observability data only and must not be parsed by recommendation logic.

## Level Policy

`DEBUG` is for local development diagnostics such as intermediate scoring details or rule traversal. Production keeps it disabled by default.

`INFO` is for normal business milestones such as request start/end, selected rule-pack version, candidate counts, and final outcome. INFO is not used inside high-cardinality candidate or intake loops.

`WARNING` is for recoverable safety or data-quality events that require attention, downgrade, refusal, or human review. Every safety hard block and uncertainty emits one warning event.

`ERROR` is for request-level failure where the current recommendation cannot be completed reliably, but the service process can continue. Examples include corrupt external payloads, missing rule-pack data, or failed log-file setup when the request is safely stopped.

`CRITICAL` is for process-level safety boundary failures where the service should not continue, such as safety gate initialization failure, unavailable mandatory audit infrastructure, or configuration that would bypass safety rules.

## Loop Logging Policy

High-cardinality loops must not emit `DEBUG` or `INFO` per item. This includes menu candidate loops, intake-record loops, rule traversal loops, and future delivery-platform result loops.

Inside loops, log only concrete `WARNING` safety events or higher-severity failures. Safe candidates, normal rule misses, and routine scoring details stay in memory and may be summarized once outside the loop.

## Safety Event Logging

Each `SafetyEvent` is logged at `WARNING` with:

- timestamp from the logging formatter
- process id
- thread id
- integer `SafetyCode.value`
- `SafetyCode.name`
- severity, such as hard block or uncertainty
- patient identifier, using anonymized or internal id where available
- optional entity id, concept, metric, scope, measured value, limit value
- rule-pack version

Tests must verify that safety logs contain timestamp, process id, thread id, and integer safety code.

## Privacy Policy

Logs must not contain patient names, phone numbers, identity numbers, full medical-record text, original food photos, precise addresses, or free-form sensitive notes.

Patient identifiers should be internal ids in MVP and should later support hashing or anonymization. Free-text food names may appear only as low-risk labels and need a future sanitization pass before production deployment.

## Implementation Rule

The core engine emits logs through Python `logging`. Runtime log destinations, rotation, retention, and production redaction are configured by the service entrypoint rather than embedded in recommendation logic.
