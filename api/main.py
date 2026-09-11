"""
Fase 4 - Motor de simulados v1.

Backend FastAPI que serve o banco de questoes (dados/banco_questoes.json)
filtrado/amostrado sob demanda, grava tentativas/respostas em SQLite
(dados/simulados.db) e serve o frontend estatico (web/).

Uso:
    python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
(rodar a partir da raiz do projeto, pra os paths relativos baterem)

Simplificacao deliberada pro MVP: GET /questoes devolve
correct_alternative junto com a questao (correcao e feita no cliente).
Nao ha login/sessao — "nome" e so um identificador de texto livre pra
separar historico, como decidido na secao 5.2 do planejamento. Sem
preocupacao de seguranca adicional porque o servidor roda em rede local,
sem dados sensiveis.
"""
import json
import random
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
DADOS_DIR = ROOT / "dados"
WEB_DIR = ROOT / "web"
BANCO_PATH = DADOS_DIR / "banco_questoes.json"
DB_PATH = DADOS_DIR / "simulados.db"

BANCO: list[dict] = []
BANCO_BY_ID: dict[str, dict] = {}


def carregar_banco() -> None:
    global BANCO, BANCO_BY_ID
    BANCO = json.loads(BANCO_PATH.read_text(encoding="utf-8"))
    BANCO_BY_ID = {q["id"]: q for q in BANCO}


def init_db() -> None:
    DADOS_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tentativas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_usuario TEXT NOT NULL,
                data TEXT NOT NULL,
                filtros_usados TEXT,
                total_questoes INTEGER NOT NULL,
                total_acertos INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS respostas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tentativa_id INTEGER NOT NULL REFERENCES tentativas(id),
                questao_id TEXT NOT NULL,
                source TEXT,
                area TEXT,
                subtopic TEXT,
                difficulty TEXT,
                resposta_usuario TEXT,
                resposta_correta TEXT,
                acertou INTEGER NOT NULL,
                tempo_gasto_segundos REAL
            )
            """
        )
        # Migracao pra bancos criados antes do campo de tempo existir:
        # ALTER TABLE so roda se a coluna ainda nao existir.
        colunas = {row[1] for row in conn.execute("PRAGMA table_info(respostas)").fetchall()}
        if "tempo_gasto_segundos" not in colunas:
            conn.execute("ALTER TABLE respostas ADD COLUMN tempo_gasto_segundos REAL")
        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    carregar_banco()
    init_db()
    yield


app = FastAPI(title="Simulador ENEM", lifespan=lifespan)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def parse_list_param(value: Optional[str]) -> Optional[list[str]]:
    if not value:
        return None
    return [v.strip() for v in value.split(",") if v.strip()]


def questoes_ja_respondidas(nome: str) -> set[str]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT r.questao_id
            FROM respostas r
            JOIN tentativas t ON t.id = r.tentativa_id
            WHERE t.nome_usuario = ?
            """,
            (nome,),
        ).fetchall()
    return {row["questao_id"] for row in rows}


def sample_weighted(candidatos: list[dict], pesos: list[float], n: int) -> list[dict]:
    """Amostragem ponderada sem reposicao (Efraimidis-Spirakis): cada item
    recebe uma chave aleatoria elevada ao inverso do peso; pega-se os N
    maiores. Peso 0 (ou negativo) ainda recebe uma chave positiva
    minuscula, pra continuar elegivel como fallback quando faltarem
    questoes ineditas (ver secao 5.5 do planejamento)."""
    keyed = []
    for q, peso in zip(candidatos, pesos):
        if peso <= 0:
            chave = random.random() * 1e-12
        else:
            chave = random.random() ** (1.0 / peso)
        keyed.append((chave, q))
    keyed.sort(key=lambda item: item[0], reverse=True)
    return [q for _, q in keyed[:n]]


