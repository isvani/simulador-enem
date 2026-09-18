"""
Ferramenta pontual: recorta as imagens das alternativas (graficos/formulas
estruturais) das 4 questoes da FUVEST 2024 Prova V cujas alternativas sao
so imagem (19, 26, 60, 72), usando as coordenadas dos boxes de tabela
(achadas via page.get_drawings()) em vez de tentar OCR/heuristica.

Uso:
    python scripts/_extract_fuvest_pending_images.py
"""
import json
import uuid
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = ROOT / "scripts" / "_pdf_cache" / "fuvest2024_primeira_fase_prova_V.pdf"
IMAGENS_DIR = ROOT / "dados" / "imagens"

# (indice_questao, pagina_0idx, x0, x1, [(letra, y0, y1), ...])
GEOMETRIA = [
    (19, 6, 340.4, 545.3, [
        ("A", 202.1, 292.0), ("B", 292.0, 380.6), ("C", 380.6, 470.5),
        ("D", 470.5, 559.7), ("E", 559.7, 650.8),
    ]),
    (26, 9, 57.1, 283.0, [
        ("A", 389.8, 523.3), ("B", 523.8, 657.3), ("C", 657.8, 791.8),
    ]),
    (26, 9, 334.9, 560.8, [
        ("D", 41.3, 174.8), ("E", 175.3, 309.3),
    ]),
    (60, 21, 332.9, 560.8, [
        ("A", 112.1, 242.5), ("B", 245.8, 376.2), ("C", 379.6, 509.9),
        ("D", 513.3, 643.7), ("E", 647.0, 778.0),
    ]),
    (72, 27, 57.1, 283.0, [
        ("A", 253.2, 355.4), ("B", 355.9, 458.1), ("C", 458.6, 560.8),
        ("D", 561.3, 663.5), ("E", 664.0, 766.7),
    ]),
]


def main() -> None:
    IMAGENS_DIR.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(PDF_PATH)
    result: dict[int, dict[str, str]] = {}

    for idx, page_no, x0, x1, rows in GEOMETRIA:
        page = doc[page_no]
        result.setdefault(idx, {})
        for letter, y0, y1 in rows:
            clip = fitz.Rect(x0 + 1, y0 + 1, x1 - 1, y1 - 1)
            pix = page.get_pixmap(clip=clip, dpi=250)
            fname = f"{uuid.uuid4()}.png"
            out_path = IMAGENS_DIR / fname
            pix.save(str(out_path))
            result[idx][letter] = f"/imagens/{fname}"
            print(f"fuvest-2024-{idx} {letter}: {fname}")

    out_json = ROOT / "scripts" / "_pdf_cache" / "fuvest_pending_images.json"
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nMapa salvo em {out_json}")


if __name__ == "__main__":
    main()
