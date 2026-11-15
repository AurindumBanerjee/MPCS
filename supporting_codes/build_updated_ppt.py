"""Build the upgraded 23-slide presentation at report/PPT/BTP_PPT.pptx.

Reads report/PPT/MPCS and LocalKG.pptx strictly read-only as an OOXML template
zip, loads empirical metrics dynamically from docs/ablation_and_indexing_study.json
and docs/benchmark_indexing_tide.json, embeds verified figures from
report/PPT/figures/, enforces strict typography/layout bounds, and writes
full presenter notes for all 23 slides.
"""

from __future__ import annotations

import json
import re
import uuid
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional
from xml.sax.saxutils import escape

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PPTX = REPO_ROOT / "report" / "PPT" / "MPCS and LocalKG.pptx"
OUTPUT_PPTX = REPO_ROOT / "report" / "PPT" / "BTP_PPT.pptx"
FIGURES_DIR = REPO_ROOT / "report" / "PPT" / "figures"
MMKG_JSON = REPO_ROOT / "docs" / "ablation_and_indexing_study.json"
BANK_JSON = REPO_ROOT / "docs" / "benchmark_indexing_tide.json"

EMU_PER_INCH = 914400
SLIDE_W_IN = 13.333333
SLIDE_H_IN = 7.500000
SLIDE_W_EMU = 12192000
SLIDE_H_EMU = 6858000

SAFE_X_MIN = 0.60
SAFE_X_MAX = 12.73
SAFE_Y_MIN = 0.45
SAFE_Y_MAX = 7.15

LEFT = 0.65
RIGHT = 12.68
CONTENT_W = RIGHT - LEFT  # 12.03 in

# Color tokens harmonized with the warm academic palette
BG_WARM = "F2F1EC"
CARD_BG = "FFFFFF"
CARD_BORDER = "D9D6C8"
ALT_ROW_BG = "F7F5EE"
INK = "16140F"
CHARCOAL = "3A382F"
MUTED = "6B6858"

BLUE = "2E5B88"
BLUE_TINT = "EBF1F6"
OCHRE = "B86B28"
OCHRE_TINT = "FAF2EA"
EMERALD = "2B6E46"
EMERALD_TINT = "EBF5EE"
CRIMSON = "B83A2E"
CRIMSON_TINT = "FAECEB"

FONT_SERIF = "Georgia"
FONT_SANS = "Inter"

NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"

FORBIDDEN_TERMS = ("antigravity", "claude", "llm-assisted", "ai-assisted")


def emu(inches: float) -> int:
    """Convert inches to integer EMUs."""
    return int(round(inches * EMU_PER_INCH))


def validate_bbox(x: float, y: float, w: float, h: float, slide_num: int, label: str) -> None:
    """Ensure every shape stays strictly inside safe slide bounds."""
    if x < SAFE_X_MIN - 1e-4 or y < SAFE_Y_MIN - 1e-4:
        raise ValueError(f"Slide {slide_num} '{label}' starts outside safe margin: ({x:.3f}, {y:.3f})")
    if x + w > SAFE_X_MAX + 1e-4 or y + h > SAFE_Y_MAX + 1e-4:
        raise ValueError(
            f"Slide {slide_num} '{label}' exceeds safe bound: x+w={x+w:.3f}, y+h={y+h:.3f}"
        )
    if w <= 0 or h <= 0:
        raise ValueError(f"Slide {slide_num} '{label}' has non-positive size: ({w:.3f}, {h:.3f})")


def clean_text(text: str, context: str = "") -> str:
    """Validate text against style constraints and escape XML characters."""
    if "\u2014" in text or "\u2013" in text:
        raise ValueError(f"Forbidden em/en-dash in {context}: {text!r}")
    if "---" in text:
        raise ValueError(f"Forbidden triple-hyphen in {context}: {text!r}")
    low = text.lower()
    for term in FORBIDDEN_TERMS:
        if term in low:
            raise ValueError(f"Forbidden term '{term}' in {context}: {text!r}")
    return escape(text)


def rpr_xml(
    font: str,
    size_pt: float,
    color: str,
    bold: bool = False,
    italic: bool = False,
    spc: Optional[int] = None,
) -> str:
    """Render an <a:rPr> run property element enforcing minimum 10 pt."""
    if font not in (FONT_SERIF, FONT_SANS):
        raise ValueError(f"Invalid font '{font}'. Only Georgia and Inter are allowed.")
    if size_pt < 10.0:
        raise ValueError(f"Font size {size_pt} pt violates minimum >= 10.0 pt rule.")
    sz = int(round(size_pt * 100))
    pitch = "18" if font == FONT_SERIF else "34"
    attrs = [
        'lang="en-US"',
        f'sz="{sz}"',
        f'b="{"1" if bold else "0"}"',
        f'i="{"1" if italic else "0"}"',
        'dirty="0"',
    ]
    if spc is not None:
        attrs.append(f'spc="{spc}"')
        attrs.append('kern="0"')
    attr_str = " ".join(attrs)
    return (
        f'<a:rPr {attr_str}>'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        f'<a:latin typeface="{font}" pitchFamily="{pitch}" charset="0"/>'
        f'<a:ea typeface="{font}" pitchFamily="{pitch}" charset="-122"/>'
        f'<a:cs typeface="{font}" pitchFamily="{pitch}" charset="-120"/>'
        f"</a:rPr>"
    )


def end_para_rpr_xml(font: str, size_pt: float) -> str:
    """Render <a:endParaRPr>."""
    sz = int(round(size_pt * 100))
    return (
        f'<a:endParaRPr lang="en-US" sz="{sz}" dirty="0">'
        f'<a:latin typeface="{font}" charset="0"/>'
        f'<a:ea typeface="{font}" charset="0"/>'
        f'<a:cs typeface="{font}" charset="0"/>'
        f"</a:endParaRPr>"
    )


@dataclass
class RunSpec:
    text: str
    font: str = FONT_SANS
    size_pt: float = 13.5
    color: str = CHARCOAL
    bold: bool = False
    italic: bool = False
    spc: Optional[int] = None


@dataclass
class ParaSpec:
    runs: list[RunSpec]
    align: str = "l"
    bullet: bool = False
    line_pct: int = 120
    space_after_pt: float = 4.0


