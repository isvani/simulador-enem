"""
Fase 2 (follow-up): completa as 12 questoes do ENEM 2024/2025 cujas
alternativas sao graficos/diagramas (dados/questoes_pendentes_imagem.json),
anexando uma imagem por alternativa e movendo cada questao para o banco
principal.

Para 11 das 12 questoes, cada alternativa e uma imagem raster (JPEG/JP2)
ja embutida no PDF como XObject proprio - extraida bit a bit via
doc.extract_image(xref), sem perda de qualidade. So a questao 112 (2024,
heredograma) tem as alternativas desenhadas como paths vetoriais (linhas
+ circulos/quadrados), entao e rasterizada a partir da pagina com
page.get_pixmap(clip=..., dpi=300).

As coordenadas/xrefs abaixo foram achados via scripts/_inspect_images.py
e scripts/_inspect_enem_page.py (ver planejamento).

Uso:
    python scripts/_complete_pending_images_enem.py
"""
import json
import uuid
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "scripts" / "_pdf_cache"
IMAGENS_DIR = ROOT / "dados" / "imagens"
BANCO_PATH = ROOT / "dados" / "banco_questoes.json"
PENDING_PATH = ROOT / "dados" / "questoes_pendentes_imagem.json"

LETTERS = "ABCDE"

# (id, pdf, pagina 1-idx, {letra: xref})
RASTER_QUESTOES = [
    ("enem-2024-121", "2024_PV_impresso_D2_CD7.pdf", 10, {"A": 66, "B": 67, "C": 68, "D": 69, "E": 70}),
    ("enem-2024-127", "2024_PV_impresso_D2_CD7.pdf", 12, {"A": 81, "B": 82, "C": 83, "D": 84, "E": 85}),
    ("enem-2024-131", "2024_PV_impresso_D2_CD7.pdf", 14, {"A": 102, "B": 103, "C": 104, "D": 105, "E": 106}),
    ("enem-2024-161", "2024_PV_impresso_D2_CD7.pdf", 23, {"A": 169, "B": 170, "C": 171, "D": 172, "E": 173}),
    ("enem-2024-168", "2024_PV_impresso_D2_CD7.pdf", 26, {"A": 194, "B": 195, "C": 196, "D": 197, "E": 198}),
    ("enem-2024-174", "2024_PV_impresso_D2_CD7.pdf", 29, {"A": 226, "B": 227, "C": 228, "D": 229, "E": 230}),
    ("enem-2025-107", "2025_PV_impresso_D2_CD7.pdf", 6, {"A": 38, "B": 41, "C": 42, "D": 43, "E": 44}),
    ("enem-2025-108", "2025_PV_impresso_D2_CD7.pdf", 6, {"A": 46, "B": 48, "C": 50, "D": 52, "E": 40}),
    ("enem-2025-127", "2025_PV_impresso_D2_CD7.pdf", 12, {"A": 170, "B": 172, "C": 174, "D": 176, "E": 178}),
    ("enem-2025-135", "2025_PV_impresso_D2_CD7.pdf", 15, {"A": 226, "B": 227, "C": 228, "D": 229, "E": 230}),
    ("enem-2025-138", "2025_PV_impresso_D2_CD7.pdf", 17, {"A": 263, "B": 264, "C": 265, "D": 266, "E": 267}),
]

# enem-2024-112: heredograma vetorial (sem XObject de imagem por
# alternativa) - recortado da pagina renderizada. Coluna direita
# (x 286-545); limites de linha = ponto medio entre os marcadores "A".."E"
# (achados em scripts/_inspect_enem_page.py), com folga manual no topo
# (abaixo do enunciado, em y=385.4) e no fundo (acima do rodape, em
# y=749.6).
VECTOR_QUESTAO = {
    "id": "enem-2024-112",
    "pdf": "2024_PV_impresso_D2_CD7.pdf",
    "page": 7,
    "x0": 308.0,
    "x1": 430.0,
    "rows": {
        "A": (386.5, 454.0),
        "B": (454.0, 526.0),
        "C": (526.0, 598.0),
        "D": (598.0, 670.0),
        "E": (670.0, 741.0),
    },
}


