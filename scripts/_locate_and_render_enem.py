"""
Ferramenta pontual (nao faz parte do pipeline de extracao) pra localizar
a pagina de questoes especificas do ENEM no PDF oficial (dia 2, caderno
azul CD7) e renderizar a regiao correspondente como PNG, pra revisao
visual das questoes cujas alternativas sao graficos/diagramas (ver
dados/questoes_pendentes_imagem.json).

Uso:
    python scripts/_locate_and_render_enem.py --pdf=2024_PV_impresso_D2_CD7.pdf 112 121 127
"""
import re
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "scripts" / "_pdf_cache"
QUESTION_RE = re.compile(r"^QUEST[ÃA]O\s*(\d+)\s*$", re.IGNORECASE)
TOTAL_QUESTOES = 180


def locate_all(pdf_path: Path) -> dict[int, tuple[int, float, float | None]]:
    doc = fitz.open(pdf_path)
    boundaries: list[tuple[int, int, float]] = []
    for page_no in range(doc.page_count):
        page = doc[page_no]
        d = page.get_text("dict")
        for block in d["blocks"]:
            for line in block.get("lines", []):
                text = "".join(span["text"] for span in line["spans"]).strip()
                m = QUESTION_RE.match(text)
                if m and 1 <= int(m.group(1)) <= TOTAL_QUESTOES:
                    boundaries.append((int(m.group(1)), page_no, line["bbox"][1]))

    result: dict[int, tuple[int, float, float | None]] = {}
    for i, (idx, page_no, y0) in enumerate(boundaries):
        if i + 1 < len(boundaries):
            next_idx, next_page, next_y0 = boundaries[i + 1]
            y1 = next_y0 if (next_page == page_no and next_y0 > y0) else None
        else:
            y1 = None
        result[idx] = (page_no, y0, y1)
    return result


def render(pdf_path: Path, indices: list[int], out_dir: Path) -> None:
    doc = fitz.open(pdf_path)
    locations = locate_all(pdf_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = pdf_path.stem
    for idx in indices:
        if idx not in locations:
            print(f"{idx}: nao localizada")
            continue
        page_no, y0, y1 = locations[idx]
        page = doc[page_no]
        clip = fitz.Rect(page.rect.x0, max(page.rect.y0, y0 - 15), page.rect.x1, y1 + 15 if y1 else page.rect.y1)
        pix = page.get_pixmap(clip=clip, dpi=220)
        out_path = out_dir / f"{prefix}_q{idx:03d}_page{page_no + 1}.png"
        pix.save(str(out_path))
        print(f"{idx}: pagina {page_no + 1}, y0={y0:.1f} y1={y1}, salvo em {out_path}")


if __name__ == "__main__":
    pdf_arg = next(a for a in sys.argv[1:] if a.startswith("--pdf="))
    outdir_arg = next((a for a in sys.argv[1:] if a.startswith("--outdir=")), None)
    args = [a for a in sys.argv[1:] if not a.startswith("--outdir=") and not a.startswith("--pdf=")]

    pdf_path = PDF_DIR / pdf_arg.split("=", 1)[1]
    out_dir = Path(outdir_arg.split("=", 1)[1]) if outdir_arg else PDF_DIR / "render"
    indices = [int(a) for a in args]
    render(pdf_path, indices, out_dir)
