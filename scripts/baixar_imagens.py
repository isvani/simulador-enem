"""
Baixa todas as imagens referenciadas no banco de questoes (hoje
hospedadas em enem.dev) para dados/imagens/, e reescreve
dados/banco_questoes.json pra apontar pros arquivos locais em vez do
servidor externo.

Motivo: nao depender de bater no servidor de terceiros (enem.dev) toda
vez que alguem abre um simulado -- funciona offline, e nao fica na mao
da disponibilidade desse servidor.

Uso:
    python scripts/baixar_imagens.py

Idempotente: pula imagens ja baixadas. Se uma URL falhar (rede
instavel, imagem removida etc.), o banco mantem a URL externa original
pra aquela imagem especifica, em vez de referenciar um arquivo local
inexistente.
"""
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANCO_PATH = ROOT / "dados" / "banco_questoes.json"
IMAGENS_DIR = ROOT / "dados" / "imagens"

IMG_MD_RE = re.compile(r'!\[([^\]]*)\]\((https://enem\.dev[^)\s]+)((?:\s+"[^"]*")?)\)')
PREFIXO_LOCAL = "/imagens/"


def nome_local(url: str) -> str:
    return url.split("/")[-1]


def baixar(url: str, destino: Path) -> bool:
    if destino.exists():
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            destino.write_bytes(resp.read())
        return True
    except Exception as exc:
        print(f"  FALHOU: {url} -> {exc}")
        return False


def coletar_urls(banco: list[dict]) -> set[str]:
    urls: set[str] = set()
    for q in banco:
        urls.update(q.get("files") or [])
        for a in q["alternatives"]:
            if a.get("file"):
                urls.add(a["file"])
        for campo in ("context", "alternatives_introduction"):
            texto = q.get(campo)
            if texto:
                urls.update(m[1] for m in IMG_MD_RE.findall(texto))
        for a in q["alternatives"]:
            if a.get("text"):
                urls.update(m[1] for m in IMG_MD_RE.findall(a["text"]))
    return {u for u in urls if u.startswith("https://enem.dev/")}


def substituir_markdown(texto: str, sucesso: set[str]) -> str:
    def repl(m):
        alt, url, title = m.group(1), m.group(2), m.group(3)
        if url in sucesso:
            return f"![{alt}]({PREFIXO_LOCAL}{nome_local(url)}{title})"
        return m.group(0)

    return IMG_MD_RE.sub(repl, texto)


def main() -> None:
    IMAGENS_DIR.mkdir(parents=True, exist_ok=True)
    banco = json.loads(BANCO_PATH.read_text(encoding="utf-8"))

    urls = coletar_urls(banco)
    print(f"Total de imagens referenciadas (enem.dev): {len(urls)}")

    sucesso: set[str] = set()
    falhas: list[str] = []
    novas = 0
    for i, url in enumerate(sorted(urls), 1):
        destino = IMAGENS_DIR / nome_local(url)
        ja_existia = destino.exists()
        if baixar(url, destino):
            sucesso.add(url)
            if not ja_existia:
                novas += 1
        else:
            falhas.append(url)
        if i % 300 == 0:
            print(f"  processadas {i}/{len(urls)}...")

    print(f"Baixadas agora: {novas}")
    print(f"Ja existiam localmente: {len(sucesso) - novas}")
    print(f"Falharam: {len(falhas)}")
    for f in falhas[:20]:
        print(f"  {f}")

    for q in banco:
        q["files"] = [
            f"{PREFIXO_LOCAL}{nome_local(u)}" if u in sucesso else u for u in (q.get("files") or [])
        ]
        for a in q["alternatives"]:
            if a.get("file") and a["file"] in sucesso:
                a["file"] = f"{PREFIXO_LOCAL}{nome_local(a['file'])}"
        for campo in ("context", "alternatives_introduction"):
            texto = q.get(campo)
            if texto:
                q[campo] = substituir_markdown(texto, sucesso)
        for a in q["alternatives"]:
            if a.get("text"):
                a["text"] = substituir_markdown(a["text"], sucesso)

    BANCO_PATH.write_text(json.dumps(banco, ensure_ascii=False, indent=2), encoding="utf-8")

    tamanho_total = sum(f.stat().st_size for f in IMAGENS_DIR.glob("*") if f.is_file())
    print(f"Total em disco: {tamanho_total / 1024 / 1024:.1f} MB em {IMAGENS_DIR}")
    print("dados/banco_questoes.json reescrito com referencias locais.")


if __name__ == "__main__":
    main()
