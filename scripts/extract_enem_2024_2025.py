"""
Fase 2 - Extracao ENEM 2024 e 2025 a partir dos PDFs oficiais do INEP
(caderno Azul, dias 1 e 2) para o schema unificado do projeto.

Os PDFs sao baixados previamente (ver download_enem_pdfs.py) para
scripts/_pdf_cache/{ano}_PV_impresso_D{dia}_CD{caderno}.pdf (prova) e
scripts/_pdf_cache/{ano}_GB_impresso_D{dia}_CD{caderno}.pdf (gabarito).

Uso:
    python scripts/extract_enem_2024_2025.py

Mescla o resultado em dados/banco_questoes.json (nao sobrescreve as
questoes 2009-2023 ja extraidas na Fase 1).

Limitacoes conhecidas (ver planejamento, secao 2.2):
- Questoes que dependem de figura/grafico para fazer sentido ficam com
  o contexto textual incompleto (extracao e so de texto, sem
  rasterizacao de pagina nesta passada).
- "context" e "alternatives_introduction" nao sao separados como no
  schema do enem-api: aqui tudo o que precede as alternativas fica em
  "context" e "alternatives_introduction" fica vazio, porque nao ha um
  jeito confiavel de achar esse corte so com texto corrido do PDF.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "scripts" / "_pdf_cache"
OUT = ROOT / "dados" / "banco_questoes.json"

YEARS = [2024, 2025]
CADERNO_BY_DAY = {1: 1, 2: 7}  # Azul, em ambos os dias/anos confirmado por busca
DAY_AREAS = {
    1: [(1, 45, "linguagens"), (46, 90, "ciencias-humanas")],
    2: [(91, 135, "ciencias-natureza"), (136, 180, "matematica")],
}

QUESTION_RE = re.compile(r"^QUEST[ÃA]O\s*(\d+)\s*$", re.IGNORECASE)
ALT_RE = re.compile(r"^([A-E])\t(.*)$")
LANGUAGE_SECTION_RE = re.compile(r"\(op[cç][aã]o (ingl[eê]s|espanhol)\)", re.IGNORECASE)
SECTION_HEADER_RE = re.compile(r"^Quest[õo]es de \d+ a \d+", re.IGNORECASE)
REDACAO_START_RE = re.compile(r"^(PROPOSTA DE REDA[ÇC][ÃA]O|INSTRU[ÇC][ÕO]ES PARA A REDA[ÇC][ÃA]O)", re.IGNORECASE)
BARCODE_RE = re.compile(r"^\*[0-9A-Za-z]+\*$")
FOOTER_TRAILER_RE = re.compile(r"[•|].*CADERNO|CADERNO.*[•|]")


def clean_page_lines(page_text: str) -> list[str]:
    lines = page_text.split("\n")
    cleaned = []
    skip_next_if_digit = False
    for raw_line in lines:
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        if skip_next_if_digit:
            skip_next_if_digit = False
            if re.fullmatch(r"\d+", stripped):
                continue

        if BARCODE_RE.match(stripped):
            continue
        if stripped.count("ENEM") > 3 and len(stripped) > 100:
            continue
        if FOOTER_TRAILER_RE.search(stripped):
            skip_next_if_digit = True
            continue

        cleaned.append(line)
    return cleaned


def parse_pdf_text_lines(pdf_path: Path) -> list[str]:
    import fitz

    doc = fitz.open(pdf_path)
    lines: list[str] = []
    for page in doc:
        lines.extend(clean_page_lines(page.get_text()))
    return lines


def parse_questions(lines: list[str], max_index: int) -> dict[tuple[int, str | None], dict]:
    questions: dict[tuple[int, str | None], dict] = {}
    current_key = None
    current_context: list[str] = []
    current_alts: dict[str, list[str]] = {}
    current_alt_letter = None
    pending_language = None
    in_redacao_skip = False
    done = False

    def flush():
        nonlocal current_key, current_context, current_alts, current_alt_letter
        if current_key is not None and current_alts:
            questions[current_key] = {
                "context": " ".join(current_context).strip(),
                "alternatives": {
                    letter: " ".join(parts).strip() for letter, parts in current_alts.items()
                },
            }
        current_key = None
        current_context = []
        current_alts = {}
        current_alt_letter = None

    for line in lines:
        if done:
            break

        stripped = line.strip()
        if not stripped:
            continue

        if REDACAO_START_RE.match(stripped):
            in_redacao_skip = True
            continue

        m = LANGUAGE_SECTION_RE.search(stripped)
        if m:
            pending_language = m.group(1).lower().replace("ê", "e")
            in_redacao_skip = False
            continue

        if SECTION_HEADER_RE.match(stripped):
            in_redacao_skip = False
            continue

        qm = QUESTION_RE.match(stripped)
        if qm:
            flush()
            in_redacao_skip = False
            index = int(qm.group(1))
            language = pending_language if index <= 5 else None
            current_key = (index, language)
            continue

        if in_redacao_skip or current_key is None:
            continue

        am = ALT_RE.match(line)
        if am:
            letter, text = am.group(1), am.group(2)
            current_alt_letter = letter
            current_alts[letter] = [text.strip()]
        elif current_alt_letter is not None:
            current_alts[current_alt_letter].append(stripped)
        else:
            current_context.append(stripped)

        if current_key[0] == max_index and len(current_alts) == 5 and current_alt_letter == "E":
            done = True

    flush()
    return questions


def parse_gabarito(pdf_path: Path) -> dict[int, str | None]:
    import fitz

    doc = fitz.open(pdf_path)
    tokens: list[str] = []
    for page in doc:
        for raw_line in page.get_text().split("\n"):
            stripped = raw_line.strip()
            if stripped and stripped not in ("QUESTÃO", "GABARITO"):
                tokens.append(stripped)

    gabarito: dict[int, str | None] = {}
    i = 0
    while i < len(tokens):
        is_index = re.fullmatch(r"\d+", tokens[i])
        next_is_answer = i + 1 < len(tokens) and (
            re.fullmatch(r"[A-E]", tokens[i + 1]) or tokens[i + 1] == "Anulado"
        )
        if is_index and next_is_answer:
            index = int(tokens[i])
            answer = tokens[i + 1]
            gabarito[index] = answer if answer != "Anulado" else None
            i += 2
        else:
            i += 1
    return gabarito


def area_for_index(day: int, index: int) -> str:
    for start, end, area in DAY_AREAS[day]:
        if start <= index <= end:
            return area
    raise ValueError(f"index {index} fora do intervalo esperado para o dia {day}")


def build_id(year: int, index: int, language: str | None) -> str:
    if language:
        return f"enem-{year}-{index}-{language}"
    return f"enem-{year}-{index}"


def extract_year(year: int) -> tuple[list[dict], list[int]]:
    results = []
    missing_indices: list[int] = []
    for day, areas in DAY_AREAS.items():
        caderno = CADERNO_BY_DAY[day]
        pv_path = PDF_DIR / f"{year}_PV_impresso_D{day}_CD{caderno}.pdf"
        gb_path = PDF_DIR / f"{year}_GB_impresso_D{day}_CD{caderno}.pdf"
        max_index = areas[-1][1]

        lines = parse_pdf_text_lines(pv_path)
        parsed = parse_questions(lines, max_index)
        gabarito = parse_gabarito(gb_path)

        covered = {index for index, _language in parsed.keys()}
        expected = set(range(areas[0][0], areas[-1][1] + 1))
        missing_indices.extend(sorted(expected - covered))

        for (index, language), data in sorted(parsed.items()):
            alternatives = [
                {
                    "letter": letter,
                    "text": data["alternatives"].get(letter, ""),
                    "file": None,
                    "is_correct": data["alternatives"].get(letter, "") != ""
                    and letter == gabarito.get(index),
                }
                for letter in "ABCDE"
            ]
            results.append(
                {
                    "id": build_id(year, index, language),
                    "source": "enem",
                    "year": year,
                    "area": area_for_index(day, index),
                    "subtopic": None,
                    "difficulty": None,
                    "language": language,
                    "context": data["context"],
                    "alternatives_introduction": "",
                    "alternatives": alternatives,
                    "correct_alternative": gabarito.get(index),
                    "files": [],
                }
            )
    return results, missing_indices


PENDING_OUT = ROOT / "dados" / "questoes_pendentes_imagem.json"


def main() -> None:
    existing = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else []
    existing_pending = json.loads(PENDING_OUT.read_text(encoding="utf-8")) if PENDING_OUT.exists() else []
    existing_by_id = {q["id"]: q for q in existing}
    kept = [q for q in existing if q["year"] not in YEARS]
    kept_pending = [q for q in existing_pending if q["year"] not in YEARS]

    all_new: list[dict] = []
    missing_by_year: dict[int, list[int]] = {}
    for year in YEARS:
        year_questions, missing_indices = extract_year(year)
        all_new.extend(year_questions)
        missing_by_year[year] = missing_indices

    # Re-rodar a extracao (ex.: via --update-questions) nao pode apagar
    # subtopic/difficulty que ja foram classificados (Fase 3) para
    # questoes que ja existiam no banco — isso e enriquecimento feito
    # por fora, nao vem do PDF. Preserva o que ja tinha, so atualiza os
    # campos que vem mesmo da extracao (context, alternativas, gabarito
    # etc.), caso o parser tenha sido melhorado.
    for q in all_new:
        anterior = existing_by_id.get(q["id"])
        if anterior:
            q["subtopic"] = anterior.get("subtopic")
            q["difficulty"] = anterior.get("difficulty")

    complete = [q for q in all_new if all(a["text"] for a in q["alternatives"])]
    incomplete = [q for q in all_new if not all(a["text"] for a in q["alternatives"])]

    merged = kept + complete
    merged_pending = kept_pending + incomplete

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    PENDING_OUT.write_text(json.dumps(merged_pending, ensure_ascii=False, indent=2), encoding="utf-8")

    by_year: dict[int, int] = {}
    for q in complete:
        by_year[q["year"]] = by_year.get(q["year"], 0) + 1

    annulled = [q["id"] for q in complete if q["correct_alternative"] is None]

    print(f"Total completo extraido: {len(complete)} questoes")
    print("Por ano:")
    for year, n in sorted(by_year.items()):
        print(f"  {year}: {n}")
    print(f"Anuladas (sem gabarito, mantidas no banco): {len(annulled)} -> {annulled}")
    print(f"Pendentes (alternativa em imagem, precisam de leitura visual): {len(incomplete)}")
    if incomplete:
        print("  " + ", ".join(q["id"] for q in incomplete))
    for year, missing in missing_by_year.items():
        if missing:
            print(f"Indices nao capturados de forma alguma em {year} (layout quebrado no parser): {missing}")
    print(f"Total no banco apos merge: {len(merged)}")
    print(f"Salvo em: {OUT}")
    print(f"Pendentes salvas em: {PENDING_OUT}")


if __name__ == "__main__":
    main()
