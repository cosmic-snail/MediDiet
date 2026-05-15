from __future__ import annotations

import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/superpowers/specs/2026-05-15-hospital-diet-agent-recommendation-engine-design.zh.md"
OUTPUT = ROOT / "docs/superpowers/specs/2026-05-15-hospital-diet-agent-recommendation-engine-design.zh.pdf"


def register_fonts() -> tuple[str, str]:
    heading_font = "STHeiti"
    try:
        pdfmetrics.registerFont(TTFont(heading_font, "/System/Library/Fonts/STHeiti Medium.ttc"))
    except Exception:
        heading_font = "Helvetica-Bold"
    return heading_font, heading_font


HEADING_FONT, BODY_FONT = register_fonts()


class MarkdownPdf:
    def __init__(self, output: Path):
        self.output = output
        self.width, self.height = A4
        self.left = 56
        self.right = 56
        self.top = 58
        self.bottom = 58
        self.content_width = self.width - self.left - self.right
        self.c = canvas.Canvas(str(output), pagesize=A4)
        self.page = 1
        self.y = self.height - self.top
        self.title = ""

    def finish(self) -> None:
        self._footer()
        self.c.save()

    def _footer(self) -> None:
        self.c.setStrokeColor(colors.HexColor("#D8DEE9"))
        self.c.setLineWidth(0.5)
        self.c.line(self.left, 42, self.width - self.right, 42)
        self.c.setFont(BODY_FONT, 8)
        self.c.setFillColor(colors.HexColor("#64748B"))
        self.c.drawString(self.left, 28, "MediDiet 医院 Agent 助手餐食推荐引擎设计")
        self.c.drawRightString(self.width - self.right, 28, f"第 {self.page} 页")
        self.c.setFillColor(colors.black)

    def new_page(self) -> None:
        self._footer()
        self.c.showPage()
        self.page += 1
        self.y = self.height - self.top

    def ensure(self, needed: float) -> None:
        if self.y - needed < self.bottom:
            self.new_page()

    def clean_inline(self, text: str) -> str:
        text = text.replace("**", "")
        text = text.replace("`", "")
        return text

    def wrap(self, text: str, font: str, size: float, max_width: float) -> list[str]:
        text = self.clean_inline(text).strip()
        if not text:
            return []
        lines: list[str] = []
        current = ""
        for ch in text:
            tentative = current + ch
            if pdfmetrics.stringWidth(tentative, font, size) <= max_width:
                current = tentative
                continue
            if current:
                lines.append(current.rstrip())
            current = ch.lstrip()
        if current:
            lines.append(current.rstrip())
        return lines

    def add_title(self, text: str) -> None:
        self.title = text
        self.ensure(180)
        self.c.setFillColor(colors.HexColor("#0F172A"))
        lines = self.wrap(text, HEADING_FONT, 24, self.content_width)
        for line in lines:
            self.c.setFont(HEADING_FONT, 24)
            self.c.drawString(self.left, self.y, line)
            self.y -= 34
        self.c.setStrokeColor(colors.HexColor("#2563EB"))
        self.c.setLineWidth(3)
        self.c.line(self.left, self.y - 4, self.left + 160, self.y - 4)
        self.y -= 32
        self.c.setFont(BODY_FONT, 11)
        self.c.setFillColor(colors.HexColor("#475569"))
        subtitle = "中文版 PDF · 面向推荐引擎 MVP、规则治理、人工审核与可审计推荐流程"
        for line in self.wrap(subtitle, BODY_FONT, 11, self.content_width):
            self.c.drawString(self.left, self.y, line)
            self.y -= 18
        self.y -= 8

    def add_heading(self, text: str, level: int) -> None:
        styles = {
            2: (16, "#1D4ED8", 30, 20),
            3: (13, "#0F766E", 24, 16),
            4: (11.5, "#334155", 20, 14),
        }
        size, color, before, leading = styles.get(level, styles[4])
        self.ensure(before + leading + 10)
        self.y -= before * 0.35
        self.c.setFillColor(colors.HexColor(color))
        self.c.setFont(HEADING_FONT, size)
        for line in self.wrap(text, HEADING_FONT, size, self.content_width):
            self.c.drawString(self.left, self.y, line)
            self.y -= leading
        self.y -= 5
        self.c.setFillColor(colors.black)

    def add_paragraph(self, text: str) -> None:
        lines = self.wrap(text, BODY_FONT, 10.5, self.content_width)
        if not lines:
            return
        self.ensure(len(lines) * 16 + 8)
        self.c.setFont(BODY_FONT, 10.5)
        self.c.setFillColor(colors.HexColor("#111827"))
        for line in lines:
            self.c.drawString(self.left, self.y, line)
            self.y -= 16
        self.y -= 5

    def add_bullet(self, text: str, marker: str = "•", indent: int = 18) -> None:
        marker_width = 18
        max_width = self.content_width - indent - marker_width
        lines = self.wrap(text, BODY_FONT, 10.2, max_width)
        if not lines:
            return
        self.ensure(len(lines) * 15 + 5)
        self.c.setFont(BODY_FONT, 10.2)
        self.c.setFillColor(colors.HexColor("#111827"))
        if marker == "•":
            self.c.setFillColor(colors.HexColor("#2563EB"))
            self.c.circle(self.left + indent + 4, self.y + 3, 2, fill=1, stroke=0)
            self.c.setFillColor(colors.HexColor("#111827"))
        else:
            self.c.drawString(self.left + indent, self.y, marker)
        self.c.drawString(self.left + indent + marker_width, self.y, lines[0])
        self.y -= 15
        for line in lines[1:]:
            self.c.drawString(self.left + indent + marker_width, self.y, line)
            self.y -= 15
        self.y -= 3

    def add_quote(self, text: str) -> None:
        lines = self.wrap(text, BODY_FONT, 10.2, self.content_width - 28)
        height = len(lines) * 15 + 18
        self.ensure(height + 8)
        x = self.left
        y0 = self.y - height + 8
        self.c.setFillColor(colors.HexColor("#EFF6FF"))
        self.c.roundRect(x, y0, self.content_width, height, 5, fill=1, stroke=0)
        self.c.setStrokeColor(colors.HexColor("#3B82F6"))
        self.c.setLineWidth(2)
        self.c.line(x + 10, y0 + 8, x + 10, y0 + height - 8)
        self.c.setFont(BODY_FONT, 10.2)
        self.c.setFillColor(colors.HexColor("#1E3A8A"))
        self.y -= 12
        for line in lines:
            self.c.drawString(x + 24, self.y, line)
            self.y -= 15
        self.y = y0 - 10
        self.c.setFillColor(colors.black)

    def add_code(self, code: str) -> None:
        raw_lines = code.strip("\n").splitlines()
        wrapped: list[str] = []
        for raw in raw_lines:
            wrapped.extend(self.wrap(raw, BODY_FONT, 8.7, self.content_width - 28) or [""])
        height = max(1, len(wrapped)) * 13 + 18
        self.ensure(height + 8)
        x = self.left
        y0 = self.y - height + 8
        self.c.setFillColor(colors.HexColor("#F8FAFC"))
        self.c.roundRect(x, y0, self.content_width, height, 4, fill=1, stroke=0)
        self.c.setFont(BODY_FONT, 8.7)
        self.c.setFillColor(colors.HexColor("#334155"))
        self.y -= 12
        for line in wrapped:
            self.c.drawString(x + 14, self.y, line)
            self.y -= 13
        self.y = y0 - 10
        self.c.setFillColor(colors.black)

    def _center_text(self, text: str, x: float, y: float, w: float, h: float, size: float = 8.6, color: str = "#111827") -> None:
        lines: list[str] = []
        for part in text.splitlines():
            lines.extend(self.wrap(part, BODY_FONT, size, w - 12) or [""])
        total = len(lines) * (size + 3)
        yy = y + (h + total) / 2 - size
        self.c.setFont(BODY_FONT, size)
        self.c.setFillColor(colors.HexColor(color))
        for line in lines:
            tw = pdfmetrics.stringWidth(line, BODY_FONT, size)
            self.c.drawString(x + (w - tw) / 2, yy, line)
            yy -= size + 3

    def _box(self, text: str, x: float, y: float, w: float, h: float, fill: str = "#F8FAFC", stroke: str = "#CBD5E1", size: float = 8.6) -> None:
        self.c.setFillColor(colors.HexColor(fill))
        self.c.setStrokeColor(colors.HexColor(stroke))
        self.c.setLineWidth(0.8)
        self.c.roundRect(x, y, w, h, 5, fill=1, stroke=1)
        self._center_text(text, x, y, w, h, size=size)

    def _oval(self, text: str, x: float, y: float, w: float, h: float, fill: str = "#EFF6FF", stroke: str = "#60A5FA", size: float = 8.4) -> None:
        self.c.setFillColor(colors.HexColor(fill))
        self.c.setStrokeColor(colors.HexColor(stroke))
        self.c.setLineWidth(0.9)
        self.c.ellipse(x, y, x + w, y + h, fill=1, stroke=1)
        self._center_text(text, x, y, w, h, size=size, color="#0F172A")

    def _arrow(self, x1: float, y1: float, x2: float, y2: float, label: str = "") -> None:
        self.c.setStrokeColor(colors.HexColor("#64748B"))
        self.c.setLineWidth(0.7)
        self.c.line(x1, y1, x2, y2)
        dx = x2 - x1
        dy = y2 - y1
        length = max((dx * dx + dy * dy) ** 0.5, 1)
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        size = 5
        self.c.setFillColor(colors.HexColor("#64748B"))
        self.c.line(x2, y2, x2 - ux * size + px * size * 0.55, y2 - uy * size + py * size * 0.55)
        self.c.line(x2, y2, x2 - ux * size - px * size * 0.55, y2 - uy * size - py * size * 0.55)
        if label:
            self.c.setFont(BODY_FONT, 7)
            self.c.setFillColor(colors.HexColor("#475569"))
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            self.c.drawCentredString(mx, my + 4, label)

    def add_mermaid_diagram(self, code: str) -> None:
        match = re.search(r"%%\s*diagram:\s*([A-Za-z0-9_-]+)", code)
        diagram = match.group(1) if match else "generic"
        if diagram == "patient_recommendation":
            self._draw_patient_recommendation()
        elif diagram == "human_review":
            self._draw_human_review()
        elif diagram == "extension_ports":
            self._draw_extension_ports()
        else:
            self.add_code(code)

    def _draw_frame(self, title: str, height: float) -> tuple[float, float, float, float]:
        self.ensure(height + 14)
        x = self.left
        y = self.y - height
        self.c.setFillColor(colors.HexColor("#FFFFFF"))
        self.c.setStrokeColor(colors.HexColor("#D8DEE9"))
        self.c.roundRect(x, y, self.content_width, height, 7, fill=1, stroke=1)
        self.c.setFillColor(colors.HexColor("#0F172A"))
        self.c.setFont(HEADING_FONT, 10)
        self.c.drawString(x + 12, y + height - 18, title)
        self.c.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.c.line(x + 12, y + height - 26, x + self.content_width - 12, y + height - 26)
        return x, y, self.content_width, height

    def _draw_patient_recommendation(self) -> None:
        x, y, w, h = self._draw_frame("用例图 1：患者下一餐推荐", 285)
        boundary_x, boundary_y = x + 150, y + 42
        boundary_w, boundary_h = 190, 200
        self.c.setFillColor(colors.HexColor("#F8FAFC"))
        self.c.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.c.roundRect(boundary_x, boundary_y, boundary_w, boundary_h, 8, fill=1, stroke=1)
        self.c.setFont(BODY_FONT, 8)
        self.c.setFillColor(colors.HexColor("#475569"))
        self.c.drawString(boundary_x + 10, boundary_y + boundary_h - 16, "MediDiet 推荐系统")
        self._box("患者", x + 18, y + 176, 76, 34, "#F0FDFA", "#14B8A6")
        self._box("小程序", x + 18, y + 112, 76, 34, "#F0FDFA", "#14B8A6")
        self._box("拍照识别", x + 370, y + 184, 86, 32, "#FFF7ED", "#FB923C")
        self._box("菜单连接器", x + 370, y + 136, 86, 32, "#FFF7ED", "#FB923C")
        self._box("营养师审核", x + 370, y + 80, 86, 32, "#FEF2F2", "#F87171")
        self._oval("建档/确认资料", boundary_x + 28, boundary_y + 150, 132, 30)
        self._oval("记录今日摄入", boundary_x + 28, boundary_y + 112, 132, 30)
        self._oval("请求下一餐推荐", boundary_x + 28, boundary_y + 74, 132, 30)
        self._oval("查看推荐解释", boundary_x + 28, boundary_y + 36, 132, 30)
        self._oval("高风险转人工", boundary_x + 32, boundary_y - 5, 124, 28, "#FEF2F2", "#F87171")
        self._arrow(x + 94, y + 193, boundary_x + 28, boundary_y + 165)
        self._arrow(x + 94, y + 129, boundary_x + 28, boundary_y + 127)
        self._arrow(x + 94, y + 129, boundary_x + 28, boundary_y + 89)
        self._arrow(boundary_x + 160, boundary_y + 51, x + 94, y + 193)
        self._arrow(x + 370, y + 200, boundary_x + 160, boundary_y + 127, "估算")
        self._arrow(x + 370, y + 152, boundary_x + 160, boundary_y + 89, "候选")
        self._arrow(boundary_x + 156, boundary_y + 9, x + 370, y + 96, "审核")
        self.y = y - 14

    def _draw_human_review(self) -> None:
        x, y, w, h = self._draw_frame("用例图 2：营养师审核与规则治理", 260)
        boundary_x, boundary_y = x + 140, y + 44
        boundary_w, boundary_h = 210, 172
        self.c.setFillColor(colors.HexColor("#F8FAFC"))
        self.c.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.c.roundRect(boundary_x, boundary_y, boundary_w, boundary_h, 8, fill=1, stroke=1)
        self.c.setFont(BODY_FONT, 8)
        self.c.setFillColor(colors.HexColor("#475569"))
        self.c.drawString(boundary_x + 10, boundary_y + boundary_h - 16, "审核与规则治理")
        self._box("营养师/医生", x + 18, y + 150, 88, 34, "#F0FDFA", "#14B8A6")
        self._box("医院管理员", x + 18, y + 82, 88, 34, "#F0FDFA", "#14B8A6")
        self._box("推荐引擎", x + 376, y + 156, 84, 32, "#EFF6FF", "#60A5FA")
        self._box("审计日志", x + 376, y + 102, 84, 32, "#F8FAFC", "#CBD5E1")
        self._box("维护菜单", x + 376, y + 50, 84, 32, "#FFF7ED", "#FB923C")
        self._oval("查看审核队列", boundary_x + 38, boundary_y + 120, 132, 28)
        self._oval("查看 trace 和风险", boundary_x + 38, boundary_y + 84, 132, 28)
        self._oval("确认/修改/驳回", boundary_x + 38, boundary_y + 48, 132, 28)
        self._oval("发布规则包", boundary_x + 38, boundary_y + 12, 132, 28, "#ECFDF5", "#34D399")
        self._arrow(x + 106, y + 167, boundary_x + 38, boundary_y + 134)
        self._arrow(x + 106, y + 167, boundary_x + 38, boundary_y + 98)
        self._arrow(x + 106, y + 99, boundary_x + 38, boundary_y + 26)
        self._arrow(boundary_x + 170, boundary_y + 62, x + 376, y + 172)
        self._arrow(boundary_x + 170, boundary_y + 98, x + 376, y + 118)
        self._arrow(boundary_x + 170, boundary_y + 62, x + 376, y + 66)
        self.y = y - 14

    def _draw_extension_ports(self) -> None:
        x, y, w, h = self._draw_frame("用例图 3：后续扩展接口", 310)
        cx, cy = x + 190, y + 130
        self._box("推荐引擎核心\n安全门禁 / 评分\n审计追踪", cx, cy, 116, 58, "#EFF6FF", "#60A5FA", size=7.6)
        ports = [
            ("患者小程序\n推荐接口", x + 20, y + 218),
            ("拍照识别\n摄入估算", x + 20, y + 154),
            ("外卖/食堂\n菜单供应", x + 20, y + 90),
            ("HIS/EMR\n患者上下文", x + 356, y + 218),
            ("医院规则服务\n规则包", x + 356, y + 154),
            ("审核台\n人工审核", x + 356, y + 90),
            ("LLM 服务\n解释/归一化", x + 188, y + 226),
            ("审计导出\nTrace/Webhook", x + 188, y + 52),
        ]
        for label, px, py in ports:
            fill = "#F8FAFC"
            stroke = "#CBD5E1"
            if "规则" in label:
                fill, stroke = "#ECFDF5", "#34D399"
            elif "审核" in label:
                fill, stroke = "#FEF2F2", "#F87171"
            elif "LLM" in label:
                fill, stroke = "#FAF5FF", "#A78BFA"
            self._box(label, px, py, 98, 42, fill, stroke, size=7.8)
            sx, sy = px + 49, py + 21
            core_center_x, core_center_y = cx + 58, cy + 29
            if sx < cx:
                ex, ey = cx, core_center_y
            elif sx > cx + 116:
                ex, ey = cx + 116, core_center_y
            elif sy > cy + 58:
                ex, ey = core_center_x, cy + 58
            else:
                ex, ey = core_center_x, cy
            self._arrow(sx, sy, ex, ey)
        self.c.setFont(BODY_FONT, 7.5)
        self.c.setFillColor(colors.HexColor("#475569"))
        self.c.drawString(x + 18, y + 24, "原则：所有外部输入都带来源、版本、时间戳和置信度；所有患者端输出都回写 RecommendationTrace。")
        self.y = y - 14

    def add_spacer(self, amount: float = 5) -> None:
        self.y -= amount
        if self.y < self.bottom:
            self.new_page()

    def render_markdown(self, md: str) -> None:
        paragraph: list[str] = []
        in_code = False
        code_lang = ""
        code_lines: list[str] = []

        def flush_paragraph() -> None:
            nonlocal paragraph
            if paragraph:
                self.add_paragraph(" ".join(p.strip() for p in paragraph))
                paragraph = []

        for line in md.splitlines():
            stripped = line.rstrip()

            if stripped.startswith("```"):
                if in_code:
                    code = "\n".join(code_lines)
                    if code_lang == "mermaid":
                        self.add_mermaid_diagram(code)
                    else:
                        self.add_code(code)
                    code_lines = []
                    code_lang = ""
                    in_code = False
                else:
                    flush_paragraph()
                    in_code = True
                    code_lang = stripped.strip("`").strip()
                continue

            if in_code:
                code_lines.append(stripped)
                continue

            if not stripped.strip():
                flush_paragraph()
                self.add_spacer(2)
                continue

            h = re.match(r"^(#{1,4})\s+(.+)$", stripped)
            if h:
                flush_paragraph()
                level = len(h.group(1))
                text = h.group(2).strip()
                if level == 1:
                    self.add_title(text)
                else:
                    self.add_heading(text, level)
                continue

            if stripped.startswith(">"):
                flush_paragraph()
                self.add_quote(stripped.lstrip("> ").strip())
                continue

            bullet = re.match(r"^\s*-\s+(.+)$", stripped)
            if bullet:
                flush_paragraph()
                self.add_bullet(bullet.group(1).strip(), "•")
                continue

            numbered = re.match(r"^\s*(\d+)\.\s+(.+)$", stripped)
            if numbered:
                flush_paragraph()
                self.add_bullet(numbered.group(2).strip(), numbered.group(1) + ".")
                continue

            paragraph.append(stripped)

        flush_paragraph()


def main() -> int:
    if not SOURCE.exists():
        print(f"Missing source: {SOURCE}", file=sys.stderr)
        return 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf = MarkdownPdf(OUTPUT)
    pdf.render_markdown(SOURCE.read_text(encoding="utf-8"))
    pdf.finish()
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
