"""
algebra2_radical_test.py
========================
Core math engine for the Algebra 2 Radical Test Generator.

Public API
----------
build_txt_bytes(**kwargs)  ->  bytes   UTF-8 text file (Google Docs / Auto-LaTeX)
build_pdf_bytes(**kwargs)  ->  bytes   binary PDF (math rendered as images)
quick_generate(...)        ->  dict    saves to disk, returns byte buffers too
interactive_menu()                     full terminal UI

This module has NO FastAPI dependency — it is a pure library.
app.py imports it and streams the returned bytes over HTTP.

Author : zekeg
Created: 12/02/2026
"""

import io
import math
import os
import random
from typing import Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════
#  Public metadata  (consumed by FastAPI /api/sections endpoint)
# ═══════════════════════════════════════════════════════════════

SECTION_TITLES: Dict[int, str] = {
    1: "DIVIDE AND SIMPLIFY",
    2: "SIMPLIFY POWERS / EXPONENTS",
    3: "MULTIPLY RADICALS",
}

SECTION_Q_DEFAULTS: Dict[int, int] = {1: 8, 2: 4, 3: 3}
SECTION_Q_BOUNDS: Dict[int, Tuple[int, int]] = {1: (1, 30), 2: (1, 20), 3: (1, 20)}

SECTION_DESCRIPTIONS: Dict[int, str] = {
    1: "Divide radical expressions and simplify (integer, fractional, variable, and higher-root problems)",
    2: "Simplify expressions with rational exponents and power-of-a-radical problems",
    3: "Multiply radical expressions and simplify the result",
}


# ═══════════════════════════════════════════════════════════════
#  Math utilities
# ═══════════════════════════════════════════════════════════════

def simplify_sqrt(n: int) -> Tuple[int, int]:
    """Return (outside, inside) such that sqrt(n) = outside * sqrt(inside)."""
    outside, inside = 1, n
    for p in [2, 3, 5, 7, 11, 13]:
        while inside % (p * p) == 0:
            outside *= p
            inside //= p * p
    return outside, inside


# ═══════════════════════════════════════════════════════════════
#  Individual question builders
#  Each returns  Tuple[prompt: str, question_latex: str, answer_latex: str]
# ═══════════════════════════════════════════════════════════════

def _q_div_integer(var_min, var_max, root_min, root_max):
    """sqrt(res^2 * d) / sqrt(d) = res"""
    res   = random.randint(4, 12)
    denom = random.choice([2, 3, 5, 6, 10])
    num   = (res ** 2) * denom
    return (
        "Simplify:",
        f"$$\\frac{{\\sqrt{{{num}}}}}{{\\sqrt{{{denom}}}}}$$",
        f"$${res}$$",
    )


def _q_div_frac_radical(var_min, var_max, root_min, root_max):
    """sqrt(a^2 * k) / sqrt(b^2) = (a * sqrt(k)) / b"""
    b    = random.choice([5, 7, 8, 9, 10, 11])
    k    = random.choice([2, 3, 5, 6])
    a_sq = random.choice([4, 9, 16])
    a    = int(math.isqrt(a_sq))
    q    = f"$$\\frac{{\\sqrt{{{a_sq * k}}}}}{{\\sqrt{{{b ** 2}}}}}$$"
    a_s  = (f"\\frac{{{a}}}{{{b}}}" if k == 1
            else f"\\frac{{{a}\\sqrt{{{k}}}}}{{{b}}}")
    return ("Simplify:", q, f"$${a_s}$$")


def _q_div_variables(var_min, var_max, root_min, root_max):
    """sqrt(c * v^m) / sqrt(c' * v^n) with variables"""
    var   = random.choice(["x", "y", "a", "b", "n"])
    c_res = random.randint(2, 6)
    c_den = random.choice([2, 3, 5])
    c_num = (c_res ** 2) * c_den
    p_num = random.randint(max(var_min + 2, 6), max(var_max, 7))
    p_den = random.randint(var_min, max(var_min, min(var_max, p_num - 2)))
    if p_den >= p_num:
        p_den = max(var_min, p_num - 2)
    q = (f"$$\\frac{{\\sqrt{{{c_num}{var}^{{{p_num}}}}}}}"
         f"{{\\sqrt{{{c_den}{var}^{{{p_den}}}}}}}$$")
    diff     = p_num - p_den
    out_pow  = diff // 2
    has_sqrt = diff % 2 == 1
    c_str    = str(c_res) if c_res != 1 else ""
    v_str    = ("" if out_pow == 0 else var if out_pow == 1
                else f"{var}^{{{out_pow}}}")
    r_str    = f"\\sqrt{{{var}}}" if has_sqrt else ""
    inner    = c_str + v_str + r_str
    return ("Simplify:", q, f"$${inner if inner else '1'}$$")


