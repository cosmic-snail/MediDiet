from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from knowledge.expert_annotations import (
    AnnotationSplit,
    AnnotationStatus,
    append_expert_annotation,
    build_annotation_queue,
    freeze_expert_gold_annotations,
)


def create_expert_annotation_app(*, dataset_dir: Path) -> FastAPI:
    app = FastAPI(title="MediDiet Expert Annotation Workbench")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _html_page(dataset_dir)

    @app.get("/api/queue")
    def queue() -> dict[str, Any]:
        records = build_annotation_queue(dataset_dir)
        return {
            "dataset_id": dataset_dir.name,
            "record_count": len(records),
            "records": records,
            "allowed_splits": [split.value for split in AnnotationSplit],
            "allowed_statuses": [status.value for status in AnnotationStatus],
        }

    @app.post("/api/annotations")
    def save_annotation(annotation: dict[str, Any]) -> dict[str, Any]:
        record = append_expert_annotation(dataset_dir=dataset_dir, annotation=annotation)
        return {"record": record}

    @app.post("/api/freeze")
    def freeze_gold() -> dict[str, Any]:
        return freeze_expert_gold_annotations(dataset_dir=dataset_dir)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the MediDiet expert annotation workbench.")
    parser.add_argument("--dataset-dir", default="knowledge/datasets/rule_extraction_v1")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(
        create_expert_annotation_app(dataset_dir=Path(args.dataset_dir)),
        host=args.host,
        port=args.port,
    )


def _html_page(dataset_dir: Path) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MediDiet Expert Annotation</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #1f2937;
      --muted: #667085;
      --line: #d7dce3;
      --accent: #0f766e;
      --accent-2: #7c3aed;
      --danger: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    header {{
      height: 56px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 18px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }}
    header strong {{ font-size: 16px; }}
    main {{
      display: grid;
      grid-template-columns: minmax(220px, 300px) minmax(0, 1fr);
      height: calc(100vh - 56px);
    }}
    aside {{
      border-right: 1px solid var(--line);
      background: var(--panel);
      overflow: auto;
    }}
    button {{
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
      border-radius: 6px;
      padding: 8px 10px;
      cursor: pointer;
      font-size: 14px;
    }}
    button.primary {{
      border-color: var(--accent);
      background: var(--accent);
      color: white;
    }}
    button.secondary {{
      border-color: var(--accent-2);
      color: var(--accent-2);
    }}
    .doc-button {{
      width: 100%;
      text-align: left;
      border: 0;
      border-bottom: 1px solid var(--line);
      border-radius: 0;
      padding: 12px;
    }}
    .doc-button.active {{ background: #e6f4f1; }}
    .doc-button small {{
      display: block;
      color: var(--muted);
      margin-top: 4px;
      line-height: 1.3;
    }}
    section.workspace {{
      display: grid;
      grid-template-columns: minmax(320px, 1fr) minmax(360px, 520px);
      gap: 0;
      overflow: hidden;
    }}
    .source, .editor {{
      padding: 16px;
      overflow: auto;
    }}
    .source {{ border-right: 1px solid var(--line); }}
    pre {{
      white-space: pre-wrap;
      line-height: 1.5;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 12px;
      font-size: 13px;
    }}
    label {{
      display: block;
      font-size: 13px;
      color: var(--muted);
      margin: 12px 0 4px;
    }}
    input, select, textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
      font: inherit;
      background: #fff;
    }}
    textarea {{ min-height: 76px; resize: vertical; }}
    .json-area {{ min-height: 112px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }}
    .toolbar {{ display: flex; gap: 8px; align-items: center; }}
    .status {{ color: var(--muted); font-size: 13px; }}
    .error {{ color: var(--danger); }}
    .meta {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
      margin: 8px 0 12px;
    }}
    @media (max-width: 900px) {{
      main, section.workspace {{ grid-template-columns: 1fr; height: auto; }}
      aside {{ max-height: 280px; }}
      .source {{ border-right: 0; border-bottom: 1px solid var(--line); }}
    }}
  </style>
