"""
Ferramenta pontual (nao faz parte do pipeline de extracao) pra localizar
a pagina/posicao de questoes especificas de uma prova da FUVEST no PDF
e renderizar a regiao correspondente como PNG, pra revisao visual das
poucas questoes que o extract_fuvest.py nao consegue resolver so com
texto (formula matematica com fonte quebrada, alternativa que e imagem).

Uso:
    python scripts/_locate_and_render_fuvest.py --pdf=fuvest2023_primeira_fase_prova_V.pdf 13 19 26
    python scripts/_locate_and_render_fuvest.py --pdf=... --outdir=... 13 19 26
"""
import re
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "scripts" / "_pdf_cache"
QUESTION_NUM_RE = re.compile(r"^\{?(\d{2})\}?$")
TOTAL_QUESTOES = 90


def locate_all(pdf_path: Path) -> dict[int, tuple[int, float, float]]:
    """Retorna {indice: (page_number, y0, y1)} - y1 e o topo da proxima questao
    (ou None se for a ultima da pagina/prova)."""
    doc = fitz.open(pdf_path)
    boundaries: list[tuple[int, int, float]] = []  # (indice, page_no, y0)
    expected_next = 1
    for page_no in range(doc.page_count):
        page = doc[page_no]
        d = page.get_text("dict")
        for block in d["blocks"]:
            for line in block.get("lines", []):
                text = "".join(span["text"] for span in line["spans"]).strip()
                m = QUESTION_NUM_RE.match(text)
                if m and int(m.group(1)) == expected_next and expected_next <= TOTAL_QUESTOES:
                    boundaries.append((expected_next, page_no, line["bbox"][1]))
                    expected_next += 1

    result: dict[int, tuple[int, float, float]] = {}
    for i, (idx, page_no, y0) in enumerate(boundaries):
        if i + 1 < len(boundaries):
            next_idx, next_page, next_y0 = boundaries[i + 1]
            # layout de 2 colunas: se a proxima questao "logica" esta mais
            # acima na pagina, e porque ela esta na proxima coluna, nao
            # embaixo desta - nesse caso vai ate o fim da pagina/coluna.
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
        out_path = out_dir / f"{prefix}_q{idx:02d}_page{page_no + 1}.png"
        pix.save(str(out_path))
        print(f"{idx}: pagina {page_no + 1}, salvo em {out_path}")


if __name__ == "__main__":
    pdf_arg = next(a for a in sys.argv[1:] if a.startswith("--pdf="))
    outdir_arg = next((a for a in sys.argv[1:] if a.startswith("--outdir=")), None)
    args = [a for a in sys.argv[1:] if not a.startswith("--outdir=") and not a.startswith("--pdf=")]

    pdf_path = PDF_DIR / pdf_arg.split("=", 1)[1]
    out_dir = Path(outdir_arg.split("=", 1)[1]) if outdir_arg else PDF_DIR / "render"
    indices = [int(a) for a in args]
    render(pdf_path, indices, out_dir)
