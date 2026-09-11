"""
Fase 2 - Baixa os PDFs oficiais do INEP (prova e gabarito, caderno Azul,
dias 1 e 2) para ENEM 2024 e 2025.

Descoberta desta sessao: o dominio download.inep.gov.br devolve
"connection reset" tanto para `curl` (Git Bash) quanto para `urllib` do
Python nesta maquina — parece bloquear pela assinatura TLS/HTTP do
cliente. Só o `Invoke-WebRequest` do PowerShell funcionou. Por isso este
script chama o PowerShell via subprocess em vez de baixar direto em
Python.

Padrao de URL confirmado por busca (ver planejamento, secao 2.2):
  https://download.inep.gov.br/enem/provas_e_gabaritos/{ano}_PV_impresso_D{dia}_CD{caderno}.pdf
  https://download.inep.gov.br/enem/provas_e_gabaritos/{ano}_GB_impresso_D{dia}_CD{caderno}.pdf

Caderno Azul = CD1 no dia 1, CD7 no dia 2 (confirmado para 2024 e 2025).

Uso:
    python scripts/download_enem_pdfs.py
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "scripts" / "_pdf_cache"

YEARS = [2024, 2025]
CADERNO_BY_DAY = {1: 1, 2: 7}
BASE_URL = "https://download.inep.gov.br/enem/provas_e_gabaritos"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for year in YEARS:
        for day, caderno in CADERNO_BY_DAY.items():
            for tipo in ("PV", "GB"):
                name = f"{year}_{tipo}_impresso_D{day}_CD{caderno}"
                out_path = OUT_DIR / f"{name}.pdf"
                if out_path.exists():
                    print(f"{name}: ja existe, pulando")
                    continue
                url = f"{BASE_URL}/{name}.pdf"
                ps_cmd = (
                    f"$ProgressPreference='SilentlyContinue'; "
                    f"Invoke-WebRequest -Uri '{url}' -OutFile '{out_path}' -TimeoutSec 90"
                )
                result = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0 and out_path.exists():
                    print(f"{name}: OK ({out_path.stat().st_size} bytes)")
                else:
                    print(f"{name}: FALHOU - {result.stderr.strip()}")


if __name__ == "__main__":
    main()