@app.get("/meta")
def get_meta():
    sources = sorted({q["source"] for q in BANCO})
    areas = sorted({q["area"] for q in BANCO})
    subtopics_by_area = {
        area: sorted({q["subtopic"] for q in BANCO if q["area"] == area and q["subtopic"]})
        for area in areas
    }
    years = [q["year"] for q in BANCO]
    return {
        "sources": sources,
        "areas": areas,
        "subtopics_by_area": subtopics_by_area,
        "difficulties": ["facil", "medio", "dificil"],
        "year_min": min(years),
        "year_max": max(years),
        "total_questoes": len(BANCO),
    }


@app.get("/questoes")
def get_questoes(
    source: Optional[str] = None,
    area: Optional[str] = None,
    subtopic: Optional[str] = None,
    difficulty: Optional[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    n: int = Query(10, ge=1, le=200),
    exploracao: float = Query(0.7, ge=0.0, le=1.0),
    nome: Optional[str] = None,
):
    sources = parse_list_param(source)
    areas = parse_list_param(area)
    subtopics = parse_list_param(subtopic)
    difficulties = parse_list_param(difficulty)

    candidatos = BANCO
    if sources:
        candidatos = [q for q in candidatos if q["source"] in sources]
    if areas:
        candidatos = [q for q in candidatos if q["area"] in areas]
    if subtopics:
        candidatos = [q for q in candidatos if q["subtopic"] in subtopics]
    if difficulties:
        candidatos = [q for q in candidatos if q["difficulty"] in difficulties]
    if year_min is not None:
        candidatos = [q for q in candidatos if q["year"] >= year_min]
    if year_max is not None:
        candidatos = [q for q in candidatos if q["year"] <= year_max]

    if not candidatos:
        raise HTTPException(404, "Nenhuma questão encontrada para esses filtros.")

    respondidas = questoes_ja_respondidas(nome) if nome else set()
    pesos = [1.0 if q["id"] not in respondidas else (1.0 - exploracao) for q in candidatos]

    n_efetivo = min(n, len(candidatos))
    selecionadas = sample_weighted(candidatos, pesos, n_efetivo)
    random.shuffle(selecionadas)
    return {"total_disponivel": len(candidatos), "questoes": selecionadas}


class RespostaIn(BaseModel):
    questao_id: str
    resposta_usuario: Optional[str] = None
    tempo_gasto_segundos: Optional[float] = None


class TentativaIn(BaseModel):
    nome: str
    filtros_usados: dict = {}
    respostas: list[RespostaIn]


@app.post("/tentativas")
def post_tentativa(payload: TentativaIn):
    nome = payload.nome.strip()
    if not nome:
        raise HTTPException(400, "Nome do usuário é obrigatório.")
    if not payload.respostas:
        raise HTTPException(400, "Nenhuma resposta enviada.")

    linhas = []
    total_acertos = 0
    for r in payload.respostas:
        q = BANCO_BY_ID.get(r.questao_id)
        if not q:
            raise HTTPException(404, f"Questão {r.questao_id} não encontrada.")
        acertou = bool(r.resposta_usuario) and r.resposta_usuario == q["correct_alternative"]
        total_acertos += int(acertou)
        linhas.append(
            {
                "questao_id": q["id"],
                "source": q["source"],
                "area": q["area"],
                "subtopic": q["subtopic"],
                "difficulty": q["difficulty"],
                "resposta_usuario": r.resposta_usuario,
                "resposta_correta": q["correct_alternative"],
                "acertou": int(acertou),
                "tempo_gasto_segundos": r.tempo_gasto_segundos,
            }
        )

    agora = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO tentativas (nome_usuario, data, filtros_usados, total_questoes, total_acertos)
            VALUES (?, ?, ?, ?, ?)
            """,
            (nome, agora, json.dumps(payload.filtros_usados, ensure_ascii=False), len(payload.respostas), total_acertos),
        )
        tentativa_id = cur.lastrowid
        conn.executemany(
            """
            INSERT INTO respostas
                (tentativa_id, questao_id, source, area, subtopic, difficulty,
                 resposta_usuario, resposta_correta, acertou, tempo_gasto_segundos)
            VALUES
                (:tentativa_id, :questao_id, :source, :area, :subtopic, :difficulty,
                 :resposta_usuario, :resposta_correta, :acertou, :tempo_gasto_segundos)
            """,
            [{**linha, "tentativa_id": tentativa_id} for linha in linhas],
        )
        conn.commit()

    return {
        "tentativa_id": tentativa_id,
        "data": agora,
        "total_questoes": len(payload.respostas),
        "total_acertos": total_acertos,
        "respostas": linhas,
    }


@app.get("/tentativas/{nome}")
def get_tentativas(nome: str):
    with get_conn() as conn:
        tentativas = conn.execute(
            "SELECT * FROM tentativas WHERE nome_usuario = ? ORDER BY data DESC", (nome,)
        ).fetchall()
        resultado = []
        for t in tentativas:
            respostas = conn.execute(
                "SELECT * FROM respostas WHERE tentativa_id = ?", (t["id"],)
            ).fetchall()
            resultado.append(
                {
                    "id": t["id"],
                    "data": t["data"],
                    "filtros_usados": json.loads(t["filtros_usados"]) if t["filtros_usados"] else {},
                    "total_questoes": t["total_questoes"],
                    "total_acertos": t["total_acertos"],
                    "respostas": [dict(r) for r in respostas],
                }
            )
    return resultado


SEM_CLASSIFICACAO = "(sem classificação)"


def _agrupar_contagem(itens: list[dict], campo: str) -> dict[str, int]:
    contagem: dict[str, int] = {}
    for item in itens:
        chave = item.get(campo) or SEM_CLASSIFICACAO
        contagem[chave] = contagem.get(chave, 0) + 1
    return contagem


def _percentual_por_chave(
    acertos_por_chave: dict[str, int], total_por_chave: dict[str, int]
) -> dict[str, dict]:
    resultado = {}
    for chave, total in total_por_chave.items():
        acertos = acertos_por_chave.get(chave, 0)
        resultado[chave] = {
            "acertos": acertos,
            "total": total,
            "percentual": round(100 * acertos / total, 1) if total else 0.0,
        }
    return resultado


@app.get("/dashboard/{nome}")
def get_dashboard(nome: str):
    """Ver planejamento secao 5.3/5.4: performance usa so a ULTIMA
    resposta de cada questao distinta (nao penaliza erro ja corrigido);
    cobertura conta cada questao distinta uma vez so, independente de
    quantas vezes foi respondida."""
    with get_conn() as conn:
        linhas = conn.execute(
            """
            SELECT r.questao_id, r.source, r.area, r.subtopic, r.difficulty, r.acertou
            FROM respostas r
            JOIN tentativas t ON t.id = r.tentativa_id
            WHERE t.nome_usuario = ?
            ORDER BY t.data ASC, t.id ASC
            """,
            (nome,),
        ).fetchall()

    ultima_por_questao: dict[str, dict] = {}
    for linha in linhas:
        ultima_por_questao[linha["questao_id"]] = dict(linha)
    respostas_validas = list(ultima_por_questao.values())

    # Performance: sobre o conjunto de ultimas respostas distintas.
    acertos_totais = sum(r["acertou"] for r in respostas_validas)
    total_respondidas = len(respostas_validas)
    acertadas = [r for r in respostas_validas if r["acertou"]]

    performance = {
        "geral": {
            "acertos": acertos_totais,
            "total": total_respondidas,
            "percentual": round(100 * acertos_totais / total_respondidas, 1) if total_respondidas else 0.0,
        },
        "por_area": _percentual_por_chave(
            _agrupar_contagem(acertadas, "area"), _agrupar_contagem(respostas_validas, "area")
        ),
        "por_subtopic": _percentual_por_chave(
            _agrupar_contagem(acertadas, "subtopic"), _agrupar_contagem(respostas_validas, "subtopic")
        ),
        "por_difficulty": _percentual_por_chave(
            _agrupar_contagem(acertadas, "difficulty"), _agrupar_contagem(respostas_validas, "difficulty")
        ),
        "por_source": _percentual_por_chave(
            _agrupar_contagem(acertadas, "source"), _agrupar_contagem(respostas_validas, "source")
        ),
    }

    # Cobertura: questoes distintas respondidas (qualquer resultado) vs total no banco.
    def cobertura_por_chave(campo: str) -> dict[str, dict]:
        respondidas = _agrupar_contagem(respostas_validas, campo)
        total_banco = _agrupar_contagem(BANCO, campo)
        resultado = {}
        for chave, total in total_banco.items():
            resp = respondidas.get(chave, 0)
            resultado[chave] = {
                "respondidas": resp,
                "total": total,
                "percentual": round(100 * resp / total, 1) if total else 0.0,
            }
        return resultado

    cobertura = {
        "geral": {
            "respondidas": total_respondidas,
            "total": len(BANCO),
            "percentual": round(100 * total_respondidas / len(BANCO), 1) if BANCO else 0.0,
        },
        "por_area": cobertura_por_chave("area"),
        "por_subtopic": cobertura_por_chave("subtopic"),
        "por_difficulty": cobertura_por_chave("difficulty"),
        "por_source": cobertura_por_chave("source"),
    }

    # Tempo de resposta: ao contrario de performance/cobertura, usa TODAS
    # as respostas cronometradas (nao so a ultima por questao), porque o
    # objetivo aqui e ver evolucao de velocidade ao longo do tempo, nao
    # um retrato final. "media_geral" = media historica completa;
    # "media_ultimos_5" = media so das ultimas 5 respostas cronometradas
    # daquele grupo, pra comparar contra a media geral e ver se esta
    # ficando mais rapido ou mais lento.
    with get_conn() as conn:
        linhas_tempo = conn.execute(
            """
            SELECT r.area, r.subtopic, r.difficulty, r.tempo_gasto_segundos
            FROM respostas r
            JOIN tentativas t ON t.id = r.tentativa_id
            WHERE t.nome_usuario = ? AND r.tempo_gasto_segundos IS NOT NULL
            ORDER BY t.data ASC, r.id ASC
            """,
            (nome,),
        ).fetchall()

    def tempo_por_chave(campo: str) -> dict[str, dict]:
        grupos: dict[str, list[float]] = {}
        for linha in linhas_tempo:
            chave = linha[campo] or SEM_CLASSIFICACAO
            grupos.setdefault(chave, []).append(linha["tempo_gasto_segundos"])
        resultado = {}
        for chave, tempos in grupos.items():
            ultimos5 = tempos[-5:]
            resultado[chave] = {
                "media_geral_segundos": round(sum(tempos) / len(tempos), 1),
                "amostras_geral": len(tempos),
                "media_ultimos_5_segundos": round(sum(ultimos5) / len(ultimos5), 1),
                "amostras_recentes": len(ultimos5),
            }
        return resultado

    todos_tempos = [linha["tempo_gasto_segundos"] for linha in linhas_tempo]
    ultimos5_geral = todos_tempos[-5:]
    tempo = {
        "geral": {
            "media_geral_segundos": round(sum(todos_tempos) / len(todos_tempos), 1) if todos_tempos else None,
            "amostras_geral": len(todos_tempos),
            "media_ultimos_5_segundos": round(sum(ultimos5_geral) / len(ultimos5_geral), 1) if ultimos5_geral else None,
            "amostras_recentes": len(ultimos5_geral),
        },
        "por_area": tempo_por_chave("area"),
        "por_subtopic": tempo_por_chave("subtopic"),
        "por_difficulty": tempo_por_chave("difficulty"),
    }

    return {"nome": nome, "performance": performance, "cobertura": cobertura, "tempo": tempo}


# Servido por ultimo: qualquer rota nao reconhecida acima cai pros
# arquivos estaticos de web/ (index.html na raiz).
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