@dataclass
class SlideBuilder:
    slide_num: int
    name: str
    shapes_xml: list[str] = field(default_factory=list)
    image_rels: list[tuple[str, str]] = field(default_factory=list)  # (rId, media_name)
    _next_id: int = 2
    _next_rid: int = 3  # rId1 = slideLayout, rId2 = notesSlide

    def alloc_id(self) -> int:
        val = self._next_id
        self._next_id += 1
        return val

    def add_rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        fill: Optional[str] = None,
        border: Optional[str] = None,
        border_w_emu: int = 6350,
        rounded: bool = False,
        adj_val: int = 3500,
        label: str = "rect",
    ) -> None:
        validate_bbox(x, y, w, h, self.slide_num, label)
        sid = self.alloc_id()
        geom = (
            f'<a:prstGeom prst="roundRect"><a:avLst><a:gd name="adj" fmla="val {adj_val}"/></a:avLst></a:prstGeom>'
            if rounded
            else '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        )
        fill_xml = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else "<a:noFill/>"
        ln_xml = (
            f'<a:ln w="{border_w_emu}"><a:solidFill><a:srgbClr val="{border}"/></a:solidFill>'
            f'<a:prstDash val="solid"/></a:ln>'
            if border
            else "<a:ln/>"
        )
        self.shapes_xml.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="{escape(label)} {sid}"/>'
            f"<p:cNvSpPr/><p:nvPr/></p:nvSpPr>"
            f'<p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>'
            f"{geom}{fill_xml}{ln_xml}</p:spPr></p:sp>"
        )

    def add_textbox(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        paras: list[ParaSpec],
        anchor: str = "t",
        is_title_ph: bool = False,
        pad_lr_in: float = 0.0,
        pad_tb_in: float = 0.0,
        label: str = "textbox",
    ) -> None:
        validate_bbox(x, y, w, h, self.slide_num, label)
        sid = self.alloc_id()
        ph_xml = '<p:ph type="title"/>' if is_title_ph else ""
        p_xml_parts: list[str] = []
        for p in paras:
            if p.align not in ("l", "ctr", "r", "just"):
                raise ValueError(f"Slide {self.slide_num} '{label}' invalid OOXML align '{p.align}'")
            if p.bullet:
                ppr_inner = (
                    f'<a:lnSpc><a:spcPct val="{p.line_pct * 1000}"/></a:lnSpc>'
                    f'<a:spcAft><a:spcPts val="{int(round(p.space_after_pt * 100))}"/></a:spcAft>'
                    f'<a:buClr><a:srgbClr val="{BLUE}"/></a:buClr>'
                    f'<a:buSzPct val="100000"/>'
                    f'<a:buFont typeface="{FONT_SANS}" pitchFamily="34" charset="0"/>'
                    f'<a:buChar char="&#x2022;"/>'
                )
                ppr_attrs = f'algn="{p.align}" marL="182880" indent="-182880"'
            else:
                ppr_inner = (
                    f'<a:lnSpc><a:spcPct val="{p.line_pct * 1000}"/></a:lnSpc>'
                    f'<a:spcAft><a:spcPts val="{int(round(p.space_after_pt * 100))}"/></a:spcAft>'
                    f"<a:buNone/>"
                )
                ppr_attrs = f'algn="{p.align}" marL="0" indent="0"'

            runs_str = "".join(
                f"<a:r>{rpr_xml(r.font, r.size_pt, r.color, r.bold, r.italic, r.spc)}"
                f"<a:t>{clean_text(r.text, f'slide {self.slide_num} {label}')}</a:t></a:r>"
                for r in p.runs
            )
            last_run = p.runs[-1] if p.runs else RunSpec("")
            end_rpr = end_para_rpr_xml(last_run.font, last_run.size_pt)
            p_xml_parts.append(f"<a:p><a:pPr {ppr_attrs}>{ppr_inner}</a:pPr>{runs_str}{end_rpr}</a:p>")

        l_ins = emu(pad_lr_in)
        r_ins = emu(pad_lr_in)
        t_ins = emu(pad_tb_in)
        b_ins = emu(pad_tb_in)
        self.shapes_xml.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="{escape(label)} {sid}"/>'
            f"<p:cNvSpPr/><p:nvPr>{ph_xml}</p:nvPr></p:nvSpPr>"
            f'<p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln/></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="{l_ins}" tIns="{t_ins}" rIns="{r_ins}" '
            f'bIns="{b_ins}" rtlCol="0" anchor="{anchor}"><a:normAutofit/></a:bodyPr>'
            f'<a:lstStyle/>{"".join(p_xml_parts)}</p:txBody></p:sp>'
        )

    def add_card(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        title: Optional[str] = None,
        bullets: Optional[list[str]] = None,
        body_paras: Optional[list[ParaSpec]] = None,
        accent: Optional[str] = BLUE,
        accent_side: str = "top",
        title_size: float = 15.5,
        bullet_size: float = 13.5,
        label: str = "card",
    ) -> None:
        """Add a crisp white card with optional colored accent bar, heading, and bullets."""
        self.add_rect(x, y, w, h, fill=CARD_BG, border=CARD_BORDER, border_w_emu=6350, rounded=True, adj_val=2500, label=label)
        if accent:
            if accent_side == "top":
                self.add_rect(x + 0.14, y + 0.08, w - 0.28, 0.05, fill=accent, border=None, label=f"{label}_accent")
                inner_top = y + 0.24
                inner_left = x + 0.20
                inner_w = w - 0.40
            else:  # left accent bar
                self.add_rect(x + 0.08, y + 0.14, 0.06, h - 0.28, fill=accent, border=None, label=f"{label}_accent")
                inner_top = y + 0.18
                inner_left = x + 0.24
                inner_w = w - 0.40
        else:
            inner_top = y + 0.18
            inner_left = x + 0.20
            inner_w = w - 0.40

        paras: list[ParaSpec] = []
        if title:
            paras.append(
                ParaSpec(
                    runs=[RunSpec(title, font=FONT_SERIF, size_pt=title_size, color=INK, bold=True)],
                    line_pct=115,
                    space_after_pt=6.0,
                )
            )
        if bullets:
            for b in bullets:
                paras.append(
                    ParaSpec(
                        runs=[RunSpec(b, font=FONT_SANS, size_pt=bullet_size, color=CHARCOAL)],
                        bullet=True,
                        line_pct=120,
                        space_after_pt=5.0,
                    )
                )
        if body_paras:
            paras.extend(body_paras)

        if paras:
            self.add_textbox(
                inner_left,
                inner_top,
                inner_w,
                max(0.25, y + h - inner_top - 0.12),
                paras,
                label=f"{label}_text",
            )

    def add_kpi_card(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        value: str,
        caption: str,
        accent: str = BLUE,
        value_size: float = 28.0,
        caption_size: float = 13.0,
        accent_side: str = "left",
        label: str = "kpi",
    ) -> None:
        """Add a high-contrast KPI card."""
        paras = [
            ParaSpec(
                runs=[RunSpec(value, font=FONT_SERIF, size_pt=value_size, color=accent, bold=True)],
                line_pct=105,
                space_after_pt=3.0,
            ),
            ParaSpec(
                runs=[RunSpec(caption, font=FONT_SANS, size_pt=caption_size, color=CHARCOAL)],
                line_pct=115,
                space_after_pt=0.0,
            ),
        ]
        self.add_card(
            x, y, w, h,
            body_paras=paras,
            accent=accent,
            accent_side=accent_side,
            label=label,
        )

    def add_image_box(
        self,
        box_x: float,
        box_y: float,
        box_w: float,
        box_h: float,
        img_path: Path,
        descr: str,
        in_card: bool = True,
        pad_in: float = 0.12,
        caption: Optional[str] = None,
        header: Optional[str] = None,
        accent: Optional[str] = None,
        label: str = "image",
    ) -> None:
        """Embed a PNG preserving exact aspect ratio via PIL.Image dimensions."""
        if not img_path.exists():
            raise FileNotFoundError(f"Missing required figure: {img_path}")
        with Image.open(img_path) as im:
            px_w, px_h = im.size
        if px_w <= 0 or px_h <= 0:
            raise ValueError(f"Invalid image size for {img_path}: {px_w}x{px_h}")

        if in_card:
            self.add_rect(box_x, box_y, box_w, box_h, fill=CARD_BG, border=CARD_BORDER, border_w_emu=6350, rounded=True, adj_val=2500, label=f"{label}_frame")
            if accent:
                self.add_rect(box_x + 0.14, box_y + 0.08, box_w - 0.28, 0.05, fill=accent, label=f"{label}_accent")

        avail_x = box_x + pad_in
        avail_y = box_y + pad_in + (0.06 if (in_card and accent) else 0.0)
        avail_w = box_w - 2 * pad_in
        avail_h = box_h - 2 * pad_in - (0.06 if (in_card and accent) else 0.0)

        if header:
            self.add_textbox(
                avail_x,
                avail_y,
                avail_w,
                0.30,
                [ParaSpec([RunSpec(header, font=FONT_SERIF, size_pt=15.0, color=INK, bold=True)], line_pct=110, space_after_pt=0.0)],
                label=f"{label}_hdr",
            )
            avail_y += 0.34
            avail_h -= 0.34

        if caption:
            cap_h = 0.56
            avail_h -= (cap_h + 0.06)
            self.add_textbox(
                avail_x,
                box_y + box_h - cap_h - pad_in + 0.04,
                avail_w,
                cap_h,
                [ParaSpec([RunSpec(caption, font=FONT_SANS, size_pt=12.0, color=CHARCOAL)], line_pct=115, space_after_pt=0.0)],
                label=f"{label}_cap",
            )

        scale = min(avail_w / px_w, avail_h / px_h)
        draw_w = px_w * scale
        draw_h = px_h * scale
        draw_x = avail_x + (avail_w - draw_w) / 2.0
        draw_y = avail_y + (avail_h - draw_h) / 2.0

        validate_bbox(draw_x, draw_y, draw_w, draw_h, self.slide_num, label)
        rid = f"rId{self._next_rid}"
        self._next_rid += 1
        media_name = img_path.name
        self.image_rels.append((rid, media_name))
        sid = self.alloc_id()
        self.shapes_xml.append(
            f'<p:pic><p:nvPicPr><p:cNvPr id="{sid}" name="{escape(label)} {sid}" descr="{clean_text(descr, label)}"/>'
            f'<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
            f'<p:blipFill><a:blip r:embed="{rid}"/><a:srcRect l="0" r="0" t="0" b="0"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
            f'<p:spPr><a:xfrm><a:off x="{emu(draw_x)}" y="{emu(draw_y)}"/><a:ext cx="{emu(draw_w)}" cy="{emu(draw_h)}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
        )

    def add_table(
        self,
        x: float,
        y: float,
        w: float,
        col_widths_in: list[float],
        headers: list[str],
        rows: list[list[str]],
        row_h_in: float = 0.40,
        header_h_in: float = 0.44,
        font_pt: float = 11.0,
        alignments: Optional[list[str]] = None,
        highlight_rows: Optional[dict[int, str]] = None,
        bold_rows: Optional[set[int]] = None,
        label: str = "table",
    ) -> float:
        """Add an OOXML table with dark header (#16140F) and alternating warm rows."""
        if abs(sum(col_widths_in) - w) > 0.02:
            raise ValueError(f"Slide {self.slide_num} table '{label}' col widths {sum(col_widths_in):.3f} != {w:.3f}")
        if font_pt < 10.0:
            raise ValueError(f"Table font {font_pt} pt violates minimum >= 10.0 pt")

        total_h = header_h_in + len(rows) * row_h_in
        validate_bbox(x, y, w, total_h, self.slide_num, label)
        sid = self.alloc_id()

        if alignments is None:
            alignments = ["l"] + ["r"] * (len(headers) - 1)
        highlight_rows = highlight_rows or {}
        bold_rows = bold_rows or set()

        grid_xml = "".join(f'<a:gridCol w="{emu(cw)}"/>' for cw in col_widths_in)

        def cell_xml(
            text: str,
            fill: str,
            text_color: str,
            bold: bool,
            algn: str,
            border_color: str,
        ) -> str:
            ln_spec = (
                f'w="6350" cap="flat" cmpd="sng" algn="ctr">'
                f'<a:solidFill><a:srgbClr val="{border_color}"/></a:solidFill><a:prstDash val="solid"/>'
            )
            borders = (
                f"<a:lnL {ln_spec}</a:lnL><a:lnR {ln_spec}</a:lnR>"
                f"<a:lnT {ln_spec}</a:lnT><a:lnB {ln_spec}</a:lnB>"
            )
            return (
                f"<a:tc><a:txBody><a:bodyPr/><a:lstStyle/><a:p>"
                f'<a:pPr algn="{algn}" indent="0" marL="0"><a:lnSpc><a:spcPct val="110000"/></a:lnSpc><a:buNone/></a:pPr>'
                f'<a:r>{rpr_xml(FONT_SANS, font_pt, text_color, bold=bold)}'
                f"<a:t>{clean_text(text, f'slide {self.slide_num} {label}')}</a:t></a:r>"
                f"{end_para_rpr_xml(FONT_SANS, font_pt)}</a:p></a:txBody>"
                f'<a:tcPr marL="64008" marR="64008" marT="36576" marB="36576" anchor="ctr">'
                f'{borders}<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill></a:tcPr></a:tc>'
            )

        hdr_cells = "".join(
            cell_xml(h_txt, INK, "FFFFFF", True, alignments[idx], "3A382F")
            for idx, h_txt in enumerate(headers)
        )
        tr_parts = [f'<a:tr h="{emu(header_h_in)}">{hdr_cells}</a:tr>']

        for r_idx, row in enumerate(rows):
            bg = highlight_rows.get(r_idx, CARD_BG if r_idx % 2 == 0 else ALT_ROW_BG)
            is_bold = r_idx in bold_rows
            cells = "".join(
                cell_xml(val, bg, INK if is_bold else CHARCOAL, is_bold or idx == 0 and r_idx in highlight_rows, alignments[idx], CARD_BORDER)
                for idx, val in enumerate(row)
            )
            tr_parts.append(f'<a:tr h="{emu(row_h_in)}">{cells}</a:tr>')

        self.shapes_xml.append(
            f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{sid}" name="{escape(label)} {sid}"/>'
            f'<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr>'
            f'<p:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(total_h)}"/></p:xfrm>'
            f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">'
            f'<a:tbl><a:tblPr/><a:tblGrid>{grid_xml}</a:tblGrid>{"".join(tr_parts)}</a:tbl>'
            f"</a:graphicData></a:graphic></p:graphicFrame>"
        )
        return y + total_h

    def add_chrome(self, eyebrow: str, title: str, accent: str = BLUE, title_pt: float = 26.0) -> None:
        """Render consistent top header bar, eyebrow, title, and footer."""
        self.add_rect(LEFT, 0.48, 0.45, 0.045, fill=accent, label="accent_bar")
        self.add_textbox(
            LEFT,
            0.57,
            10.50,
            0.22,
            [ParaSpec([RunSpec(eyebrow, font=FONT_SANS, size_pt=10.5, color=MUTED, bold=True, spc=140)], line_pct=105, space_after_pt=0.0)],
            label="eyebrow",
        )
        self.add_textbox(
            LEFT,
            0.80,
            CONTENT_W,
            0.48,
            [ParaSpec([RunSpec(title, font=FONT_SERIF, size_pt=title_pt, color=INK, bold=True, spc=-25)], line_pct=110, space_after_pt=0.0)],
            is_title_ph=True,
            label="title",
        )
        self.add_textbox(
            LEFT,
            6.84,
            6.50,
            0.22,
            [ParaSpec([RunSpec("MPCS & LOCALKG  |  B.TECH PROJECT, IIT JODHPUR", font=FONT_SANS, size_pt=10.5, color=MUTED, spc=80)], line_pct=105, space_after_pt=0.0)],
            label="footer_left",
        )
        self.add_textbox(
            11.88,
            6.84,
            0.80,
            0.22,
            [ParaSpec([RunSpec(f"{self.slide_num:02d}", font=FONT_SANS, size_pt=10.5, color=MUTED, bold=True, spc=80)], align="r", line_pct=105, space_after_pt=0.0)],
            label="footer_num",
        )

    def to_xml(self) -> bytes:
        """Serialize slide XML."""
        body = (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<p:sld xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">'
            f'<p:cSld name="{escape(self.name)}">'
            f'<p:bg><p:bgPr><a:solidFill><a:srgbClr val="{BG_WARM}"/></a:solidFill></p:bgPr></p:bg>'
            f'<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            f'<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            f'{"".join(self.shapes_xml)}'
            f'</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
        )
        return body.encode("utf-8")

    def to_rels_xml(self) -> bytes:
        """Serialize slide relationship XML."""
        rels = [
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout2.xml"/>',
            f'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide" Target="../notesSlides/notesSlide{self.slide_num}.xml"/>',
        ]
        for rid, media_name in self.image_rels:
            rels.append(
                f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/{escape(media_name)}"/>'
            )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(rels)
            + "</Relationships>"
        ).encode("utf-8")


def build_notes_xml(slide_num: int, notes_text: str) -> tuple[bytes, bytes]:
    """Generate notesSlide{n}.xml and notesSlide{n}.xml.rels."""
    cleaned = clean_text(notes_text, f"notesSlide{slide_num}")
    fld_uuid = str(uuid.uuid4()).upper()
    notes_xml = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<p:notes xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">'
        f"<p:cSld><p:spTree>"
        f'<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        f'<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        f'<p:sp><p:nvSpPr><p:cNvPr id="2" name="Slide Image Placeholder 1"/><p:cNvSpPr><a:spLocks noGrp="1" noRot="1" noChangeAspect="1"/></p:cNvSpPr><p:nvPr><p:ph type="sldImg"/></p:nvPr></p:nvSpPr><p:spPr/></p:sp>'
        f'<p:sp><p:nvSpPr><p:cNvPr id="3" name="Notes Placeholder 2"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr><p:spPr/>'
        f'<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US" sz="1200" dirty="0">'
        f'<a:latin typeface="{FONT_SANS}" charset="0"/><a:ea typeface="{FONT_SANS}" charset="0"/><a:cs typeface="{FONT_SANS}" charset="0"/>'
        f'</a:rPr><a:t>{cleaned}</a:t></a:r><a:endParaRPr lang="en-US" sz="1200" dirty="0"/></a:p></p:txBody></p:sp>'
        f'<p:sp><p:nvSpPr><p:cNvPr id="4" name="Slide Number Placeholder 3"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="sldNum" sz="quarter" idx="10"/></p:nvPr></p:nvSpPr><p:spPr/>'
        f'<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:fld id="{{{fld_uuid}}}" type="slidenum"><a:rPr lang="en-US"/><a:t>{slide_num}</a:t></a:fld><a:endParaRPr lang="en-US"/></a:p></p:txBody></p:sp>'
        f'</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>'
    ).encode("utf-8")

    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesMaster" Target="../notesMasters/notesMaster1.xml"/>'
        f'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="../slides/slide{slide_num}.xml"/>'
        "</Relationships>"
    ).encode("utf-8")
    return notes_xml, rels_xml


