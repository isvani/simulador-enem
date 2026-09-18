"""
Fase 5 - Teste de extracao de texto de um caderno da FUVEST (1a fase),
so pra confirmar viabilidade antes de escrever o parser definitivo.

Uso:
    python scripts/test_extract_fuvest.py
"""
import fitz  # pymupdf
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = ROOT / "scripts" / "_pdf_cache" / "fuvest2024_primeira_fase_prova_V.pdf"
GABARITO_PATH = ROOT / "scripts" / "_pdf_cache" / "fuvest2024_gabarito_primeira_fase.pdf"


def dump(path: Path, n_pages: int) -> None:
    doc = fitz.open(path)
    print(f"\n=== {path.name} ({doc.page_count} paginas) ===")
    for i in range(min(n_pages, doc.page_count)):
        text = doc[i].get_text()
        print(f"\n--- pagina {i + 1} ({len(text)} chars) ---")
        print(text[:1500])


if __name__ == "__main__":
    dump(PDF_PATH, 4)
    dump(GABARITO_PATH, 2)