WEB_SAFE_EXTS = {"png", "jpg", "jpeg"}


def save_raster(doc: fitz.Document, xref: int) -> str:
    info = doc.extract_image(xref)
    ext = info["ext"]
    if ext in WEB_SAFE_EXTS:
        fname = f"{uuid.uuid4()}.{ext}"
        (IMAGENS_DIR / fname).write_bytes(info["image"])
        return f"/imagens/{fname}"

    # Formatos que navegadores nao decodificam nativamente (ex.: JPEG2000/jpx,
    # usado em alguns paths do ENEM 2024) - reconverte pra PNG via Pixmap.
    pix = fitz.Pixmap(info["image"])
    if pix.colorspace and pix.colorspace.name not in ("DeviceRGB", "DeviceGray"):
        pix = fitz.Pixmap(fitz.csRGB, pix)
    fname = f"{uuid.uuid4()}.png"
    pix.save(str(IMAGENS_DIR / fname))
    return f"/imagens/{fname}"


def save_vector_crop(page: fitz.Page, x0: float, x1: float, y0: float, y1: float) -> str:
    clip = fitz.Rect(x0, y0, x1, y1)
    pix = page.get_pixmap(clip=clip, dpi=300)
    fname = f"{uuid.uuid4()}.png"
    pix.save(str(IMAGENS_DIR / fname))
    return f"/imagens/{fname}"


def apply_files(question: dict, files_by_letter: dict[str, str]) -> None:
    for alt in question["alternatives"]:
        alt["text"] = ""
        alt["file"] = files_by_letter[alt["letter"]]
        alt["is_correct"] = alt["letter"] == question["correct_alternative"]


def main() -> None:
    IMAGENS_DIR.mkdir(parents=True, exist_ok=True)
    banco = json.loads(BANCO_PATH.read_text(encoding="utf-8"))
    pending = json.loads(PENDING_PATH.read_text(encoding="utf-8"))
    pending_by_id = {q["id"]: q for q in pending}

    completed_ids = []
    open_docs: dict[str, fitz.Document] = {}

    def get_doc(pdf_name: str) -> fitz.Document:
        if pdf_name not in open_docs:
            open_docs[pdf_name] = fitz.open(PDF_DIR / pdf_name)
        return open_docs[pdf_name]

    for qid, pdf_name, page_no, xrefs in RASTER_QUESTOES:
        question = pending_by_id[qid]
        doc = get_doc(pdf_name)
        files_by_letter = {letter: save_raster(doc, xref) for letter, xref in xrefs.items()}
        apply_files(question, files_by_letter)
        banco.append(question)
        completed_ids.append(qid)
        print(f"{qid}: " + ", ".join(f"{l}={f}" for l, f in files_by_letter.items()))

    v = VECTOR_QUESTAO
    question = pending_by_id[v["id"]]
    doc = get_doc(v["pdf"])
    page = doc[v["page"] - 1]
    files_by_letter = {
        letter: save_vector_crop(page, v["x0"], v["x1"], y0, y1) for letter, (y0, y1) in v["rows"].items()
    }
    apply_files(question, files_by_letter)
    banco.append(question)
    completed_ids.append(v["id"])
    print(f"{v['id']}: " + ", ".join(f"{l}={f}" for l, f in files_by_letter.items()))

    remaining = [q for q in pending if q["id"] not in completed_ids]

    BANCO_PATH.write_text(json.dumps(banco, ensure_ascii=False, indent=2), encoding="utf-8")
    PENDING_PATH.write_text(json.dumps(remaining, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nQuestoes completadas e movidas para o banco: {len(completed_ids)}")
    print(f"Restam pendentes: {len(remaining)}")


if __name__ == "__main__":
    main()