def load_json(path: Path) -> dict:
    """Load JSON safely with explicit close."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def build_slides(mmkg: dict, bank: dict) -> list[tuple[SlideBuilder, str]]:
    """Construct all 23 slides and presenter speaker notes."""
    slides: list[tuple[SlideBuilder, str]] = []
    ds = mmkg["dataset_stats"]
    study_a = mmkg["study_a_extended_indexing_mmkg"]
    study_b1 = mmkg["study_b_mpcs_tide_ablation_mmkg"]
    study_b2 = mmkg["study_b_anytime_budgets_mmkg"]
    study_b3 = mmkg["study_b_sufficiency_routing_mmkg"]
    study_c = mmkg["study_c_personakg_ablation_mmkg"]
    bank_idx = bank["indexing_schemes"]

    # ------------------------------------------------------------------
    # Slide 01: Title Slide
    # ------------------------------------------------------------------
    s = SlideBuilder(1, "Slide 1")
    s.add_image_box(
        5.85, 0.58, 1.63, 1.48,
        FIGURES_DIR / "iitj_logo.png",
        "IIT Jodhpur Crest",
        in_card=False,
        pad_in=0.0,
        label="iitj_logo",
    )
    s.add_textbox(
        LEFT, 2.18, CONTENT_W, 0.28,
        [ParaSpec([RunSpec("B.TECH PROJECT PRESENTATION  |  IIT JODHPUR", font=FONT_SANS, size_pt=10.5, color=MUTED, bold=True, spc=160)], align="ctr", line_pct=110)],
        label="title_kicker",
    )
    s.add_textbox(
        LEFT, 2.52, CONTENT_W, 0.90,
        [ParaSpec([RunSpec("MPCS & LocalKG", font=FONT_SERIF, size_pt=44.0, color=INK, bold=True, spc=-40)], align="ctr", line_pct=105)],
        is_title_ph=True,
        label="main_title",
    )
    s.add_textbox(
        1.10, 3.45, 11.13, 0.65,
        [ParaSpec([RunSpec("A Memory-Perceptual Cognitive System with a Grounded Clinical Knowledge Graph", font=FONT_SANS, size_pt=15.0, color=CHARCOAL)], align="ctr", line_pct=120)],
        label="subtitle",
    )
    s.add_rect(5.85, 4.25, 1.63, 0.045, fill=BLUE, label="hero_divider")
    s.add_card(
        2.15, 4.55, 9.03, 1.90,
        accent=BLUE,
        accent_side="top",
        body_paras=[
            ParaSpec([RunSpec("Aurindum Banerjee (B23CS1006)  &  Lokesh Motwani (B23CS1033)", font=FONT_SERIF, size_pt=16.0, color=INK, bold=True)], align="ctr", line_pct=120, space_after_pt=6.0),
            ParaSpec([RunSpec("Department of Computer Science and Engineering, IIT Jodhpur", font=FONT_SANS, size_pt=13.5, color=CHARCOAL)], align="ctr", line_pct=115, space_after_pt=6.0),
            ParaSpec([RunSpec("Supervisor: Dr. Romi Banerjee", font=FONT_SANS, size_pt=13.5, color=BLUE, bold=True)], align="ctr", line_pct=115, space_after_pt=0.0),
        ],
        label="author_card",
    )
    notes_01 = (
        "Good morning. We present MPCS and LocalKG, our B.Tech project under Dr. Romi Banerjee in the Department of CSE at IIT Jodhpur. "
        "The work couples a fast, safety-gated memory-perceptual cognitive engine with a typed clinical knowledge graph in which every symptom carries a verbatim source citation. "
        "Over the next slides we cover the architecture, six retrieval layers, graph construction, and empirical evaluations across both Bank v3 and the Materia Medica knowledge graph."
    )
    slides.append((s, notes_01))

    # ------------------------------------------------------------------
    # Slide 02: Problem
    # ------------------------------------------------------------------
    s = SlideBuilder(2, "Slide 2")
    s.add_chrome("PROBLEM", "Why LLM-Only Decision Support Falls Short", accent=CRIMSON)
    problems = [
        ("01  Traceability", CRIMSON, [
            "Generated text detaches from sources",
            "Fluent claims hide unsupported steps",
            "Clinical review demands exact citations",
        ]),
        ("02  Hard Constraints", OCHRE, [
            "Cosine scores blur critical attributes",
            "9/10 match fails on thermal state",
            "Safety rules require exact-match gates",
        ]),
        ("03  Latency", BLUE, [
            "Autoregressive decoding scales with length",
            "No strict deadline on decision time",
            "High GPU cost for routine triage",
        ]),
    ]
    cw = (CONTENT_W - 0.60) / 3.0
    for idx, (heading, acc, pts) in enumerate(problems):
        cx = LEFT + idx * (cw + 0.30)
        s.add_card(cx, 1.50, cw, 3.85, title=heading, bullets=pts, accent=acc, title_size=16.0, bullet_size=14.0, label=f"prob_{idx}")
    s.add_card(
        LEFT, 5.58, CONTENT_W, 0.95,
        accent=INK,
        accent_side="left",
        body_paras=[
            ParaSpec([
                RunSpec("Engineering Goal: ", font=FONT_SERIF, size_pt=15.0, color=INK, bold=True),
                RunSpec("Enforce safety constraints structurally, expose verbatim evidence, and respond in ~4 ms on a single CPU core.", font=FONT_SANS, size_pt=13.5, color=CHARCOAL),
            ], line_pct=120, space_after_pt=0.0)
        ],
        label="prob_goal",
    )
    notes_02 = (
        "Standard retrieval-augmented language models excel at fluent prose, yet fail three requirements in high-stakes decision support. "
        "First, generated answers cannot always be traced back to the exact passage that justifies them. "
        "Second, dense similarity scores treat all attributes smoothly, so matching nine of ten features can still override a single safety-critical feature like hot versus cold contact. "
        "Third, autoregressive generation lacks a fixed latency upper bound, motivating our explicit, non-LLM decision architecture."
    )
    slides.append((s, notes_02))

    # ------------------------------------------------------------------
    # Slide 03: Solution
    # ------------------------------------------------------------------
    s = SlideBuilder(3, "Slide 3")
    s.add_chrome("SOLUTION", "Explicit, Inspectable Neuro-Symbolic Architecture", accent=BLUE)
    s.add_textbox(
        LEFT, 1.38, CONTENT_W, 0.32,
        [ParaSpec([RunSpec("Two cooperating subsystems coupled by a deterministic safety and provenance bridge.", font=FONT_SANS, size_pt=14.0, color=MUTED)], line_pct=110)],
        label="sol_sub",
    )
    sol_cards = [
        ("MPCS Cognitive Agent", BLUE, [
            "4-channel Z-number sensory percepts",
            "7 first-match safety reflex rules",
            "6-layer episodic indexing & TIDE",
            "Reward penalty & threshold learning",
        ]),
        ("LocalKG Knowledge Graph", OCHRE, [
            f"{ds['graph_nodes']:,} nodes, {ds['graph_links']:,} typed edges",
            "Hahnemann corpus + 21 PubMed records",
            "Verbatim substring quote on every node",
            "3D VAD affect & grade severity W",
        ]),
        ("Neuro-Symbolic Bridge", EMERALD, [
            "Stage 1 regex red-flag halt",
            "4-channel clinical modality mapping",
            "Dual-persona + G9 TIDE decision fusion",
            "3.91 ms mean single-CPU response",
        ]),
    ]
    for idx, (heading, acc, pts) in enumerate(sol_cards):
        cx = LEFT + idx * (cw + 0.30)
        s.add_card(cx, 1.82, cw, 3.65, title=heading, bullets=pts, accent=acc, title_size=15.5, bullet_size=13.5, label=f"sol_{idx}")
    s.add_card(
        LEFT, 5.66, CONTENT_W, 0.86,
        accent=EMERALD,
        accent_side="left",
        body_paras=[
            ParaSpec([
                RunSpec("Zero GPU & Full Auditability: ", font=FONT_SERIF, size_pt=14.5, color=INK, bold=True),
                RunSpec("Every action is grounded in stored episodes and verbatim clinical passages.", font=FONT_SANS, size_pt=13.5, color=CHARCOAL),
            ], line_pct=115, space_after_pt=0.0)
        ],
        label="sol_strip",
    )
    notes_03 = (
        "Our solution separates fast, safety-constrained control from structured clinical knowledge while keeping every step inspectable. "
        "MPCS perceives four sensory modalities with Z-number confidence weights, executes reflex checks, retrieves episodes across six layers, and adapts via reward feedback. "
        "LocalKG extracts a 1,106-node, 2,024-edge typed clinical graph where every symptom retains its exact source quote, and the bridge fuses both subsystems within roughly 4 milliseconds on CPU."
    )
    slides.append((s, notes_03))

    # ------------------------------------------------------------------
    # Slide 04: Objectives & Key Contributions
    # ------------------------------------------------------------------
    s = SlideBuilder(4, "Slide 4")
    s.add_chrome("OBJECTIVES & CONTRIBUTIONS", "Project Scope and Core Engineering Contributions", accent=BLUE)
    w2 = (CONTENT_W - 0.31) / 2.0
    s.add_card(
        LEFT, 1.48, w2, 5.02,
        title="Five Core Objectives",
        accent=BLUE,
        title_size=16.0,
        bullet_size=14.0,
        bullets=[
            "Build perception-decision-reward over Z-number percepts",
            "Compare 6 retrieval layers on safety, RAM, and latency",
            "Extract typed KG from historical + PubMed texts",
            "Design dual-persona query engine with one threshold",
            "Couple KG and MPCS under automated tests",
        ],
        label="obj_card",
    )
    s.add_card(
        LEFT + w2 + 0.31, 1.48, w2, 5.02,
        title="Key Contributions",
        accent=OCHRE,
        title_size=16.0,
        bullet_size=14.0,
        bullets=[
            "MPCS core: 7 reflexes, off-policy penalty, adaptive tau",
            "Layered cascade (dlCBF through G9 TIDE)",
            "LocalKG: 9-type ontology, hybrid auditor, VAD & W",
            "O(1)-indexed dual-persona BFS (theta 0.70 vs 0.35)",
            "Unified Bank v3 & MMKG (N=953) empirical suites",
        ],
        label="contrib_card",
    )
    notes_04 = (
        "The project targeted five concrete objectives spanning cognitive modeling, memory indexing, clinical graph extraction, thresholded querying, and end-to-end integration. "
        "Each contribution is implemented as a standalone, testable Python module: later MPCS layers import only earlier ones, enabling isolated ablation across identical memory banks. "
        "On the knowledge side, LocalKG pairs a nine-entity ontology with hybrid LLM auditing and deterministic benchmarks on both synthetic scenes and real extracted Materia Medica data."
    )
    slides.append((s, notes_04))

    # ------------------------------------------------------------------
    # Slide 05: System Overview
    # ------------------------------------------------------------------
    s = SlideBuilder(5, "Slide 5")
    s.add_chrome("SYSTEM OVERVIEW", "Three Cooperating Subsystems", accent=BLUE)
    s.add_image_box(
        LEFT, 1.44, 7.20, 5.10,
        FIGURES_DIR / "fig01_architecture.png",
        "Overall MPCS and LocalKG Architecture",
        accent=BLUE,
        label="fig01",
    )
    rx = LEFT + 7.42
    rw = RIGHT - rx
    subsystems = [
        ("1. MPCS Agent (Model/)", BLUE, [
            "4-channel Z-number percept input",
            "Reflex -> 6-layer retrieval -> reward",
            "5 actions: ignore to withdraw",
        ]),
        ("2. LocalKG (LocalKG/)", OCHRE, [
            "Ingests Materia Medica & PubMed",
            f"{ds['graph_nodes']:,} nodes, {ds['graph_links']:,} typed edges",
            "Dual-persona BFS subgraph engine",
        ]),
        ("3. Bridge (09_localrag_bridge)", EMERALD, [
            "Red-flag safety halt + dlCBF check",
            "4-channel modality & VAD fusion",
            "Returns ranked remedies + quotes",
        ]),
    ]
    for idx, (heading, acc, pts) in enumerate(subsystems):
        cy = 1.44 + idx * 1.74
        s.add_card(rx, cy, rw, 1.62, title=heading, bullets=pts, accent=acc, accent_side="left", title_size=15.0, bullet_size=13.0, label=f"sub_{idx}")
    notes_05 = (
        "Figure 3.1 illustrates how the three subsystems interact at runtime. "
        "On the left, the MPCS cognitive agent processes multimodal percepts through prioritized reflexes, six layered memory filters, deliberation, and episodic storage. "
        "On the right, LocalKG transforms historical Materia Medica and PubMed abstracts into a typed graph served by the dual-persona query engine, while the bridge at the bottom routes queries to both and merges their outputs with cited evidence."
    )
    slides.append((s, notes_05))

    # ------------------------------------------------------------------
    # Slide 06: MPCS Cognitive Engine
    # ------------------------------------------------------------------
    s = SlideBuilder(6, "Slide 6")
    s.add_chrome("MPCS COGNITIVE ENGINE", "One Cognitive Step: Percept to Stored Episode", accent=BLUE)
    s.add_image_box(
        LEFT, 1.42, CONTENT_W, 2.52,
        FIGURES_DIR / "fig02_cognitive_step.png",
        "One cognitive step of the MPCS engine",
        accent=BLUE,
        label="fig02",
    )
    eng_cards = [
        ("7 Ordered Reflex Rules", CRIMSON, [
            "First-match wins bypass deliberation",
            "thermal=hot or impact -> withdraw",
            "alarm or smoke -> alert; sets hard slots",
        ]),
        ("Deliberation (k=5, lambda=0.99)", BLUE, [
            "Min-confidence Z-number similarity",
            "Top k=5 per action, decay lambda=0.99",
            "Novelty-scaled eps-greedy + hesitate",
        ]),
        ("Reward & Expert Teaching", EMERALD, [
            "Memory reward + off-policy penalty",
            "Threshold tau adapts (eta=0.01)",
            "Expert teach stored at 0.95 (3.0x)",
        ]),
    ]
    for idx, (heading, acc, pts) in enumerate(eng_cards):
        cx = LEFT + idx * (cw + 0.30)
        s.add_card(cx, 4.10, cw, 2.44, title=heading, bullets=pts, accent=acc, title_size=15.0, bullet_size=13.0, label=f"eng_{idx}")
    notes_06 = (
        "Every step in MPCS converts four sensory channels into Z-number value-confidence pairs and computes similarity using minimum confidence so exact repeats score 1.0. "
        "Seven ordered reflex rules immediately intercept hazardous inputs like hot surfaces or alarms, and those same features define the default hard-slot set for downstream filtering. "
        "Otherwise, deliberation scores each action from its top k=5 memories with temporal decay lambda=0.99, updates the action threshold tau from reward feedback, and accepts expert corrections at reward 0.95 with a 3.0x weight boost."
    )
    slides.append((s, notes_06))

    # ------------------------------------------------------------------
    # Slide 07: Six-Layer Retrieval Cascade
    # ------------------------------------------------------------------
    s = SlideBuilder(7, "Slide 7")
    s.add_chrome("RETRIEVAL CASCADE", "Six-Layer Retrieval Cascade & Empirical Gains", accent=BLUE)
    s.add_image_box(
        LEFT, 1.44, 4.40, 5.10,
        FIGURES_DIR / "fig03_retrieval_cascade.png",
        "Six-layer retrieval cascade",
        accent=BLUE,
        label="fig03",
    )
    tx = LEFT + 4.62
    tw = RIGHT - tx
    dlcbf = bank_idx["Counting Bloom (dlCBF Gate)"]
    g5 = bank_idx["G5: HyST (Hard Slot + Soft Kernel)"]
    g7 = bank_idx["G7: SHMF (Auto-Relaxed Filter)"]
    g8 = bank_idx["G8: KERL (SHMF + Safety + Graph)"]
    g9 = bank_idx["G9: TIDE (Spreading Activation)"]
    cascade_rows = [
        ["L1: dlCBF", f"4-table Bloom hint; {dlcbf['space_kb']:.1f} KB, {dlcbf['latency_mean_ms']:.3f} ms exact match"],
        ["L2: G5 HyST", f"Hard-slot gate; Bank v3 unsafe drops to {g5['unsafe_clean']:.1f}%"],
        ["L3: G6 HMGI", "Modality partitions + episode edges trim scan scope"],
        ["L4: G7 SHMF", f"Relaxes 18.3% empty HyST pools; {g7['accuracy_clean']:.1f}% clean acc."],
        ["L5: G8 KERL", f"Near-miss guard + 3-head fusion; {g8['unsafe_clean']:.1f}% clean unsafe"],
        ["L6: G9 TIDE", f"Anytime 3-hop activation + routing ({g9['latency_mean_ms']:.2f} ms)"],
    ]
    tbl_end = s.add_table(
        tx, 1.44, tw,
        [1.55, tw - 1.55],
        ["Layer", "Mechanism & Role (Bank v3 Verified)"],
        cascade_rows,
        row_h_in=0.60,
        header_h_in=0.46,
        font_pt=11.5,
        alignments=["l", "l"],
        highlight_rows={1: EMERALD_TINT, 5: BLUE_TINT},
        bold_rows={1, 5},
        label="cascade_tbl",
    )
    s.add_card(
        tx, tbl_end + 0.16, tw, 6.54 - (tbl_end + 0.16),
        accent=OCHRE,
        accent_side="left",
        body_paras=[
            ParaSpec([
                RunSpec("Modular Dependency Invariant: ", font=FONT_SERIF, size_pt=14.0, color=INK, bold=True),
                RunSpec("Each folder (04_hyst to 08_tide) imports only earlier layers for controlled ablation.", font=FONT_SANS, size_pt=12.5, color=CHARCOAL),
            ], line_pct=115, space_after_pt=0.0)
        ],
        label="cascade_note",
    )
    notes_07 = (
        "To resolve both linear-scan scaling and unsafe soft-similarity voting, MPCS stacks six retrieval layers in strict dependency order. "
        "The d-left Counting Bloom Filter gives an 8.8 KB, 17-microsecond exact-repeat hint, while HyST enforces exact hard-slot matches to cut unsafe actions down to 1.2 percent on Bank v3. "
        "HMGI partitions memory by active modalities, SHMF relaxes constraints when strict filtering returns zero candidates, KERL guards near-misses across modalities, and TIDE adds time-bounded spreading activation."
    )
    slides.append((s, notes_07))

    # ------------------------------------------------------------------
    # Slide 08: G9 TIDE
    # ------------------------------------------------------------------
    s = SlideBuilder(8, "Slide 8")
    s.add_chrome("LAYER 6: G9 TIDE", "G9 TIDE: Time-Bounded Spreading Activation", accent=OCHRE)
    tide_cards = [
        ("1. Salience Seeding (beta=0.8)", BLUE, [
            "A^(0) = sim(Q, M) * (1 + beta * arousal) * boost",
            "High-arousal cues amplify seed spread",
            "Seeds < 5% of peak are pruned",
        ]),
        ("2. 3-Hop Propagation (gamma=0.5, d=0.2)", OCHRE, [
            "Spreads 3 hops over prev/action/object/place",
            "Out-degree normalized with gamma = 0.5 decay",
            "ACT-R recency (1 + dt)^(-0.2), <= 80 nodes",
        ]),
        ("3. Sufficiency Routing", EMERALD, [
            "DIRECT: lead >= 0.25 and support >= 0.80",
            "SUBGRAPH: returns active episodes to audit",
            "UNGROUNDED: zero support -> observe",
        ]),
        ("4. Anytime Urgent Deadline", CRIMSON, [
            "Reads strongest seeds up to B or 2 ms",
            "Background passive thread checks full read",
            "Logs disagreements onto stored episode",
        ]),
    ]
    q_w = (CONTENT_W - 0.31) / 2.0
    q_h = 2.42
    for idx, (heading, acc, pts) in enumerate(tide_cards):
        col = idx % 2
        row = idx // 2
        cx = LEFT + col * (q_w + 0.31)
        cy = 1.48 + row * (q_h + 0.24)
        s.add_card(cx, cy, q_w, q_h, title=heading, bullets=pts, accent=acc, accent_side="left", title_size=15.5, bullet_size=13.5, label=f"tide_{idx}")
    notes_08 = (
        "Layer 6, TIDE, governs how surviving candidates are read and bounded at inference time. "
        "Admitted seeds are scaled by arousal salience with beta=0.8 and spread over three hops with hop decay gamma=0.5, ACT-R recency decay d=0.2, and a cap of 80 active nodes. "
        "When urgent mode is active, TIDE reads top-activated candidates first until a budget B or 2-millisecond deadline expires, while a passive thread checks full-read agreement and logs discrepancies; otherwise it routes queries to DIRECT, SUBGRAPH, or UNGROUNDED."
    )
    slides.append((s, notes_08))

    # ------------------------------------------------------------------
    # Slide 09: LocalKG Construction
    # ------------------------------------------------------------------
    s = SlideBuilder(9, "Slide 9")
    s.add_chrome("LOCALKG CONSTRUCTION", "LocalKG: Historical Text to Typed Clinical Graph", accent=OCHRE)
    s.add_image_box(
        LEFT, 1.42, 8.05, 2.48,
        FIGURES_DIR / "fig04_localkg_pipeline.png",
        "LocalKG ingestion pipeline",
        accent=OCHRE,
        label="fig04",
    )
    kx = LEFT + 8.25
    kw = RIGHT - kx
    s.add_kpi_card(
        kx, 1.42, kw, 1.16,
        f"{ds['graph_nodes']:,}",
        "Nodes across 9 typed ontology classes",
        accent=BLUE,
        value_size=28.0,
        caption_size=13.0,
        label="kpi_nodes",
    )
    s.add_kpi_card(
        kx, 2.74, kw, 1.16,
        f"{ds['graph_links']:,}",
        "Edges across 12 clinical relation types",
        accent=OCHRE,
        value_size=28.0,
        caption_size=13.0,
        label="kpi_edges",
    )
    lkg_cards = [
        ("Sources & Provenance", BLUE, [
            "Hahnemann corpus (30 remedies)",
            "21 PubMed records separated",
            "Exact source quote per symptom",
        ]),
        ("Ontology & VAD Space", OCHRE, [
            "623 physical, 195 affective, 128 mod.",
            "Affective nodes in VAD [0,1]^3",
            "6 cognitive domains via cue lexicon",
        ]),
        ("Deterministic Weight W", EMERALD, [
            "W in [0,3]: G (40%) + severity S (30%)",
            "Peak arousal (20%) + conf. (10%)",
            "Content-hash LLM cache",
        ]),
    ]
    for idx, (heading, acc, pts) in enumerate(lkg_cards):
        cx = LEFT + idx * (cw + 0.30)
        s.add_card(cx, 4.08, cw, 2.46, title=heading, bullets=pts, accent=acc, title_size=15.0, bullet_size=13.0, label=f"lkg_{idx}")
    notes_09 = (
        "LocalKG converts unstructured Materia Medica texts and 21 modern PubMed abstracts into a typed clinical graph while strictly separating historical and modern provenance. "
        "Each chunk passes through OCR cleaning, schema-validated extraction requiring an exact substring evidence quote, alias resolution, VAD affect placement, and symptom weighting W in [0, 3]. "
        "The final cleaned graph contains 1,106 nodes across 9 ontology types and 2,024 edges across 12 relation types, rebuilt deterministically from a content-hash cache."
    )
    slides.append((s, notes_09))

    # ------------------------------------------------------------------
    # Slide 10: LocalKG Extraction Benchmark
    # ------------------------------------------------------------------
    s = SlideBuilder(10, "Slide 10")
    s.add_chrome("EXTRACTION BENCHMARK", "Gold-Set Extraction: Rule-Based vs. Model vs. Hybrid", accent=OCHRE)
    extract_headers = ["Method", "Recall", "Precision", "F1", "Symptoms", "Failed Chunks"]
    extract_rows = [
        ["Rule-based (Regex & Punct.)", "61.5%", "4.0%", "7.5%", "401", "0"],
        ["Model-only (gpt-oss-120b)", "80.8%", "4.9%", "9.2%", "432", "24 (21%)"],
        ["Hybrid (Rule + LLM Audit)", "80.8%", "5.4%", "10.1%", "388", "0"],
    ]
    tbl_end = s.add_table(
        LEFT, 1.44, CONTENT_W,
        [3.60, 1.45, 1.55, 1.40, 1.75, 2.28],
        extract_headers,
        extract_rows,
        row_h_in=0.52,
        header_h_in=0.48,
        font_pt=12.0,
        alignments=["l", "r", "r", "r", "r", "r"],
        highlight_rows={2: EMERALD_TINT},
        bold_rows={2},
        label="extract_tbl",
    )
    s.add_textbox(
        LEFT, tbl_end + 0.14, CONTENT_W, 0.30,
        [ParaSpec([RunSpec("Table 6.2 Gold Set: 26 keynote symptoms over 8 remedies (relative precision: extractors emit all chunk symptoms).", font=FONT_SANS, size_pt=12.5, color=MUTED, italic=True)], line_pct=110)],
        label="extract_sub",
    )
    ext_cards = [
        ("Rule-Based: 61.5% R / 0 Fail", BLUE, [
            "100% offline, verbatim-grounded",
            "Splits abbreviations (e.g. 'St.')",
            "Sensitive to section heading drift",
        ]),
        ("Model-Only: 80.8% R / 21% Fail", CRIMSON, [
            "gpt-oss-120b handles archaic text",
            "24 chunks failed JSON schema check",
            "Timeouts & truncated outputs block",
        ]),
        ("Hybrid: 80.8% R / 10.1% F1", EMERALD, [
            "Audits rule candidates, zero failures",
            "Prunes noise (432 -> 388 symptoms)",
            "Fixes mis-typed emotional terms",
        ]),
    ]
    for idx, (heading, acc, pts) in enumerate(ext_cards):
        cx = LEFT + idx * (cw + 0.30)
        s.add_card(cx, 4.02, cw, 2.50, title=heading, bullets=pts, accent=acc, title_size=15.0, bullet_size=13.5, label=f"ext_{idx}")
    notes_10 = (
        "We benchmarked three extraction strategies on a gold set of 26 keynote symptoms across 8 remedies from Boericke's Materia Medica. "
        "Pure rule-based extraction never fails a batch and guarantees verbatim spans, but achieves only 61.5 percent recall due to abbreviation splits and heading noise. "
        "Pure gpt-oss-120b reaches 80.8 percent recall but fails schema validation on 24 chunks, or 21 percent; our hybrid design lets the LLM audit grounded rule candidates, retaining 80.8 percent recall, raising F1 to 10.1 percent, and guaranteeing zero failed chunks."
    )
    slides.append((s, notes_10))

    # ------------------------------------------------------------------
    # Slide 11: LocalKG Structure & Views
    # ------------------------------------------------------------------
    s = SlideBuilder(11, "Slide 11")
    s.add_chrome("GRAPH STRUCTURE & VIEWS", "LocalKG Relation Profile & Interactive Graph Views", accent=OCHRE)
    views = [
        (
            FIGURES_DIR / "fig05_kg_edge_stats.png",
            f"Edges by Relation ({ds['graph_links']:,})",
            "640 physical, 555 body region, 211 affective, 197 domains, 146 agg., 50 amel.",
            BLUE,
            "Edge counts across 12 relation types",
        ),
        (
            FIGURES_DIR / "kg_single_remedy.png",
            "Arnica montana (59n / 93e)",
            "Radial remedy view with left entity filter and right provenance panel.",
            OCHRE,
            "Single-remedy view for Arnica montana",
        ),
        (
            FIGURES_DIR / "kg_full.png",
            f"Full LocalKG ({ds['graph_nodes']:,}n / {ds['graph_links']:,}e)",
            "Galaxy layout placing 41 remedies around shared clinical symptom hubs.",
            EMERALD,
            "Full Materia Medica knowledge graph view",
        ),
    ]
    for idx, (img_p, hdr, cap, acc, desc) in enumerate(views):
        cx = LEFT + idx * (cw + 0.30)
        s.add_image_box(
            cx, 1.44, cw, 5.10,
            img_p,
            desc,
            in_card=True,
            pad_in=0.14,
            header=hdr,
            caption=cap,
            accent=acc,
            label=f"kg_view_{idx}",
        )
    notes_11 = (
        "These three views summarize the structure of the completed LocalKG graph. "
        "On the left, physical symptoms, body-region links, affective symptoms, cognitive domains, and aggravating or ameliorating modalities account for the vast majority of the 2,024 edges. "
        "In the center and right, our interactive HTML visualizer renders both focused single-remedy views like Arnica montana with 59 nodes and 93 edges and the full 1,106-node galaxy showing shared clinical hubs across remedies."
    )
    slides.append((s, notes_11))

    # ------------------------------------------------------------------
    # Slide 12: PersonaQueryEngine
    # ------------------------------------------------------------------
    s = SlideBuilder(12, "Slide 12")
    s.add_chrome("DUAL-PERSONA QUERY ENGINE", "PersonaQueryEngine: Threshold-Based Subgraph Retrieval", accent=BLUE)
    s.add_image_box(
        LEFT, 1.42, CONTENT_W, 2.28,
        FIGURES_DIR / "fig06_persona_partition.png",
        "Dual-threshold partition of graph nodes",
        accent=BLUE,
        label="fig06",
    )
    persona_headers = ["Engine", "Mean", "p50", "p95", "Speed-up"]
    persona_rows = [
        ["Linear-scan baseline", "3.65 ms", "3.16 ms", "6.85 ms", "1.00x"],
        ["Confident (theta=0.70)", "1.43 ms", "1.07 ms", "3.62 ms", "2.56x"],
        ["Exploratory (theta=0.35)", "1.95 ms", "1.52 ms", "4.52 ms", "1.87x"],
    ]
    tbl_end = s.add_table(
        LEFT, 3.86, 7.00,
        [2.75, 1.05, 1.00, 1.00, 1.20],
        persona_headers,
        persona_rows,
        row_h_in=0.52,
        header_h_in=0.46,
        font_pt=11.5,
        alignments=["l", "r", "r", "r", "r"],
        highlight_rows={1: BLUE_TINT, 2: OCHRE_TINT},
        bold_rows={1},
        label="persona_tbl",
    )
    s.add_textbox(
        LEFT, tbl_end + 0.12, 7.00, 0.35,
        [ParaSpec([RunSpec("Table 9.8: 8 clinical archetype queries x 50 runs = 400 calls (1,106 nodes, 2,024 edges).", font=FONT_SANS, size_pt=12.0, color=MUTED, italic=True)], line_pct=110)],
        label="persona_note",
    )
    s.add_card(
        LEFT + 7.22, 3.86, RIGHT - (LEFT + 7.22), 2.66,
        title="Retrieval & Pruning Mechanics",
        accent=BLUE,
        title_size=15.0,
        bullet_size=13.0,
        bullets=[
            "2,236-token O(1) inverted seed index",
            "Active-frontier BFS (delta=0.58, <=2 hops)",
            "Confident prunes 99.7% (3 / 1,106 nodes)",
            "Exploratory keeps 42 nodes for comparison",
        ],
        label="persona_mech",
    )
    notes_12 = (
        "PersonaQueryEngine answers free-text clinical queries using a single activation threshold to trade precision for differential breadth. "
        "A 2,236-token inverted index seeds active-frontier spreading activation across at most two hops with decay delta=0.58, discarding pruned nodes before Pydantic object construction. "
        "Across 400 archetype calls, the confident persona at theta=0.70 achieves 1.43 milliseconds mean latency and a 2.56x speed-up over linear scan, while the exploratory persona at theta=0.35 retains related remedies in 1.95 milliseconds."
    )
    slides.append((s, notes_12))

    # ------------------------------------------------------------------
    # Slide 13: Neuro-Symbolic Bridge & Clinical Studio UI
    # ------------------------------------------------------------------
    s = SlideBuilder(13, "Slide 13")
    s.add_chrome("BRIDGE & CLINICAL STUDIO UI", "Four-Stage Neuro-Symbolic Bridge & Studio Interface", accent=EMERALD)
    s.add_image_box(
        LEFT, 1.40, CONTENT_W, 1.92,
        FIGURES_DIR / "fig07_bridge_stages.png",
        "Four stages of the neuro-symbolic bridge",
        accent=EMERALD,
        label="fig07",
    )
    s.add_image_box(
        LEFT, 3.48, 6.80, 3.06,
        FIGURES_DIR / "ui_pipeline.png",
        "Clinical Studio web interface showing four bridge panels",
        accent=BLUE,
        label="ui_pipe",
    )
    s.add_card(
        LEFT + 7.00, 3.48, RIGHT - (LEFT + 7.00), 3.06,
        title="Pipeline Guarantees & Tests",
        accent=EMERALD,
        accent_side="left",
        title_size=15.5,
        bullet_size=13.5,
        bullets=[
            "Stage 1 regex red-flag halt + 30 us dlCBF",
            "4-channel modality map -> G9 TIDE + KG fusion",
            "3.91 ms mean / 5.41 ms p95 (92.4%-99.4% pruned)",
            "5/5 bridge & 33/33 unit tests pass",
        ],
        label="bridge_card",
    )
    notes_13 = (
        "The neuro-symbolic bridge orchestrates four stages for every clinical query. "
        "Stage 1 checks emergency red flags such as chest pain or stroke, immediately halting deliberation on a match, while running a 30-microsecond Bloom filter check. "
        "Stages 2 through 4 query PersonaQueryEngine, map modifying words into the 4-channel MPCS percept, fuse G9 TIDE and somatic VAD scores, and return verbatim citations in 3.91 ms mean latency, verified by 5/5 bridge tests and 33/33 unit tests."
    )
    slides.append((s, notes_13))

    # ------------------------------------------------------------------
    # Slide 14: Dual Evaluation Benchmarks
    # ------------------------------------------------------------------
    s = SlideBuilder(14, "Slide 14")
    s.add_chrome("EVALUATION BENCHMARKS", "Dual Evaluation: Synthetic Bank v3 & Materia Medica KG", accent=BLUE)
    s.add_card(
        LEFT, 1.44, w2, 3.00,
        title="Benchmark I: Synthetic Bank v3",
        accent=BLUE,
        title_size=16.0,
        bullet_size=13.5,
        bullets=[
            f"{bank['bank_records']} canonical archetype episode records",
            "480 clean + 480 perturbed noisy queries",
            "5 actions (ignore, observe, approach, alert, withdraw)",
            "Unsafe = alert/withdraw mispredicted approach/ignore",
        ],
        label="bench_bank",
    )
    s.add_card(
        LEFT + w2 + 0.31, 1.44, w2, 3.00,
        title="Benchmark II: Materia Medica KG (MMKG)",
        accent=OCHRE,
        title_size=16.0,
        bullet_size=13.5,
        bullets=[
            f"{ds['jsonl_rows']} JSONL rows -> {ds['total_occurrences']} occurrences ({ds['unique_percepts']} percepts)",
            f"{ds['clean_query_count']} clean + {ds['noisy_query_count']} noisy ({ds['safety_critical_clean_queries']} safety-critical)",
            f"Paired {ds['graph_nodes']:,}-node / {ds['graph_links']:,}-link clinical graph",
            "Deterministic regex + negation 4-channel mapping",
        ],
        label="bench_mmkg",
    )
    studies = [
        ("Study A (MMKG, N=953)", BLUE, [
            "7 indexing schemes vs. 7 MPCS variants",
            "Measures RAM, build, scan, latency, safety",
        ]),
        ("Study B1-B3 (G9 TIDE)", OCHRE, [
            "8-variant TIDE component ablation",
            "Anytime budgets B=3..Full & routing",
        ]),
        ("Study C (PersonaEngine)", EMERALD, [
            "8-variant graph ablation on 1,106 nodes",
            "40 queries x 10 runs (deterministic tie-break)",
        ]),
    ]
    for idx, (heading, acc, pts) in enumerate(studies):
        cx = LEFT + idx * (cw + 0.30)
        s.add_card(cx, 4.64, cw, 1.90, title=heading, bullets=pts, accent=acc, title_size=15.0, bullet_size=13.0, label=f"study_ov_{idx}")
    notes_14 = (
        "To evaluate both controlled safety invariants and realistic clinical complexity, we benchmark across two complementary datasets. "
        "Bank v3 provides 700 archetype episodes with 480 clean and 480 noisy queries to isolate each MPCS layer. "
        "To go beyond synthetic scenes, our MMKG benchmark deterministically maps 953 extracted Materia Medica occurrences into 452 unique 4-channel percepts alongside 300 clean and 300 noisy queries for Studies A, B, and C."
    )
    slides.append((s, notes_14))

    # ------------------------------------------------------------------
    # Slide 15: Benchmark I (Bank v3) - Safety & Accuracy
    # ------------------------------------------------------------------
    s = SlideBuilder(15, "Slide 15")
    s.add_chrome("BENCHMARK I: BANK V3", "Bank v3: Safety & Accuracy Across Generations", accent=BLUE)
    bank_order = [
        ("Exact KNN", "Exact KNN (One-Hot Cosine)"),
        ("BM25", "BM25 Inverted Index"),
        ("dlCBF alone", "Counting Bloom (dlCBF Gate)"),
        ("B2 Global top-5", "B2: Baseline v2 (Global Top-5)"),
        ("B2 + dlCBF gate", "B2g: Baseline v2 + dlCBF Gate"),
        ("G4 Core", "G4: Core v2 (Per-Action Z)"),
        ("G5 HyST", "G5: HyST (Hard Slot + Soft Kernel)"),
        ("G6 HMGI", "G6: HMGI (Modality Partitions)"),
        ("G7 SHMF", "G7: SHMF (Auto-Relaxed Filter)"),
        ("G8 KERL", "G8: KERL (SHMF + Safety + Graph)"),
        ("G9 TIDE", "G9: TIDE (Spreading Activation)"),
    ]
    bank_rows = []
    for disp, key in bank_order:
        m = bank_idx[key]
        lat_str = f"{m['latency_mean_ms']:.3f}" if m["latency_mean_ms"] < 0.1 else f"{m['latency_mean_ms']:.2f}"
        bank_rows.append([
            disp,
            f"{m['space_kb']:.1f}",
            lat_str,
            f"{m['accuracy_clean']:.1f}",
            f"{m['recall_3']:.1f}",
            f"{m['unsafe_clean']:.1f}",
            f"{m['accuracy_noisy']:.1f}",
            f"{m['unsafe_noisy']:.1f}",
        ])
    bank_tbl_w = 8.25
    s.add_table(
        LEFT, 1.42, bank_tbl_w,
        [2.05, 0.82, 0.86, 0.90, 0.86, 0.92, 0.90, 0.94],
        ["Scheme", "KB", "ms", "Cln%", "R@3", "C.Unsf", "Nsy%", "N.Unsf"],
        bank_rows,
        row_h_in=0.38,
        header_h_in=0.42,
        font_pt=11.0,
        alignments=["l", "r", "r", "r", "r", "r", "r", "r"],
        highlight_rows={5: CRIMSON_TINT, 6: EMERALD_TINT, 8: BLUE_TINT, 10: BLUE_TINT},
        bold_rows={6, 8, 10},
        label="bank_tbl",
    )
    kx = LEFT + bank_tbl_w + 0.22
    kw = RIGHT - kx
    s.add_kpi_card(
        kx, 1.42, kw, 1.44,
        "26x Safer",
        f"HyST slashes unsafe actions: {bank_idx['G4: Core v2 (Per-Action Z)']['unsafe_clean']:.1f}% -> {g5['unsafe_clean']:.1f}%",
        accent=EMERALD, value_size=26.0, caption_size=13.0, label="bank_kpi1",
    )
    b3_clean = bank["tide_clean"]["B=3"]
    s.add_kpi_card(
        kx, 3.04, kw, 1.44,
        f"{b3_clean['read_ratio']}",
        f"TIDE B=3 candidates read for {b3_clean['accuracy_pct']:.1f}% clean acc.",
        accent=BLUE, value_size=26.0, caption_size=13.0, label="bank_kpi2",
    )
    s.add_kpi_card(
        kx, 4.66, kw, 1.44,
        "~4 ms",
        f"Urgent TIDE ({b3_clean['decision_latency_ms']:.2f} ms) & CPU bridge latency",
        accent=OCHRE, value_size=26.0, caption_size=13.0, label="bank_kpi3",
    )
    s.add_textbox(
        LEFT, 6.22, CONTENT_W, 0.32,
        [ParaSpec([RunSpec("Bank v3 (700 records, 480 clean & 480 noisy queries): SHMF recovers 18.3% empty pools; KERL cuts clean unsafe to 1.7%.", font=FONT_SANS, size_pt=12.0, color=MUTED)], line_pct=110)],
        label="bank_foot",
    )
    notes_15 = (
        "Table 9.1 on Bank v3 demonstrates why structural constraints matter. "
        "Without hard slots, G4 Core allows weakly related high-reward memories to outvote exact matches, causing 31.2 percent unsafe actions. "
        "Introducing HyST hard slots in G5 slashes unsafe actions 26-fold to 1.2 percent, SHMF recovers the 18.3 percent empty candidate sets to lift clean accuracy to 75.6 percent, and KERL and TIDE refine unsafe errors down to 1.7 percent while exposing evidence routing."
    )
    slides.append((s, notes_15))

    # ------------------------------------------------------------------
    # Slide 16: Benchmark I (Bank v3) - Progression & Anytime TIDE
    # ------------------------------------------------------------------
    s = SlideBuilder(16, "Slide 16")
    s.add_chrome("BENCHMARK I: PROGRESSION & ANYTIME", "Bank v3: Generation Progression & Anytime TIDE", accent=BLUE)
    s.add_image_box(
        LEFT, 1.42, w2, 3.68,
        FIGURES_DIR / "fig08_bankv3_acc_unsafe.png",
        "Bank v3 accuracy and unsafe rate across generations",
        accent=BLUE,
        label="fig08",
    )
    s.add_image_box(
        LEFT + w2 + 0.31, 1.42, w2, 3.68,
        FIGURES_DIR / "fig09_bankv3_tide_budget.png",
        "Bank v3 TIDE accuracy vs candidate budget",
        accent=OCHRE,
        label="fig09",
    )
    full_clean = bank["tide_clean"]["full"]
    b3_noisy = bank["tide_noisy"]["B=3"]
    take16 = [
        ("Hard-Slot Safety Invariant", EMERALD, f"Unsafe rate stays fixed at {b3_clean['unsafe_pct']:.1f}% across all budgets"),
        ("Anytime Foraging Peak", BLUE, f"B=3 reaches {b3_clean['accuracy_pct']:.1f}% clean vs {full_clean['accuracy_pct']:.1f}% full read"),
        ("Noisy Consistency", OCHRE, f"B=3 hits {b3_noisy['accuracy_pct']:.1f}% noisy ({b3_noisy['agreement_with_full_pct']:.1f}% full agree)"),
    ]
    for idx, (hdr, acc, txt) in enumerate(take16):
        cx = LEFT + idx * (cw + 0.30)
        s.add_card(cx, 5.26, cw, 1.28, title=hdr, bullets=[txt], accent=acc, title_size=14.5, bullet_size=13.0, label=f"t16_{idx}")
    notes_16 = (
        "These two charts capture our two main findings on Bank v3. "
        "On the left, moving from G4 to G5 eliminates nearly all unsafe actions, while G7 SHMF through G9 TIDE recover coverage without sacrificing safety. "
        "On the right, under urgent anytime deadlines, accuracy peaks at budget B=3 with 71.9 percent clean accuracy reading just 2.2 of 25.4 candidates, outperforming a full read at 64.8 percent because reading lower-ranked episodes dilutes the top seeds."
    )
    slides.append((s, notes_16))

    # ------------------------------------------------------------------
    # Slide 17: Study A (MMKG, N=953)
    # ------------------------------------------------------------------
    s = SlideBuilder(17, "Slide 17")
    s.add_chrome("STUDY A: MMKG INDEXING (N=953)", "Study A: Extended Perceptual Indexing on MMKG", accent=BLUE)
    s.add_image_box(
        LEFT, 1.40, 5.95, 3.55,
        FIGURES_DIR / "fig10_mmkg_study_a.png",
        "Study A grouped bar chart across indexing and MPCS models on MMKG",
        accent=BLUE,
        label="fig10",
    )
    gate_acc = study_a["dlCBF Gate"]["clean_acc"]
    bitset_noisy = study_a["Slot Inverted Bitset"]["noisy_acc"]
    nsw_scan = study_a["NSW Proximity Graph"]["scanned_clean"]
    nsw_cut = int(round(100.0 * (1.0 - nsw_scan / ds["total_occurrences"])))
    kpi_w3 = (5.95 - 0.30) / 3.0
    s.add_kpi_card(LEFT, 5.10, kpi_w3, 1.44, f"{gate_acc:.1f}%", "dlCBF / Cuckoo clean (0.02 ms)", accent=EMERALD, value_size=26.0, caption_size=12.0, label="sa_kpi1")
    s.add_kpi_card(LEFT + kpi_w3 + 0.15, 5.10, kpi_w3, 1.44, f"{bitset_noisy:.1f}%", "Slot Bitset noisy (48.9 KB)", accent=BLUE, value_size=26.0, caption_size=12.0, label="sa_kpi2")
    s.add_kpi_card(LEFT + 2 * (kpi_w3 + 0.15), 5.10, kpi_w3, 1.44, f"{nsw_cut}%", f"NSW scan cut ({nsw_scan:.1f} / {ds['total_occurrences']})", accent=OCHRE, value_size=26.0, caption_size=12.0, label="sa_kpi3")

    sa_models = [
        ("Exact KNN", "Exact KNN (Cosine)"),
        ("BM25 Index", "BM25 Inverted Index"),
        ("dlCBF Gate", "dlCBF Gate"),
        ("Cuckoo Gate", "Cuckoo Filter Gate"),
        ("SimHash LSH", "SimHash LSH (64-bit)"),
        ("Slot Bitset", "Slot Inverted Bitset"),
        ("NSW Graph", "NSW Proximity Graph"),
        ("MPCS B2", "B2 Global Top-5"),
        ("G5 HyST", "G5 HyST"),
        ("G7 SHMF", "G7 SHMF"),
        ("G9 TIDE", "G9 TIDE"),
    ]
    sa_rows = []
    for disp, key in sa_models:
        m = study_a[key]
        lat_s = f"{m['latency_mean_ms']:.3f}" if m["latency_mean_ms"] < 0.1 else f"{m['latency_mean_ms']:.2f}"
        scan_s = f"{int(m['scanned_clean'])}" if float(m["scanned_clean"]).is_integer() else f"{m['scanned_clean']:.1f}"
        sa_rows.append([
            disp,
            f"{m['space_kb']:.1f}",
            scan_s,
            lat_s,
            f"{m['clean_acc']:.1f}",
            f"{m['noisy_acc']:.1f}",
            f"{m['clean_unsafe']:.1f}",
        ])
    rx17 = LEFT + 6.13
    rw17 = RIGHT - rx17  # 5.90 in
    s.add_table(
        rx17, 1.40, rw17,
        [1.76, 0.68, 0.62, 0.68, 0.68, 0.68, 0.80],
        ["Scheme", "KB", "Scan", "ms", "Cln%", "Nsy%", "Unsf%"],
        sa_rows,
        row_h_in=0.415,
        header_h_in=0.44,
        font_pt=11.0,
        alignments=["l", "r", "r", "r", "r", "r", "r"],
        highlight_rows={2: EMERALD_TINT, 5: BLUE_TINT, 6: OCHRE_TINT, 10: BLUE_TINT},
        bold_rows={2, 5, 6},
        label="study_a_tbl",
    )
    notes_17 = (
        "Study A evaluates seven perceptual indexing baselines alongside seven MPCS variants on all 953 Materia Medica KG occurrences. "
        "Exact hash gates like dlCBF and Cuckoo Filter hit 95.0 percent clean accuracy scanning just 11 records in 20 microseconds, but drop to 45.7 percent when a single noisy feature triggers a cache miss. "
        "Slot Inverted Bitset preserves the highest noisy accuracy at 77.7 percent in 48.9 KB, NSW cuts node scans by 71 percent down to 278.9 nodes, and G5/G7 hard-slot filtering lowers clean unsafe errors to 11.7 percent."
    )
    slides.append((s, notes_17))

    # ------------------------------------------------------------------
    # Slide 18: Study B1 (MMKG) - G9 TIDE Component Ablation
    # ------------------------------------------------------------------
    s = SlideBuilder(18, "Slide 18")
    s.add_chrome("STUDY B1: MMKG G9 TIDE ABLATION", "Study B1: MPCS G9 TIDE Component Ablation", accent=OCHRE)
    s.add_image_box(
        LEFT, 1.40, 5.75, 3.68,
        FIGURES_DIR / "fig11_mmkg_study_b1.png",
        "Study B1 G9 TIDE 8-variant ablation chart on MMKG",
        accent=OCHRE,
        label="fig11",
    )
    b1_soft = next(v for v in study_b1 if "Hard Slots" in v["variant"])
    b1_urg = next(v for v in study_b1 if "Urgent B=3" in v["variant"])
    kpi_w2 = (5.75 - 0.16) / 2.0
    s.add_kpi_card(
        LEFT, 5.22, kpi_w2, 1.32,
        f"{b1_soft['clean_acc']:.1f}%",
        f"w/o Hard Slots ({b1_soft['clean_lat_ms']:.2f} ms, >5x slower)",
        accent=CRIMSON, value_size=26.0, caption_size=12.0, label="sb1_kpi1",
    )
    s.add_kpi_card(
        LEFT + kpi_w2 + 0.16, 5.22, kpi_w2, 1.32,
        f"{b1_urg['clean_acc']:.1f}%",
        f"Urgent B=3 clean ({b1_urg['noisy_acc']:.1f}% noisy, {b1_urg['clean_unsafe']:.1f}% unsf)",
        accent=EMERALD, value_size=26.0, caption_size=12.0, label="sb1_kpi2",
    )

    b1_short_names = {
        "Full G9 TIDE (Urgent=False)": "Full G9 TIDE (Urgent=False)",
        "w/o TIDE Spread (hops=0, w_g=0)": "w/o TIDE Spread (hops=0)",
        "w/o VAD Affect & Salience (salience_gain=0, affect=False)": "w/o VAD Affect & Salience",
        "w/o KERL Near-Miss Guard": "w/o KERL Near-Miss Guard",
        "w/o SHMF Auto-Relaxation": "w/o SHMF Auto-Relaxation",
        "w/o HyST Hard Slots (Soft Only)": "w/o HyST Hard Slots",
        "w/o Expert Grade Boost (boost=1.0)": "w/o Expert Boost (1.0)",
        "w/o Full-Read (Urgent B=3)": "w/o Full-Read (Urgent B=3)",
    }
    b1_rows = []
    for row in study_b1:
        b1_rows.append([
            b1_short_names.get(row["variant"], row["variant"]),
            f"{row['clean_acc']:.1f}",
            f"{row['clean_unsafe']:.1f}",
            f"{row['clean_lat_ms']:.2f}",
            f"{row['noisy_acc']:.1f}",
            f"{row['noisy_unsafe']:.1f}",
            f"{row['noisy_lat_ms']:.2f}",
        ])
    rx18 = LEFT + 5.93
    rw18 = RIGHT - rx18  # 6.10 in
    tbl18_end = s.add_table(
        rx18, 1.40, rw18,
        [2.32, 0.63, 0.67, 0.60, 0.63, 0.67, 0.58],
        ["Variant", "Cln%", "C.Un%", "C.ms", "Nsy%", "N.Un%", "N.ms"],
        b1_rows,
        row_h_in=0.47,
        header_h_in=0.46,
        font_pt=11.0,
        alignments=["l", "r", "r", "r", "r", "r", "r"],
        highlight_rows={5: CRIMSON_TINT, 7: EMERALD_TINT},
        bold_rows={5, 7},
        label="study_b1_tbl",
    )
    s.add_card(
        rx18, tbl18_end + 0.14, rw18, 6.54 - (tbl18_end + 0.14),
        accent=BLUE,
        accent_side="left",
        body_paras=[
            ParaSpec([
                RunSpec("Key Insight: ", font=FONT_SERIF, size_pt=14.0, color=INK, bold=True),
                RunSpec("Urgent B=3 halts _head_a k=5 dilution; complete 4-channel MMKG percepts hold guard/relaxation invariant.", font=FONT_SANS, size_pt=12.5, color=CHARCOAL),
            ], line_pct=115, space_after_pt=0.0)
        ],
        label="sb1_note",
    )
    notes_18 = (
        "Study B1 isolates each architectural module inside MPCS G9 TIDE on the 953-occurrence MMKG corpus. "
        "Removing HyST hard slots causes full architectural collapse: accuracy plunges to 12.7 percent and latency jumps over fivefold to 34.48 ms because the engine must score every record. "
        "Conversely, toggling off full-read in favor of Urgent B=3 surges clean accuracy from 42.7 to 91.0 percent and noisy accuracy to 78.7 percent while more than halving clean unsafe errors to 11.7 percent."
    )
    slides.append((s, notes_18))

    # ------------------------------------------------------------------
    # Slide 19: Study B2 & B3 (MMKG)
    # ------------------------------------------------------------------
    s = SlideBuilder(19, "Slide 19")
    s.add_chrome("STUDY B2 & B3: MMKG BUDGETS & ROUTING", "Study B2 & B3: Anytime Budgets & Sufficiency Routing", accent=BLUE)
    s.add_image_box(
        LEFT, 1.40, 5.25, 2.98,
        FIGURES_DIR / "fig12_mmkg_tide_budget.png",
        "Study B2 MMKG TIDE accuracy vs budget",
        accent=BLUE,
        label="fig12",
    )
    b3_rows = []
    for mode in ("DIRECT", "SUBGRAPH", "UNGROUNDED"):
        c = study_b3["clean"][mode]
        n = study_b3["noisy"][mode]
        b3_rows.append([
            mode,
            f"{c['count']} ({c['share_pct']:.1f}%)",
            f"{c['accuracy_pct']:.1f}%",
            f"{n['count']} ({n['share_pct']:.1f}%)",
            f"{n['accuracy_pct']:.1f}%",
        ])
    s.add_table(
        LEFT, 4.54, 5.25,
        [1.35, 1.15, 0.80, 1.15, 0.80],
        ["Study B3 Route", "Cln Share", "Cln%", "Nsy Share", "Nsy%"],
        b3_rows,
        row_h_in=0.45,
        header_h_in=0.46,
        font_pt=11.0,
        alignments=["l", "r", "r", "r", "r"],
        highlight_rows={0: BLUE_TINT, 1: OCHRE_TINT},
        bold_rows={0, 1},
        label="study_b3_tbl",
    )
    rx19 = LEFT + 5.45
    rw19 = RIGHT - rx19  # 6.58 in
    b2_rows = []
    for split_lbl, split_key in (("Clean", "clean"), ("Noisy", "noisy")):
        for b_key in ("B=3", "B=5", "B=10", "B=20", "B=50", "Full"):
            e = study_b2[split_key][b_key]
            b2_rows.append([
                split_lbl,
                e["budget"],
                e["read_ratio"],
                f"{e['cut_short_pct']:.1f}%",
                f"{e['accuracy_pct']:.1f}%",
                f"{e['unsafe_pct']:.1f}%",
                f"{e['agreement_with_full_pct']:.1f}%",
                f"{e['decision_latency_ms']:.2f}",
            ])
    tbl19_end = s.add_table(
        rx19, 1.40, rw19,
        [0.72, 0.68, 1.08, 0.78, 0.82, 0.82, 0.84, 0.84],
        ["Split", "Budget", "Read/Avail", "Cut%", "Acc%", "Unsf%", "Agr%", "ms"],
        b2_rows,
        row_h_in=0.35,
        header_h_in=0.38,
        font_pt=11.0,
        alignments=["l", "l", "r", "r", "r", "r", "r", "r"],
        highlight_rows={0: EMERALD_TINT, 2: BLUE_TINT, 6: EMERALD_TINT},
        bold_rows={0, 6},
        label="study_b2_tbl",
    )
    s.add_textbox(
        rx19, tbl19_end + 0.10, rw19, 0.46,
        [ParaSpec([RunSpec("B=3 cuts short 81.7% (2.8/67.3 read) for 91.0% clean acc.; B=10 achieves 3.9% clean unsafe.", font=FONT_SANS, size_pt=12.0, color=MUTED)], line_pct=110)],
        label="sb2_note",
    )
    notes_19 = (
        "Study B2 sweeps TIDE candidate budgets from B=3 to Full on MMKG under urgent mode. "
        "Clean accuracy declines monotonically from 91.0 percent at B=3, where TIDE reads 2.8 of 67.3 available candidates in 5.67 ms, down to 44.0 percent on a full read, while B=10 cuts clean unsafe errors down to 3.9 percent. "
        "In Study B3 with urgent mode off, 19.7 percent of queries route DIRECT and 80.3 percent escalate to SUBGRAPH, with zero UNGROUNDED queries because all four channels are populated."
    )
    slides.append((s, notes_19))

    # ------------------------------------------------------------------
    # Slide 20: Study C (MMKG) - PersonaQueryEngine Ablation
    # ------------------------------------------------------------------
    s = SlideBuilder(20, "Slide 20")
    s.add_chrome("STUDY C: PERSONA ENGINE ABLATION", "Study C: PersonaQueryEngine Ablation (1,106 Nodes)", accent=EMERALD)
    s.add_image_box(
        LEFT, 1.40, 5.15, 3.55,
        FIGURES_DIR / "fig13_mmkg_study_c.png",
        "Study C PersonaQueryEngine 8-variant ablation chart",
        accent=EMERALD,
        label="fig13",
    )
    sc_expl = study_c[0]
    sc_mu = next(v for v in study_c if "mu_v=1.0" in v["variant"])
    kpi_c2 = (5.15 - 0.16) / 2.0
    s.add_kpi_card(
        LEFT, 5.10, kpi_c2, 1.44,
        f"{sc_mu['remedy_top1_pct']:.0f}%",
        f"mu_v=1.0 Top-1 (vs {sc_expl['remedy_top1_pct']:.0f}%; Top-3: {sc_mu['remedy_top3_pct']:.0f}%)",
        accent=EMERALD, value_size=26.0, caption_size=12.0, label="sc_kpi1",
    )
    s.add_kpi_card(
        LEFT + kpi_c2 + 0.16, 5.10, kpi_c2, 1.44,
        "hops=1",
        f"Matches Full ({sc_expl['remedy_top1_pct']:.0f}%/{sc_expl['remedy_top3_pct']:.0f}%), delta^2 < 0.35",
        accent=BLUE, value_size=26.0, caption_size=12.0, label="sc_kpi2",
    )

    sc_short = {
        "Full Exploratory Persona (theta=0.35)": "Full Exploratory (0.35)",
        "Full Confident Persona (theta=0.70)": "Full Confident (0.70)",
        "w/o 2-Hop Spreading Activation (hops=0)": "w/o Spread (hops=0)",
        "w/o 2nd Hop (hops=1)": "w/o 2nd Hop (hops=1)",
        "w/o VAD Arousal & Grade Multiplier (mu_v=1.0)": "w/o VAD & Grade (mu_v=1)",
        "w/o Clinical Synonym Expansion": "w/o Synonym Expansion",
        "w/o Edge-Weight Modulation (uniform w_uv=1.0)": "w/o Edge Weights (w=1)",
        "w/o Precomputed Inverted Index (Linear Scan)": "w/o Inverted Index (Lin.)",
    }
    sc_rows = []
    for row in study_c:
        sc_rows.append([
            sc_short.get(row["variant"], row["variant"]),
            f"{row['mean_kept_nodes']:.1f}",
            f"{row['mean_pruned_pct']:.1f}%",
            f"{row['mean_internal_edges']}",
            row["remedy_top1_hits"],
            row["remedy_top3_hits"],
            f"{row['mean_lat_ms']:.2f}",
            f"{row['speedup_vs_linear']:.2f}x",
        ])
    rx20 = LEFT + 5.33
    rw20 = RIGHT - rx20  # 6.70 in
    tbl20_end = s.add_table(
        rx20, 1.40, rw20,
        [2.20, 0.58, 0.66, 0.58, 0.72, 0.72, 0.64, 0.60],
        ["Variant", "Kept", "Prun%", "Edg", "Top-1", "Top-3", "ms", "Spd"],
        sc_rows,
        row_h_in=0.47,
        header_h_in=0.46,
        font_pt=11.0,
        alignments=["l", "r", "r", "r", "r", "r", "r", "r"],
        highlight_rows={0: BLUE_TINT, 3: OCHRE_TINT, 4: EMERALD_TINT},
        bold_rows={0, 4},
        label="study_c_tbl",
    )
    s.add_card(
        rx20, tbl20_end + 0.14, rw20, 6.54 - (tbl20_end + 0.14),
        accent=OCHRE,
        accent_side="left",
        body_paras=[
            ParaSpec([
                RunSpec("40 queries x 10 runs (400 calls/variant): ", font=FONT_SERIF, size_pt=13.5, color=INK, bold=True),
                RunSpec("Deterministic (-score, label.lower()) tie-break; hops=0 & Confident get 0/40 remedies.", font=FONT_SANS, size_pt=12.5, color=CHARCOAL),
            ], line_pct=115, space_after_pt=0.0)
        ],
        label="sc_note",
    )
    notes_20 = (
        "Study C ablates every component of PersonaQueryEngine across 40 queries repeated 10 times on the 1,106-node graph with deterministic (-score, label.lower()) tie-breaking. "
        "Both hops=0 and Confident mode at theta=0.70 score 0 of 40 remedies because symptom-only queries need one propagation step to reach Medicine nodes, yet 1-hop transfer delta=0.58 sits below 0.70. "
        "Furthermore, removing the second hop reproduces the exact 60 percent Top-1 and 80 percent Top-3 exploratory result faster, while setting mu_v=1.0 lifts Top-1 from 60 to 80 percent and Top-3 from 80 to 90 percent by removing high-arousal symptom hub amplification."
    )
    slides.append((s, notes_20))

    # ------------------------------------------------------------------
    # Slide 21: Code-Verified Architectural Findings
    # ------------------------------------------------------------------
    s = SlideBuilder(21, "Slide 21")
    s.add_chrome("CODE-VERIFIED FINDINGS", "Three Code-Level Mechanisms Explaining MMKG Results", accent=CRIMSON)
    findings = [
        ("1. _head_a k=5 Dilution vs. B=3", BLUE, [
            "kerl_layer._head_a sets k=5 when Urgent=False",
            "Dense MMKG repeats dilute top exact match",
            "Urgent B=3 forces k=1 & top-3 truncation",
            f"Drives {study_b1[0]['clean_acc']:.1f}% -> {b1_urg['clean_acc']:.1f}% clean jump",
        ]),
        ("2. 1-Hop Sufficiency & mu_v Hub Bias", OCHRE, [
            "Bipartite graph needs 1 hop to hit Medicine",
            "delta^2 = 0.3364 < theta_expl = 0.35 (pruned)",
            "hops=1 matches Full Exploratory faster",
            "mu_v=(1+0.85*a_v)*(W_v/2.2) boosts hubs",
        ]),
        ("3. min(1.0, edge_w) Clamping", EMERALD, [
            "persona_engine.py clamps transfer by min(1, w)",
            "All 2,024 MMKG edge weights lie in [1.0, 2.95]",
            "Edge weights saturate uniformly at 1.0",
            "Explains w_uv=1.0 matching Full Exploratory",
        ]),
    ]
    for idx, (heading, acc, pts) in enumerate(findings):
        cx = LEFT + idx * (cw + 0.30)
        s.add_card(cx, 1.50, cw, 4.10, title=heading, bullets=pts, accent=acc, title_size=15.0, bullet_size=13.5, label=f"find_{idx}")
    s.add_card(
        LEFT, 5.76, CONTENT_W, 0.78,
        accent=INK,
        accent_side="left",
        body_paras=[
            ParaSpec([
                RunSpec("Verified in Source: ", font=FONT_SERIF, size_pt=14.0, color=INK, bold=True),
                RunSpec("Model/experimental/07_kerl/kerl_layer.py (_head_a) and LocalKG/src/lkg/query/persona_engine.py (query, node_multipliers).", font=FONT_SANS, size_pt=13.0, color=CHARCOAL),
            ], line_pct=115, space_after_pt=0.0)
        ],
        label="find_foot",
    )
    notes_21 = (
        "Inspecting the implementation directly explains three subtle empirical behaviors observed in Studies B and C. "
        "First, _head_a in kerl_layer.py averages the top k=5 candidates per action when urgent is false, allowing lower-ranked dense MMKG matches to dilute the consensus unless urgent B=3 narrows k to 1. "
        "Second, in persona_engine.py, squared hop decay delta^2 equals 0.3364 which falls below the 0.35 exploratory threshold, while the salience multiplier mu_v amplifies high-arousal symptom hubs over Medicine nodes. "
        "Third, edge propagation clamps weight via min(1.0, edge_w), saturating all 2,024 MMKG weights in [1.0, 2.95] identically to 1.0."
    )
    slides.append((s, notes_21))

    # ------------------------------------------------------------------
    # Slide 22: Limitations & Future Work
    # ------------------------------------------------------------------
    s = SlideBuilder(22, "Slide 22")
    s.add_chrome("LIMITATIONS & FUTURE WORK", "Known Limitations & Concrete Next Steps", accent=OCHRE)
    s.add_card(
        LEFT, 1.48, w2, 5.02,
        title="Current Limitations",
        accent=CRIMSON,
        title_size=16.0,
        bullet_size=13.5,
        bullets=[
            "MMKG percepts rule-mapped, not live hardware sensors",
            "Full-read _head_a k=5 lags B=3 on dense clusters",
            "Small extraction gold set (26 keynotes, 8 remedies)",
            "min(1, w_uv) saturates MMKG [1.0, 2.95] edge weights",
            "Historical corpus serves as testbed, not clinical advice",
        ],
        label="lim_card",
    )
    s.add_card(
        LEFT + w2 + 0.31, 1.48, w2, 5.02,
        title="Future Work",
        accent=EMERALD,
        title_size=16.0,
        bullet_size=13.5,
        bullets=[
            "Replace per-action k=5 with global top-k voting",
            "Validate MPCS on recorded real sensor streams",
            "Normalize edge weights & tune mu_v hub bias",
            "Map LocalKG types to UMLS and SNOMED CT",
            "Constrain local SLMs using verified subgraphs",
        ],
        label="fut_card",
    )
    notes_22 = (
        "Our evaluation highlights clear engineering limitations and next steps. "
        "While Studies A, B, and C move beyond synthetic Bank v3 scenes onto 953 real extracted clinical occurrences, those occurrences are deterministically mapped into the four-channel schema rather than captured from hardware sensors, and _head_a full-read averaging plus min(1, w_uv) weight clamping remain open refinements. "
        "Future work targets global top-k voting inside HyST and TIDE, normalized edge weights, UMLS and SNOMED CT alignment, and using MPCS as a structural guardrail around small local language models."
    )
    slides.append((s, notes_22))

    # ------------------------------------------------------------------
    # Slide 23: Closing Summary
    # ------------------------------------------------------------------
    s = SlideBuilder(23, "Slide 23")
    s.add_chrome("CLOSING SUMMARY", "Explicit Structures, Auditable Decisions", accent=INK, title_pt=28.0)
    kpi4_w = (CONTENT_W - 0.75) / 4.0
    closing_kpis = [
        ("26x", f"Unsafe drop on Bank v3 via HyST ({bank_idx['G4: Core v2 (Per-Action Z)']['unsafe_clean']:.1f}% -> {g5['unsafe_clean']:.1f}%)", EMERALD),
        (f"{b1_urg['clean_acc']:.1f}%", f"MMKG Urgent B=3 clean acc. ({study_b2['clean']['B=3']['read_ratio']} read)", BLUE),
        (f"{ds['graph_nodes']:,} / {ds['graph_links']:,}", "LocalKG nodes & edges; 0% hybrid extraction failure", OCHRE),
        ("3.91 ms", "Mean CPU bridge latency; 5/5 bridge & 33/33 unit tests pass", INK),
    ]
    for idx, (val, cap, acc) in enumerate(closing_kpis):
        cx = LEFT + idx * (kpi4_w + 0.25)
        s.add_kpi_card(cx, 1.56, kpi4_w, 2.55, val, cap, accent=acc, value_size=28.0, caption_size=13.5, accent_side="top", label=f"close_kpi_{idx}")

    s.add_card(
        LEFT, 4.40, CONTENT_W, 2.05,
        title="Key Takeaway",
        accent=BLUE,
        accent_side="left",
        title_size=16.0,
        body_paras=[
            ParaSpec([
                RunSpec(
                    "Safety can be enforced structurally via hard-slot gating; reading fewer, salience-ranked episodes improves accuracy on both synthetic and clinical banks; and pairing MPCS with LocalKG anchors every output to verifiable source quotes.",
                    font=FONT_SANS, size_pt=14.5, color=CHARCOAL,
                )
            ], line_pct=130, space_after_pt=0.0)
        ],
        label="close_synth",
    )
    notes_23 = (
        "In summary, MPCS and LocalKG demonstrate that decision support can be safe, fast, and fully auditable without relying on opaque end-to-end language generation. "
        "Hard-slot filtering cuts unsafe actions 26-fold on Bank v3, anytime TIDE reading achieves 91.0 percent clean accuracy on MMKG at budget B=3, and our hybrid extractor produces a 1,106-node clinical graph with zero batch failures. "
        "Running in under 4 milliseconds on a single CPU core and passing all 5 bridge and 33 unit tests, the integrated system provides a clean foundation for trustworthy neuro-symbolic reasoning. Thank you."
    )
    slides.append((s, notes_23))

    return slides


def rewrite_font_references(xml_bytes: bytes) -> bytes:
    """Replace legacy Source Serif 4 and Arial buFont references with Georgia/Inter."""
    text = xml_bytes.decode("utf-8")
    text = text.replace("Source Serif 4", FONT_SERIF)
    text = text.replace('<a:buFont typeface="Arial"', f'<a:buFont typeface="{FONT_SANS}"')
    return text.encode("utf-8")


def build_presentation_xml(num_slides: int, template_bytes: bytes) -> bytes:
    """Update ppt/presentation.xml for num_slides slides and updated rIds."""
    text = template_bytes.decode("utf-8")
    text = re.sub(
        r'<p:notesMasterId\s+r:id="rId\d+"\s*/>',
        f'<p:notesMasterId r:id="rId{num_slides + 2}"/>',
        text,
    )
    text = re.sub(
        r'<p:regular\s+r:id="rId\d+"\s*/>',
        f'<p:regular r:id="rId{num_slides + 7}"/>',
        text,
    )
    text = re.sub(
        r'<p:bold\s+r:id="rId\d+"\s*/>',
        f'<p:bold r:id="rId{num_slides + 8}"/>',
        text,
    )
    sld_ids = "".join(
        f'<p:sldId id="{256 + i}" r:id="rId{2 + i}"/>' for i in range(num_slides)
    )
    text = re.sub(r"<p:sldIdLst>.*?</p:sldIdLst>", f"<p:sldIdLst>{sld_ids}</p:sldIdLst>", text, flags=re.DOTALL)
    return text.encode("utf-8")


def build_presentation_rels_xml(num_slides: int) -> bytes:
    """Build ppt/_rels/presentation.xml.rels matching presentation.xml rIds."""
    rels = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
    ]
    for i in range(num_slides):
        rels.append(
            f'<Relationship Id="rId{2 + i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i + 1}.xml"/>'
        )
    base = num_slides + 2
    rels.extend([
        f'<Relationship Id="rId{base}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesMaster" Target="notesMasters/notesMaster1.xml"/>',
        f'<Relationship Id="rId{base + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps" Target="presProps.xml"/>',
        f'<Relationship Id="rId{base + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps" Target="viewProps.xml"/>',
        f'<Relationship Id="rId{base + 3}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>',
        f'<Relationship Id="rId{base + 4}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles" Target="tableStyles.xml"/>',
        f'<Relationship Id="rId{base + 5}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/font" Target="fonts/font1.fntdata"/>',
        f'<Relationship Id="rId{base + 6}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/font" Target="fonts/font2.fntdata"/>',
    ])
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(rels)
        + "</Relationships>"
    ).encode("utf-8")


def build_content_types_xml(num_slides: int) -> bytes:
    """Build [Content_Types].xml registering all slides, notes, and defaults."""
    defaults = (
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="jpeg" ContentType="image/jpeg"/>'
        '<Default Extension="jpg" ContentType="image/jpg"/>'
        '<Default Extension="svg" ContentType="image/svg+xml"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        '<Default Extension="gif" ContentType="image/gif"/>'
        '<Default Extension="fntdata" ContentType="application/x-fontdata"/>'
    )
    overrides = [
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
        '<Override PartName="/ppt/notesMasters/notesMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml"/>',
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
        '<Override PartName="/ppt/presProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/>',
        '<Override PartName="/ppt/viewProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"/>',
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
        '<Override PartName="/ppt/tableStyles.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"/>',
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>',
        '<Override PartName="/ppt/slideLayouts/slideLayout2.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    for i in range(1, num_slides + 1):
        overrides.append(
            f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        )
        overrides.append(
            f'<Override PartName="/ppt/notesSlides/notesSlide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        + defaults
        + "".join(overrides)
        + "</Types>"
    ).encode("utf-8")


def build_app_xml(num_slides: int, template_app_bytes: bytes) -> bytes:
    """Update docProps/app.xml slide and note counts cleanly."""
    text = template_app_bytes.decode("utf-8")
    text = re.sub(r"<Slides>\d+</Slides>", f"<Slides>{num_slides}</Slides>", text)
    text = re.sub(r"<Notes>\d+</Notes>", f"<Notes>{num_slides}</Notes>", text)
    text = re.sub(
        r"<vt:vector size=\"\d+\" baseType=\"lpstr\">.*?</vt:vector>",
        (
            f'<vt:vector size="{num_slides + 3}" baseType="lpstr">'
            '<vt:lpstr>Georgia</vt:lpstr><vt:lpstr>Inter</vt:lpstr><vt:lpstr>MPCS and LocalKG</vt:lpstr>'
            + "".join(f"<vt:lpstr>Slide {i}</vt:lpstr>" for i in range(1, num_slides + 1))
            + "</vt:vector>"
        ),
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r'(<vt:lpstr>Slide Titles</vt:lpstr></vt:variant>\s*<vt:variant><vt:i4>)\d+(</vt:i4>)',
        rf"\g<1>{num_slides}\2",
        text,
    )
    return text.encode("utf-8")


def verify_pptx(pptx_path: Path, expected_slides: int) -> None:
    """Self-verify XML integrity, font rules, bounding boxes, and image refs."""
    with zipfile.ZipFile(pptx_path, "r") as zf:
        names = set(zf.namelist())
        for name in names:
            if name.endswith(".xml") or name.endswith(".rels"):
                ET.fromstring(zf.read(name))

        pres_root = ET.fromstring(zf.read("ppt/presentation.xml"))
        pres_rels = ET.fromstring(zf.read("ppt/_rels/presentation.xml.rels"))
        ct_root = ET.fromstring(zf.read("[Content_Types].xml"))
        sld_ids = list(pres_root.iter(f"{{{NS_P}}}sldId"))
        assert len(sld_ids) == expected_slides, f"Expected {expected_slides} sldId, got {len(sld_ids)}"
        pres_rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in pres_rels}
        for idx, sld_id in enumerate(sld_ids, start=1):
            rid = sld_id.attrib[f"{{{NS_R}}}id"]
            assert pres_rel_map[rid] == f"slides/slide{idx}.xml", f"Bad slide rel {idx}"

        override_parts = {el.attrib["PartName"] for el in ct_root if el.tag.endswith("Override")}
        for idx in range(1, expected_slides + 1):
            assert f"/ppt/slides/slide{idx}.xml" in override_parts, f"Missing ContentType for slide{idx}"
            assert f"/ppt/notesSlides/notesSlide{idx}.xml" in override_parts, f"Missing ContentType for notesSlide{idx}"

        for name in names:
            if name.startswith(("ppt/theme/", "ppt/slideMasters/", "ppt/slideLayouts/", "docProps/app.xml")) and name.endswith(".xml"):
                raw = zf.read(name).decode("utf-8")
                assert "Source Serif 4" not in raw, f"Legacy font Source Serif 4 left in {name}"

        for i in range(1, expected_slides + 1):
            s_path = f"ppt/slides/slide{i}.xml"
            n_path = f"ppt/notesSlides/notesSlide{i}.xml"
            r_path = f"ppt/slides/_rels/slide{i}.xml.rels"
            assert s_path in names and n_path in names and r_path in names, f"Missing slide/notes {i}"

            s_root = ET.fromstring(zf.read(s_path))
            rels_root = ET.fromstring(zf.read(r_path))
            rid_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels_root}

            for blip in s_root.iter(f"{{{NS_A}}}blip"):
                rid = blip.attrib[f"{{{NS_R}}}embed"]
                target = rid_map[rid].replace("../", "ppt/")
                assert target in names, f"Slide {i} missing image target {target}"

            for sr in s_root.iter(f"{{{NS_A}}}srcRect"):
                for attr in ("l", "r", "t", "b"):
                    assert int(sr.attrib.get(attr, "0")) >= 0, f"Slide {i} negative srcRect {attr}"

            for rpr in list(s_root.iter(f"{{{NS_A}}}rPr")) + list(s_root.iter(f"{{{NS_A}}}endParaRPr")):
                sz = int(rpr.attrib.get("sz", "1200"))
                assert sz >= 1000, f"Slide {i} font below 10pt: {sz}"
                for tag in ("latin", "ea", "cs"):
                    el = rpr.find(f"{{{NS_A}}}{tag}")
                    if el is not None and el.attrib.get("typeface"):
                        assert el.attrib["typeface"] in (FONT_SERIF, FONT_SANS), f"Bad font on slide {i}: {el.attrib['typeface']}"

            spTree = s_root.find(f".//{{{NS_P}}}spTree")
            for ch in spTree:
                cNv = ch.find(f".//{{{NS_P}}}cNvPr")
                cname = cNv.attrib.get("name", "") if cNv is not None else ""
                for xfrm in ch.iter(f"{{{NS_A}}}xfrm"):
                    off = xfrm.find(f"{{{NS_A}}}off")
                    ext = xfrm.find(f"{{{NS_A}}}ext")
                    if off is not None and ext is not None:
                        cx, cy = int(ext.attrib["cx"]), int(ext.attrib["cy"])
                        if cx > 0 and cy > 0:
                            x_in = int(off.attrib["x"]) / EMU_PER_INCH
                            y_in = int(off.attrib["y"]) / EMU_PER_INCH
                            w_in = cx / EMU_PER_INCH
                            h_in = cy / EMU_PER_INCH
                            assert SAFE_X_MIN - 1e-3 <= x_in and x_in + w_in <= SAFE_X_MAX + 1e-3, f"Slide {i} '{cname}' X out of bounds"
                            assert SAFE_Y_MIN - 1e-3 <= y_in and y_in + h_in <= SAFE_Y_MAX + 1e-3, f"Slide {i} '{cname}' Y out of bounds"
                            if i >= 2 and not cname.startswith("footer_"):
                                assert y_in + h_in <= 6.74, f"Slide {i} '{cname}' encroaches on footer ({y_in + h_in:.2f} in)"

            slide_txt = " ".join(t.text for t in s_root.iter(f"{{{NS_A}}}t") if t.text)
            clean_text(slide_txt, f"verify slide {i}")

            n_root = ET.fromstring(zf.read(n_path))
            note_txt = " ".join(t.text for t in n_root.iter(f"{{{NS_A}}}t") if t.text)
            clean_text(note_txt, f"verify notes {i}")
            assert len(note_txt.strip()) > 30, f"Slide {i} notes too short"


def build_pptx() -> Path:
    """Assemble and write report/PPT/BTP_PPT.pptx."""
    mmkg = load_json(MMKG_JSON)
    bank = load_json(BANK_JSON)
    slides = build_slides(mmkg, bank)
    num_slides = len(slides)

    OUTPUT_PPTX.parent.mkdir(parents=True, exist_ok=True)
    preserved_prefixes = ("ppt/fonts/", "ppt/notesMasters/", "ppt/slideLayouts/", "ppt/slideMasters/", "ppt/theme/")
    preserved_exact = {"_rels/.rels", "docProps/core.xml", "ppt/presProps.xml", "ppt/viewProps.xml", "ppt/tableStyles.xml"}

    media_files: set[str] = set()
    for sb, _ in slides:
        for _, media_name in sb.image_rels:
            media_files.add(media_name)

    with zipfile.ZipFile(TEMPLATE_PPTX, "r") as zin, zipfile.ZipFile(OUTPUT_PPTX, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            name = item.filename
            if name.endswith("/"):
                continue
            if name in preserved_exact or name.startswith(preserved_prefixes):
                data = zin.read(name)
                if name.endswith(".xml") and ("slideMaster" in name or "slideLayout" in name or "theme1" in name):
                    data = rewrite_font_references(data)
                zout.writestr(name, data)

        zout.writestr("[Content_Types].xml", build_content_types_xml(num_slides))
        zout.writestr("docProps/app.xml", build_app_xml(num_slides, zin.read("docProps/app.xml")))
        zout.writestr("ppt/presentation.xml", build_presentation_xml(num_slides, zin.read("ppt/presentation.xml")))
        zout.writestr("ppt/_rels/presentation.xml.rels", build_presentation_rels_xml(num_slides))

        for idx, (sb, notes_text) in enumerate(slides, start=1):
            zout.writestr(f"ppt/slides/slide{idx}.xml", sb.to_xml())
            zout.writestr(f"ppt/slides/_rels/slide{idx}.xml.rels", sb.to_rels_xml())
            notes_xml, notes_rels = build_notes_xml(idx, notes_text)
            zout.writestr(f"ppt/notesSlides/notesSlide{idx}.xml", notes_xml)
            zout.writestr(f"ppt/notesSlides/_rels/notesSlide{idx}.xml.rels", notes_rels)

        for media_name in sorted(media_files):
            img_path = FIGURES_DIR / media_name
            with open(img_path, "rb") as fh:
                zout.writestr(f"ppt/media/{media_name}", fh.read())

    verify_pptx(OUTPUT_PPTX, num_slides)
    return OUTPUT_PPTX


if __name__ == "__main__":
    out_path = build_pptx()
    print(f"Built and verified {out_path} (23 slides)")
