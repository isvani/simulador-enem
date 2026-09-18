"""
Fase 5 - Extracao da FUVEST (1a fase, prova de conhecimentos gerais) a
partir do PDF oficial, para o schema unificado do projeto.

PDFs oficiais em https://www.fuvest.br/wp-content/uploads/, padrao de URL:
  fuvest{ano}_primeira_fase_prova_{LETRA}.pdf   (prova, uma por versao V/K/Q/X/Z)
  fuvest{ano}_gabarito_primeira_fase.pdf         (gabarito, cobre as 5 versoes)
Baixados manualmente para scripts/_pdf_cache/ (mesmo diretorio do ENEM,
ja gitignored) - nao ha bloqueio de acesso, ao contrario do INEP.

Uso:
    python scripts/extract_fuvest.py

Mescla o resultado em dados/banco_questoes.json (source="fuvest").

Diferencas de layout em relacao ao parser do ENEM
(extract_enem_2024_2025.py):
- Numero da questao e uma linha solta com 2 digitos (com zero a
  esquerda: "01".."09"), nao "QUESTAO N". Como isso pode colidir com
  numeros soltos que aparecem dentro de tabelas do proprio enunciado
  (ex.: um valor "70" dentro da Tabela I da questao 33 desta prova), so
  aceitamos a linha como fronteira de questao quando ela bate com o
  proximo indice esperado em sequencia (1, 2, 3, ... 90) - qualquer
  numero fora dessa sequencia e tratado como parte do enunciado.
- Alternativas vem como "(A) texto", nao "A<TAB>texto".
- Texto-base compartilhado por varias questoes vem com cabecalho
  explicito "TEXTO PARA A(S) QUESTAO(OES) ..." nomeando os indices
  atendidos - diferente do ENEM (onde esse cabecalho e mais generico e
  o texto compartilhado acabava ficando preso na questao anterior, bug
  so descoberto e corrigido depois via scripts de recuperacao). Aqui
  aproveitamos o cabecalho para anexar o texto certo em cada questao
  contemplada desde a primeira extracao.

Limitacao conhecida (mesma classe do ENEM Fase 2): sem rasterizacao de
pagina, questoes que dependem de figura ficam com contexto incompleto.
Alem disso, nesta prova o PDF usa uma fonte com CMap quebrado para
alguns simbolos matematicos (raiz, fracoes com expoente/indice) que o
PyMuPDF decodifica para pontos de codigo Unicode errados (ex.: caem no
bloco Oriya). Questoes/alternativas com esses glifos suspeitos sao
desviadas para dados/questoes_pendentes_revisao_fuvest.json em vez de
entrar no banco principal, ate serem conferidas visualmente.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "scripts" / "_pdf_cache"
OUT = ROOT / "dados" / "banco_questoes.json"
PENDING_OUT = ROOT / "dados" / "questoes_pendentes_revisao_fuvest.json"

YEAR = 2024
PROVA_LETRA = "V"
TOTAL_QUESTOES = 90
PROVA_ORDER = ["V", "K", "Q", "X", "Z"]

QUESTION_NUM_RE = re.compile(r"^\d{2}$")
ALT_RE = re.compile(r"^\(([A-E])\)\s*(.*)$")
SHARED_TEXT_HEADER_RE = re.compile(r"^TEXTO PARA A[S]? QUEST(?:[ÃA]O|[ÕO]ES)\b(.*)", re.IGNORECASE)
FOOTER_RE = re.compile(r"^Concurso Vestibular FUVEST \d{4} - Prova [A-Z]$")
RASCUNHO_RE = re.compile(r"^RASCUNHO$")

# Faixas Unicode que so aparecem neste PDF por causa do CMap quebrado da
# fonte matematica (glifos de expoente/indice mapeados para pontos de
# codigo de escritas indianas ou para a Area de Uso Privado) - nao tem
# nenhum uso legitimo em uma prova em portugues. Simbolos matematicos de
# verdade (grego, setas, operadores, italico matematico Unicode como
# "𝑓(𝑥)") ficam fora dessas faixas e nao sao sinalizados.
SUSPICIOUS_RANGES = [
    (0x0900, 0x0DFF),  # Devanagari ... Malayalam (blocos de escritas indianas)
    (0xA700, 0xA7FF),  # Latin Extended-D (viu-se glifo isolado nessa faixa)
    (0xE000, 0xF8FF),  # Area de Uso Privado
]


def has_suspicious_glyphs(text: str) -> bool:
    return any(
        any(start <= ord(ch) <= end for start, end in SUSPICIOUS_RANGES) for ch in text
    )


def parse_shared_targets(header_rest: str) -> set[int]:
    nums = [int(n) for n in re.findall(r"\d+", header_rest)]
    if not nums:
        return set()
    if re.search(r"\bDE\b", header_rest, re.IGNORECASE) and re.search(r"\bA\b", header_rest, re.IGNORECASE):
        return set(range(nums[0], nums[-1] + 1))
    return set(nums)


def load_prova_lines(pdf_path: Path) -> list[str]:
    import fitz

    doc = fitz.open(pdf_path)
    lines: list[str] = []
    stopped = False
    for page in doc:
        if stopped:
            break
        for raw_line in page.get_text().split("\n"):
            stripped = raw_line.strip()
            if RASCUNHO_RE.match(stripped):
                stopped = True
                break
            if not stripped or FOOTER_RE.match(stripped):
                continue
            lines.append(stripped)
    return lines


def parse_questions(lines: list[str]) -> tuple[dict[int, dict], list[int]]:
    questions: dict[int, dict] = {}
    current_index: int | None = None
    current_context: list[str] = []
    current_alts: dict[str, list[str]] = {}
    current_alt_letter: str | None = None
    expected_next = 1
    shared_lines: list[str] = []
    shared_targets: set[int] = set()
    collecting_shared = False

    def flush():
        nonlocal current_index, current_context, current_alts, current_alt_letter
        if current_index is not None and current_alts:
            questions[current_index] = {
                "context": " ".join(current_context).strip(),
                "alternatives": {
                    letter: " ".join(parts).strip() for letter, parts in current_alts.items()
                },
            }
        current_index = None
        current_context = []
        current_alts = {}
        current_alt_letter = None

    for line in lines:
        header_m = SHARED_TEXT_HEADER_RE.match(line)
        if header_m:
            flush()
            shared_targets = parse_shared_targets(header_m.group(1))
            shared_lines = []
            collecting_shared = True
            continue

        num_m = QUESTION_NUM_RE.match(line)
        if num_m and int(line) == expected_next and expected_next <= TOTAL_QUESTOES:
            flush()
            current_index = expected_next
            if expected_next in shared_targets:
                current_context = list(shared_lines)
                if expected_next >= max(shared_targets):
                    shared_targets = set()
                    shared_lines = []
            collecting_shared = False
            expected_next += 1
            continue

        if collecting_shared:
            shared_lines.append(line)
            continue

        if current_index is None:
            continue

        am = ALT_RE.match(line)
        if am:
            letter, text = am.group(1), am.group(2)
            current_alt_letter = letter
            current_alts[letter] = [text.strip()] if text.strip() else []
        elif current_alt_letter is not None:
            current_alts[current_alt_letter].append(line)
        else:
            current_context.append(line)

    flush()
    missing = sorted(set(range(1, TOTAL_QUESTOES + 1)) - questions.keys())
    return questions, missing


def parse_gabarito(pdf_path: Path, prova_letra: str) -> dict[int, str]:
    import fitz

    doc = fitz.open(pdf_path)
    tokens: list[str] = []
    for page in doc:
        for raw_line in page.get_text().split("\n"):
            stripped = raw_line.strip()
            if stripped:
                tokens.append(stripped)

    start = next(i for i, t in enumerate(tokens) if "CORRESPOND" in t.upper())
    col_index = PROVA_ORDER.index(prova_letra)  # posicao da prova entre V,K,Q,X,Z

    gabarito: dict[int, str] = {}
    i = start
    while i < len(tokens):
        if re.fullmatch(r"[A-E]", tokens[i]):
            row = tokens[i : i + 6]
            if len(row) == 6 and all(re.fullmatch(r"\d+", t) for t in row[1:]):
                answer = row[0]
                question_num = int(row[1 + col_index])
                gabarito[question_num] = answer
                i += 6
                continue
        i += 1
    return gabarito


def build_questions(parsed: dict[int, dict], gabarito: dict[int, str]) -> tuple[list[dict], list[dict]]:
    complete: list[dict] = []
    pending: list[dict] = []
    for index, data in sorted(parsed.items()):
        alt_texts = data["alternatives"]
        alternatives = [
            {
                "letter": letter,
                "text": alt_texts.get(letter, ""),
                "file": None,
                "is_correct": bool(alt_texts.get(letter)) and letter == gabarito.get(index),
            }
            for letter in "ABCDE"
        ]
        question = {
            "id": f"fuvest-{YEAR}-{index}",
            "source": "fuvest",
            "year": YEAR,
            "area": None,
            "subtopic": None,
            "difficulty": None,
            "language": None,
            "context": data["context"],
            "alternatives_introduction": "",
            "alternatives": alternatives,
            "correct_alternative": gabarito.get(index),
            "files": [],
        }
        suspicious = has_suspicious_glyphs(question["context"]) or any(
            has_suspicious_glyphs(a["text"]) for a in alternatives
        )
        has_all_alts = all(a["text"] for a in alternatives)
        has_answer = question["correct_alternative"] is not None
        if suspicious or not has_all_alts or not has_answer:
            question["_motivo_pendencia"] = (
                ("glifos_suspeitos " if suspicious else "")
                + ("alternativa_faltando " if not has_all_alts else "")
                + ("sem_gabarito " if not has_answer else "")
            ).strip()
            pending.append(question)
        else:
            complete.append(question)
    return complete, pending


def main() -> None:
    prova_path = PDF_DIR / f"fuvest{YEAR}_primeira_fase_prova_{PROVA_LETRA}.pdf"
    gabarito_path = PDF_DIR / f"fuvest{YEAR}_gabarito_primeira_fase.pdf"

    lines = load_prova_lines(prova_path)
    parsed, missing = parse_questions(lines)
    gabarito = parse_gabarito(gabarito_path, PROVA_LETRA)

    complete, pending = build_questions(parsed, gabarito)

    existing = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else []
    kept = [q for q in existing if not (q["source"] == "fuvest" and q["year"] == YEAR)]
    merged = kept + complete
    OUT.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    PENDING_OUT.write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Questoes reconhecidas no PDF: {len(parsed)} de {TOTAL_QUESTOES}")
    if missing:
        print(f"Indices nao capturados (layout quebrado no parser): {missing}")
    print(f"Completas (adicionadas ao banco): {len(complete)}")
    print(f"Pendentes de revisao visual: {len(pending)}")
    if pending:
        for q in pending:
            print(f"  {q['id']}: {q['_motivo_pendencia']}")
    print(f"Total no banco apos merge: {len(merged)}")
    print(f"Salvo em: {OUT}")
    print(f"Pendentes salvas em: {PENDING_OUT}")


if __name__ == "__main__":
    main()