</head>
<body>
  <header>
    <strong>MediDiet Expert Annotation</strong>
    <div class="toolbar">
      <span class="status">Dataset: {dataset_dir}</span>
      <button class="secondary" id="freezeButton">Freeze Gold</button>
      <button class="primary" id="saveButton">Save</button>
    </div>
  </header>
  <main>
    <aside id="docList"></aside>
    <section class="workspace">
      <div class="source">
        <h2 id="docTitle">Loading...</h2>
        <div class="meta" id="docMeta"></div>
        <h3>Source Card</h3>
        <pre id="sourceText"></pre>
        <h3>Silver Draft</h3>
        <pre id="silverExpected"></pre>
      </div>
      <div class="editor">
        <label>Annotator</label>
        <input id="annotator" value="expert" />
        <label>Split</label>
        <select id="split">
          <option value="train">train</option>
          <option value="dev">dev</option>
          <option value="test">test</option>
          <option value="holdout">holdout</option>
        </select>
        <label>Status</label>
        <select id="annotationStatus">
          <option value="draft">draft</option>
          <option value="needs_revision">needs_revision</option>
          <option value="approved">approved</option>
        </select>
        <label>Gold Behavior</label>
        <select id="goldBehavior">
          <option value="rule">rule</option>
          <option value="suggested_concept">suggested_concept</option>
          <option value="negative">negative</option>
          <option value="contextual">contextual</option>
          <option value="conflict">conflict</option>
        </select>
        <label>Extractability</label>
        <select id="extractability">
          <option value="source_card_direct">source_card_direct</option>
          <option value="original_source_direct">original_source_direct</option>
          <option value="contextual_inference">contextual_inference</option>
          <option value="unit_conversion">unit_conversion</option>
          <option value="schema_gap">schema_gap</option>
          <option value="not_extractable">not_extractable</option>
        </select>
        <label>Condition JSON</label>
        <textarea class="json-area" id="condition">{{"kind":"condition","value":""}}</textarea>
        <label>Nutrition Limits JSON Array</label>
        <textarea class="json-area" id="nutritionLimits">[]</textarea>
        <label>Hard Exclusions JSON Array</label>
        <textarea class="json-area" id="hardExclusions">[]</textarea>
        <label>Preferred Tags JSON Array</label>
        <textarea class="json-area" id="preferredTags">[]</textarea>
        <label>Expected Atomic Concepts JSON Array</label>
        <textarea class="json-area" id="atomicConcepts">[]</textarea>
        <label>Alias Groups JSON Array</label>
        <textarea class="json-area" id="aliasGroups">[]</textarea>
        <label>Umbrella Relations JSON Array</label>
        <textarea class="json-area" id="umbrellaRelations">[]</textarea>
        <label>Evidence Quotes, one per line</label>
        <textarea id="evidenceQuotes"></textarea>
        <label>Review Notes</label>
        <textarea id="reviewNotes"></textarea>
        <p class="status" id="statusText"></p>
      </div>
    </section>
  </main>
  <script>
    let records = [];
    let activeIndex = 0;

    function parseJsonField(id) {{
      const text = document.getElementById(id).value.trim();
      if (!text) return id === "condition" ? null : [];
      return JSON.parse(text);
    }}

    function pretty(value) {{
      return JSON.stringify(value ?? null, null, 2);
    }}

    function setStatus(text, isError = false) {{
      const node = document.getElementById("statusText");
      node.textContent = text;
      node.className = isError ? "status error" : "status";
    }}

    function renderList() {{
      const list = document.getElementById("docList");
      list.innerHTML = "";
      records.forEach((record, index) => {{
        const button = document.createElement("button");
        button.className = "doc-button" + (index === activeIndex ? " active" : "");
        button.innerHTML = `${{record.doc_id}}<small>${{record.title || ""}} · ${{record.latest_annotation?.annotation_status || "unreviewed"}}</small>`;
        button.onclick = () => {{ activeIndex = index; render(); }};
        list.appendChild(button);
      }});
    }}

    function render() {{
      const record = records[activeIndex];
      if (!record) return;
      renderList();
      document.getElementById("docTitle").textContent = record.title || record.doc_id;
      document.getElementById("docMeta").innerHTML = `
        <div>doc_id: ${{record.doc_id}}</div>
        <div>source_type: ${{record.source_type}}</div>
        <div>language: ${{record.language}}</div>
        <div>hash: ${{record.source_card_hash.slice(0, 19)}}...</div>
      `;
      document.getElementById("sourceText").textContent = record.source_text;
      document.getElementById("silverExpected").textContent = pretty(record.silver_expected);
      const annotation = record.latest_annotation || record.silver_expected || {{}};
      document.getElementById("split").value = annotation.split || "dev";
      document.getElementById("annotationStatus").value = annotation.annotation_status || "draft";
      document.getElementById("goldBehavior").value = annotation.gold_behavior || annotation.expected_behavior || "rule";
      document.getElementById("extractability").value = annotation.extractability || "source_card_direct";
      document.getElementById("condition").value = pretty(annotation.condition || {{"kind":"condition","value":""}});
      document.getElementById("nutritionLimits").value = pretty(annotation.nutrition_limits || []);
      document.getElementById("hardExclusions").value = pretty(annotation.hard_exclusions || []);
      document.getElementById("preferredTags").value = pretty(annotation.preferred_tags || []);
      document.getElementById("atomicConcepts").value = pretty(annotation.expected_atomic_concepts || []);
      document.getElementById("aliasGroups").value = pretty(annotation.alias_groups || []);
      document.getElementById("umbrellaRelations").value = pretty(annotation.umbrella_relations || []);
      document.getElementById("evidenceQuotes").value = (annotation.evidence_quotes || []).join("\\n");
      document.getElementById("reviewNotes").value = annotation.review_notes || "";
      setStatus("");
    }}

    async function loadQueue() {{
      const response = await fetch("/api/queue");
      const payload = await response.json();
      records = payload.records;
      render();
    }}

    async function saveAnnotation() {{
      const record = records[activeIndex];
      try {{
        const payload = {{
          doc_id: record.doc_id,
          source_card_hash: record.source_card_hash,
          annotator: document.getElementById("annotator").value || "expert",
          split: document.getElementById("split").value,
          annotation_status: document.getElementById("annotationStatus").value,
          gold_behavior: document.getElementById("goldBehavior").value,
          extractability: document.getElementById("extractability").value,
          condition: parseJsonField("condition"),
          nutrition_limits: parseJsonField("nutritionLimits"),
          hard_exclusions: parseJsonField("hardExclusions"),
          preferred_tags: parseJsonField("preferredTags"),
          expected_atomic_concepts: parseJsonField("atomicConcepts"),
          alias_groups: parseJsonField("aliasGroups"),
          umbrella_relations: parseJsonField("umbrellaRelations"),
          evidence_quotes: document.getElementById("evidenceQuotes").value.split("\\n").map(item => item.trim()).filter(Boolean),
          review_notes: document.getElementById("reviewNotes").value,
        }};
        const response = await fetch("/api/annotations", {{
          method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify(payload),
        }});
        if (!response.ok) throw new Error(await response.text());
        setStatus("Saved.");
        await loadQueue();
      }} catch (error) {{
        setStatus(String(error), true);
      }}
    }}

    async function freezeGold() {{
      try {{
        const response = await fetch("/api/freeze", {{method: "POST"}});
        if (!response.ok) throw new Error(await response.text());
        const payload = await response.json();
        setStatus(`Frozen ${{payload.approved_annotation_count}} rows to ${{payload.gold_path}}.`);
      }} catch (error) {{
        setStatus(String(error), true);
      }}
    }}

    document.getElementById("saveButton").onclick = saveAnnotation;
    document.getElementById("freezeButton").onclick = freezeGold;
    loadQueue();
  </script>
</body>
</html>"""


if __name__ == "__main__":
    main()