def _q_div_higher_root(var_min, var_max, root_min, root_max):
    """n-th root division: result is c_res * a"""
    root      = random.randint(root_min, root_max)
    c_res     = random.randint(2, 4)
    c_den     = random.choice([2, 3])
    c_num     = (c_res ** root) * c_den
    p_den_val = root - 1
    p_num_val = root + p_den_val
    var       = "a"
    q = (f"$$\\frac{{\\sqrt[{root}]{{{c_num}{var}^{{{p_num_val}}}}}}}"
         f"{{\\sqrt[{root}]{{{c_den}{var}^{{{p_den_val}}}}}}}$$")
    return ("Simplify:", q, f"$${c_res}{var}$$")


def _q_power_radical(var_min, var_max, root_min, root_max):
    """(n-th root of x^p)^mult = x^(p*mult/n)"""
    root   = random.randint(root_min, root_max)
    p      = random.randint(2, max(2, var_max // max(root, 1) + 1))
    mult   = root * random.randint(1, 2)
    q      = f"$$\\left(\\sqrt[{root}]{{x^{{{p}}}}}\\right)^{{{mult}}}$$"
    g      = math.gcd(p * mult, root)
    en, ed = (p * mult) // g, root // g
    a      = (f"$$x^{{{en}}}$$" if ed == 1
              else f"$$x^{{\\frac{{{en}}}{{{ed}}}}}$$")
    return ("Simplify:", q, a)


def _q_rational_exp_fixed(var_min, var_max, root_min, root_max):
    """Fixed anchor problem: x^(9/4) / x^(1/4) = x^2"""
    return (
        "Simplify:",
        r"$$\frac{x^{\frac{9}{4}}}{x^{\frac{1}{4}}}$$",
        r"$$x^{2}$$",
    )


def _q_rational_exp_random(var_min, var_max, root_min, root_max):
    """x^(top/q) / x^(bot/q) = x^((top-bot)/q)"""
    q      = random.choice([2, 3, 4])
    top    = random.randint(q + 1, 3 * q)
    bottom = random.randint(1, top - 1)
    diff_n = top - bottom
    g      = math.gcd(diff_n, q)
    en, ed = diff_n // g, q // g
    a      = (f"$$x^{{{en}}}$$" if ed == 1
              else f"$$x^{{\\frac{{{en}}}{{{ed}}}}}$$")
    return (
        "Simplify:",
        f"$$\\frac{{x^{{\\frac{{{top}}}{{{q}}}}}}}{{x^{{\\frac{{{bottom}}}{{{q}}}}}}}$$",
        a,
    )


def _q_multiply(var_min, var_max, root_min, root_max):
    """sqrt(c1*m) * sqrt(c2*m^e) = simplified"""
    c1             = random.randint(2, 5)
    c2             = random.randint(2, 5)
    e              = random.randint(max(var_min, 2), max(var_max, 3))
    out_coeff, rem = simplify_sqrt(c1 * c2)
    q              = f"$$\\sqrt{{{c1}m}} \\cdot \\sqrt{{{c2}m^{{{e}}}}}$$"
    total_vp       = 1 + e
    out_vp         = total_vp // 2
    rem_vp         = total_vp % 2
    c_str          = str(out_coeff) if out_coeff != 1 else ""
    v_str          = (f"m^{{{out_vp}}}" if out_vp > 1 else
                      "m" if out_vp == 1 else "")
    rad_inner      = (str(rem) if rem != 1 else "") + ("m" if rem_vp == 1 else "")
    r_str          = f"\\sqrt{{{rad_inner}}}" if rad_inner else ""
    inner          = c_str + v_str + r_str
    return ("Multiply and simplify:", q, f"$${inner if inner else '1'}$$")


# ── Section pools ─────────────────────────────────────────────

_POOLS = {
    1: [_q_div_integer, _q_div_frac_radical, _q_div_variables, _q_div_higher_root],
    2: [_q_power_radical, _q_rational_exp_fixed, _q_rational_exp_random],
    3: [_q_multiply],
}


def _gen_section(sec: int, count: int,
                 var_min: int, var_max: int,
                 root_min: int, root_max: int) -> List[Tuple]:
    pool = _POOLS[sec]
    return [pool[i % len(pool)](var_min, var_max, root_min, root_max)
            for i in range(count)]


def _q_starts(sections: List[int], section_counts: Dict[int, int]) -> Dict[int, int]:
    starts, n = {}, 1
    for s in sorted(sections):
        starts[s] = n
        n += section_counts[s]
    return starts


# ═══════════════════════════════════════════════════════════════
#  TXT builder  ->  bytes
# ═══════════════════════════════════════════════════════════════

def _render_txt_version(buf: io.StringIO, v: int, test_title: str,
                        sections: List[int], section_counts: Dict[int, int],
                        var_min: int, var_max: int,
                        root_min: int, root_max: int,
                        name_label: str, date_label: str, period_label: str):
    starts = _q_starts(sections, section_counts)
    all_qs = {s: _gen_section(s, section_counts[s], var_min, var_max, root_min, root_max)
              for s in sorted(sections)}

    buf.write("=" * 60 + "\n")
    buf.write(f"VERSION {v}  —  {test_title}\n")
    buf.write("=" * 60 + "\n\n")
    buf.write(f"{name_label}: ______________________  "
              f"{date_label}: __________  {period_label}: ____\n\n")

    for s in sorted(sections):
        qs = all_qs[s]
        s0 = starts[s]
        s1 = s0 + len(qs) - 1
        buf.write("-" * 60 + "\n")
        buf.write(f"  SECTION {s} — {SECTION_TITLES[s]}  (Q{s0}–Q{s1})\n")
        buf.write("-" * 60 + "\n\n")
        for li, (prompt, q_tex, _) in enumerate(qs):
            buf.write(f"{s0 + li}.  {prompt}\n\n     {q_tex}\n\n\n")

    buf.write("=" * 60 + "\n")
    buf.write(f"  ANSWER KEY — VERSION {v}\n")
    buf.write("=" * 60 + "\n\n")
    for s in sorted(sections):
        qs = all_qs[s]
        s0 = starts[s]
        buf.write(f"  Section {s} — {SECTION_TITLES[s]}\n")
        buf.write("  " + "-" * 44 + "\n")
        for li, (_, _, a_tex) in enumerate(qs):
            buf.write(f"  {s0 + li:2d}.  {a_tex}\n")
        buf.write("\n")
    buf.write("\n\n")


def build_txt_bytes(
    num_versions: int,
    test_title: str,
    sections: List[int],
    section_counts: Dict[int, int],
    var_min: int,
    var_max: int,
    root_min: int,
    root_max: int,
    name_label: str = "Name",
    date_label: str = "Date",
    period_label: str = "Period",
) -> bytes:
    """Build a complete multi-version TXT worksheet. Returns UTF-8 bytes."""
    buf = io.StringIO()
    buf.write(
        "=" * 60 + "\n"
        "GOOGLE DOCS / AUTO-LATEX INSTRUCTIONS\n"
        + "=" * 60 + "\n"
        "Open this file in Google Docs, then:\n"
        "  Extensions → Add-ons → Get add-ons\n"
        "  → search 'Auto-LaTeX Equations' → install\n"
        "  → Extensions → Auto-LaTeX Equations → Start\n"
        "  Every $$ ... $$ block becomes a rendered math image.\n"
        + "=" * 60 + "\n\n\n"
    )
    for v in range(1, num_versions + 1):
        _render_txt_version(buf, v, test_title, sections, section_counts,
                            var_min, var_max, root_min, root_max,
                            name_label, date_label, period_label)
    return buf.getvalue().encode("utf-8")


# ═══════════════════════════════════════════════════════════════
#  PDF builder  ->  bytes
# ═══════════════════════════════════════════════════════════════

def _render_math_png(plt, latex_str: str, fontsize: int = 14, dpi: int = 200):
    """Render a $$...$$ string to an in-memory PNG.
    Returns (BytesIO, width_pts, height_pts).
    """
    math = latex_str.strip().strip("$")
    fig  = plt.figure()
    ax   = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    txt  = ax.text(0.5, 0.5, f"${math}$", fontsize=fontsize,
                   ha="center", va="center", usetex=False)
    fig.canvas.draw()
    bb   = txt.get_window_extent(renderer=fig.canvas.get_renderer())
    w_in = (bb.width + 40) / dpi
    h_in = (bb.height + 24) / dpi
    fig.set_size_inches(w_in, h_in)
    png  = io.BytesIO()
    fig.savefig(png, format="png", dpi=dpi, bbox_inches="tight",
                pad_inches=0.05, transparent=True)
    plt.close(fig)
    png.seek(0)
    return png, w_in * 72, h_in * 72  # convert inches -> pts (72 pts per inch)


def _build_pdf_version(story, plt, Image, Paragraph, Spacer,
                       HRFlowable, KeepTogether, Table, TableStyle,
                       PageBreak, ParagraphStyle,
                       styles, colors, inch,
                       v: int, test_title: str,
                       sections: List[int], section_counts: Dict[int, int],
                       var_min: int, var_max: int,
                       root_min: int, root_max: int,
                       name_label: str, date_label: str, period_label: str):

    normal  = styles["Normal"]
    h1      = styles["h1"]
    # Use version-unique style names to avoid ReportLab caching conflicts
    sec_sty = ParagraphStyle(f"SecHead_v{v}", parent=normal,
                              fontSize=11, fontName="Helvetica-Bold", spaceAfter=4)
    key_sty = ParagraphStyle(f"KeyHead_v{v}", parent=normal,
                              fontSize=10, fontName="Helvetica-Bold",
                              textColor=colors.HexColor("#444444"))

    MAX_Q = 4.5 * inch
    MAX_A = 3.5 * inch

    def _img(latex_str, fs=14, max_w=MAX_Q):
        png, w, h = _render_math_png(plt, latex_str, fontsize=fs)
        if w > max_w:
            h *= max_w / w
            w  = max_w
        return Image(png, width=w, height=h)

    # ── Header ────────────────────────────────────────────────
    story.append(Paragraph(f"<b>VERSION {v}</b>  —  {test_title}", h1))
    story.append(Spacer(1, 6))
    hdr_tbl = Table([[
        Paragraph(f"{name_label}: ________________________________", normal),
        Paragraph(f"{date_label}: _____________", normal),
        Paragraph(f"{period_label}: ______", normal),
    ]], colWidths=[3.2 * inch, 2.2 * inch, 1.6 * inch])
    hdr_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(hdr_tbl)
    story.append(Spacer(1, 10))

    starts = _q_starts(sections, section_counts)
    all_qs = {s: _gen_section(s, section_counts[s], var_min, var_max, root_min, root_max)
              for s in sorted(sections)}

    # ── Questions ─────────────────────────────────────────────
    for s in sorted(sections):
        qs = all_qs[s]
        s0 = starts[s]
        s1 = s0 + len(qs) - 1
        story.append(HRFlowable(width="100%", thickness=1,
                                color=colors.HexColor("#888888")))
        story.append(Paragraph(
            f"SECTION {s} — {SECTION_TITLES[s]}"
            f"   <font size='9'>(Q{s0}–Q{s1})</font>", sec_sty))
        story.append(Spacer(1, 4))
        for li, (prompt, q_tex, _) in enumerate(qs):
            qn  = s0 + li
            img = _img(q_tex)
            row = Table(
                [[Paragraph(f"<b>{qn}.</b>  {prompt}", normal), img]],
                colWidths=[1.3 * inch, img.drawWidth + 0.2 * inch],
            )
            row.setStyle(TableStyle([
                ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]))
            story.append(KeepTogether(row))
        story.append(Spacer(1, 8))

    # ── Answer key ────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1.5,
                            color=colors.HexColor("#333333")))
    story.append(Paragraph(f"<b>ANSWER KEY — VERSION {v}</b>", sec_sty))
    story.append(Spacer(1, 4))
    for s in sorted(sections):
        qs = all_qs[s]
        s0 = starts[s]
        story.append(Paragraph(
            f"<b>Section {s} — {SECTION_TITLES[s]}</b>", key_sty))
        for li, (_, _, a_tex) in enumerate(qs):
            qn  = s0 + li
            img = _img(a_tex, fs=11, max_w=MAX_A)
            row = Table(
                [[Paragraph(f"<b>{qn}.</b>", normal), img]],
                colWidths=[0.4 * inch, img.drawWidth + 0.1 * inch],
            )
            row.setStyle(TableStyle([
                ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(row)
        story.append(Spacer(1, 6))

    story.append(PageBreak())


def build_pdf_bytes(
    num_versions: int,
    test_title: str,
    sections: List[int],
    section_counts: Dict[int, int],
    var_min: int,
    var_max: int,
    root_min: int,
    root_max: int,
    name_label: str = "Name",
    date_label: str = "Date",
    period_label: str = "Period",
) -> bytes:
    """Build a complete multi-version PDF worksheet. Returns raw PDF bytes.
    matplotlib and reportlab are imported lazily here — only when PDF is needed.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units     import inch
    from reportlab.lib.styles    import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib           import colors
    from reportlab.platypus      import (SimpleDocTemplate, Paragraph, Spacer,
                                         Image, PageBreak, HRFlowable,
                                         Table, TableStyle, KeepTogether)

    styles  = getSampleStyleSheet()
    out_buf = io.BytesIO()
    doc     = SimpleDocTemplate(
        out_buf, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch,  bottomMargin=0.75 * inch,
    )
    story = []
    for v in range(1, num_versions + 1):
        _build_pdf_version(
            story, plt, Image, Paragraph, Spacer,
            HRFlowable, KeepTogether, Table, TableStyle,
            PageBreak, ParagraphStyle,
            styles, colors, inch,
            v, test_title, sections, section_counts,
            var_min, var_max, root_min, root_max,
            name_label, date_label, period_label,
        )
    doc.build(story)
    out_buf.seek(0)
    return out_buf.read()


# ═══════════════════════════════════════════════════════════════
#  quick_generate  (convenience wrapper for CLI / scripted use)
# ═══════════════════════════════════════════════════════════════

def quick_generate(
    num_versions:   int             = 5,
    test_title:     str             = "Algebra 2 Test: Simplifying Radicals",
    sections:       Optional[List[int]]      = None,
    section_counts: Optional[Dict[int, int]] = None,
    var_min:        int             = 1,
    var_max:        int             = 10,
    root_min:       int             = 2,
    root_max:       int             = 5,
    name_label:     str             = "Name",
    date_label:     str             = "Date",
    period_label:   str             = "Period",
    fmt:            str             = "both",   # "txt" | "pdf" | "both"
    txt_path:       Optional[str]   = None,
    pdf_path:       Optional[str]   = None,
) -> dict:
    """
    Generate worksheets and (optionally) save to disk.

    Returns
    -------
    {
        "txt_bytes": bytes | None,
        "pdf_bytes": bytes | None,
        "txt_path":  str   | None,   # set only when txt_path arg was given
        "pdf_path":  str   | None,   # set only when pdf_path arg was given
    }
    """
    if sections is None:
        sections = [1, 2, 3]
    if section_counts is None:
        section_counts = {s: SECTION_Q_DEFAULTS[s] for s in sections}

    sections = sorted(sections)
    kwargs = dict(
        num_versions=num_versions, test_title=test_title,
        sections=sections, section_counts=section_counts,
        var_min=var_min, var_max=var_max,
        root_min=root_min, root_max=root_max,
        name_label=name_label, date_label=date_label, period_label=period_label,
    )
    result = {"txt_bytes": None, "pdf_bytes": None,
              "txt_path":  None, "pdf_path":  None}

    if fmt in ("txt", "both"):
        result["txt_bytes"] = build_txt_bytes(**kwargs)
        if txt_path:
            with open(txt_path, "wb") as fh:
                fh.write(result["txt_bytes"])
            result["txt_path"] = os.path.abspath(txt_path)

    if fmt in ("pdf", "both"):
        result["pdf_bytes"] = build_pdf_bytes(**kwargs)
        if pdf_path:
            with open(pdf_path, "wb") as fh:
                fh.write(result["pdf_bytes"])
            result["pdf_path"] = os.path.abspath(pdf_path)

    return result


# ═══════════════════════════════════════════════════════════════
#  Interactive CLI menu
# ═══════════════════════════════════════════════════════════════

def _ask(prompt, valid=None, default=None, cast=None):
    while True:
        raw = input(prompt).strip()
        if raw == "" and default is not None:
            raw = str(default)
        if cast is not None:
            try:
                value = cast(raw)
            except (ValueError, TypeError):
                print("    ✗  Invalid value — please try again.")
                continue
        else:
            value = raw
        if valid is not None and str(value) not in [str(v) for v in valid]:
            print(f"    ✗  Choose from: {' / '.join(str(v) for v in valid)}")
            continue
        print(f"    ✓  {value}")
        return value


def interactive_menu():
    while True:
        print("\n" + "=" * 64)
        print("   ALGEBRA 2 RADICAL TEST GENERATOR  (CLI)")
        print("=" * 64 + "\n")

        raw = input("  1/8  Title [default: Algebra 2 Test: Simplifying Radicals]: ").strip()
        test_title = raw or "Algebra 2 Test: Simplifying Radicals"

        print("\n  2/8  Sections and question counts")
        for s, t in SECTION_TITLES.items():
            lo, hi = SECTION_Q_BOUNDS[s]
            print(f"       {s}  {t}  (1–{hi} questions)")
        sections = []
        while not sections:
            raw = _ask("       Sections [default: 1,2,3]: ", default="1,2,3")
            for part in raw.replace(" ", "").split(","):
                if part in ("1", "2", "3") and int(part) not in sections:
                    sections.append(int(part))
        sections.sort()
        section_counts = {}
        for s in sections:
            lo, hi = SECTION_Q_BOUNDS[s]
            dq     = SECTION_Q_DEFAULTS[s]
            print(f"\n       Section {s} — {SECTION_TITLES[s]}")
            while True:
                c = _ask(f"         Questions ({lo}–{hi}) [default: {dq}]: ",
                         cast=int, default=dq)
                if lo <= c <= hi:
                    section_counts[s] = c
                    break

        print("\n  3/8  Root index range  (2=sqrt  3=cbrt  4=4th-root …)")
        while True:
            root_min = _ask("       Min (2–10) [default: 2]: ", cast=int, default=2)
            if 2 <= root_min <= 10:
                break
        while True:
            root_max = _ask(f"       Max ({root_min}–10) [default: {max(root_min, 3)}]: ",
                            cast=int, default=max(root_min, 3))
            if root_min <= root_max <= 10:
                break

        print("\n  4/8  Variable exponent range")
        while True:
            var_min = _ask("       Min (1–20) [default: 1]: ", cast=int, default=1)
            if 1 <= var_min <= 20:
                break
        while True:
            var_max = _ask(f"       Max ({var_min}–20) [default: {max(var_min, 10)}]: ",
                           cast=int, default=max(var_min, 10))
            if var_min <= var_max <= 20:
                break

        print("\n  5/8  Number of versions")
        while True:
            nv = _ask("       How many? (1–100) [default: 33]: ", cast=int, default=33)
            if 1 <= nv <= 100:
                break

        print("\n  6/8  Student header labels")
        name_lbl   = input("       Name field   [default: Name]:   ").strip() or "Name"
        date_lbl   = input("       Date field   [default: Date]:   ").strip() or "Date"
        period_lbl = input("       Period field [default: Period]: ").strip() or "Period"

        print("\n  7/8  Export format")
        print("       1 TXT only   2 PDF only   3 Both [default]")
        fmt_key = _ask("       Choose (1/2/3): ", valid=["1", "2", "3"], default="3")
        fmt     = {"1": "txt", "2": "pdf", "3": "both"}[fmt_key]

        print("\n  8/8  Output file names")
        safe = test_title.replace(" ", "_").replace(":", "").replace("/", "-")[:40]
        base = f"{safe}_v{nv}_sec{''.join(str(s) for s in sections)}"
        txt_path = pdf_path = None
        if fmt in ("txt", "both"):
            txt_path = _ask(f"       TXT [default: {base}.txt]: ", default=f"{base}.txt")
        if fmt in ("pdf", "both"):
            pdf_path = _ask(f"       PDF [default: {base}.pdf]: ", default=f"{base}.pdf")

        confirm = input("\n  Enter to GENERATE, 'r' to restart: ").strip().lower()
        if confirm == "r":
            continue

        print("\n  Generating…")
        result = quick_generate(
            num_versions=nv, test_title=test_title,
            sections=sections, section_counts=section_counts,
            var_min=var_min, var_max=var_max,
            root_min=root_min, root_max=root_max,
            name_label=name_lbl, date_label=date_lbl, period_label=period_lbl,
            fmt=fmt, txt_path=txt_path, pdf_path=pdf_path,
        )
        if result["txt_path"]:
            print(f"  ✓ TXT  →  {result['txt_path']}")
        if result["pdf_path"]:
            print(f"  ✓ PDF  →  {result['pdf_path']}")
        print("  Done! 📐\n")
        break


if __name__ == "__main__":
    interactive_menu()
