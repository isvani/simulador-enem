#!/usr/bin/env bash
# iniciar-simulador.bash
#
# Gerencia o Simulador ENEM: instala dependencias, sobe/derruba o
# servidor web e reseta historico de usuario.
#
# Uso (Git Bash no Windows, sempre a partir da raiz do repositorio):
#   bash iniciar-simulador.bash --start              Instala (so na 1a vez
#                                                     ou se as dependencias
#                                                     mudaram) e sobe o
#                                                     servidor em segundo
#                                                     plano; volta pro
#                                                     prompt assim que
#                                                     confirmar que subiu.
#                                                     Se ja tinha uma
#                                                     instancia rodando,
#                                                     reinicia ela, pra
#                                                     sempre servir o
#                                                     dados/banco_questoes.json
#                                                     mais recente (util
#                                                     depois de editar/
#                                                     substituir esse
#                                                     arquivo por fora).
#   bash iniciar-simulador.bash --stop               Para o servidor.
#   bash iniciar-simulador.bash --reset <nome>        Apaga o historico de
#                                                     tentativas/respostas
#                                                     daquele usuario
#                                                     (pede confirmacao).
#
# Pra re-extrair as questoes de 2024/2025 dos PDFs (raro — so quando o
# parser muda ou um PDF novo aparece), rode direto:
#   .venv/Scripts/python.exe scripts/extract_enem_2024_2025.py
#   .venv/Scripts/python.exe scripts/patch_enem_2024_2025_manual.py
# e depois "bash iniciar-simulador.bash --start" pra recarregar.
#
# Variaveis de ambiente opcionais (valem pra todos os comandos):
#   SIMULADOR_HOST=127.0.0.1   (padrao: 0.0.0.0, acessivel por outros
#                                dispositivos na mesma rede local, ex.: celular)
#   SIMULADOR_PORT=8080        (padrao: 8000)

set -euo pipefail

PROJETO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJETO_DIR/.venv"
MARCADOR_INSTALADO="$VENV_DIR/.instalado_ok"
REQUISITOS_API="$PROJETO_DIR/api/requirements.txt"
REQUISITOS_SCRIPTS="$PROJETO_DIR/scripts/requirements.txt"
LOG_DIR="$PROJETO_DIR/logs"
LOG_FILE="$LOG_DIR/servidor.log"
HOST="${SIMULADOR_HOST:-0.0.0.0}"
PORT="${SIMULADOR_PORT:-8000}"

# Forca UTF-8 em toda saida do Python (sem isso, mensagens com acento
# viram mojibake no console do Windows/Git Bash).
export PYTHONUTF8=1

VENV_PYTHON=""
PORTA_STATUS=""

mostrar_ajuda() {
  cat <<EOF
Uso: bash iniciar-simulador.bash <comando>

Comandos:
  --start              Instala dependencias (so se precisar) e sobe o
                        servidor em segundo plano — reiniciando uma
                        instancia anterior se houver, pra sempre carregar
                        o dados/banco_questoes.json mais recente.
  --stop               Para o servidor.
  --reset <nome>       Apaga o historico daquele usuario (com confirmacao).

Variaveis de ambiente opcionais: SIMULADOR_HOST, SIMULADOR_PORT.
EOF
}

# ---------------------------------------------------------------------
# 1. Achar um Python de verdade. No Windows, "python"/"py" no PATH as
#    vezes e so o atalho da Microsoft Store (nao executa nada de
#    verdade); por isso testamos se o comando realmente roda codigo
#    Python, em vez de so checar se o nome existe no PATH.
# ---------------------------------------------------------------------
encontrar_python() {
  local cmd
  for cmd in python3 python py; do
    if command -v "$cmd" >/dev/null 2>&1 && "$cmd" -c "import sys" >/dev/null 2>&1; then
      echo "$cmd"
      return 0
    fi
  done

  local candidatos=(
    "$HOME/anaconda3/python.exe"
    "$HOME/miniconda3/python.exe"
    "/c/ProgramData/Anaconda3/python.exe"
  )
  local c
  for c in "${candidatos[@]}"; do
    [ -x "$c" ] && { echo "$c"; return 0; }
  done
  for c in "$HOME"/AppData/Local/Programs/Python/Python3*/python.exe; do
    [ -x "$c" ] && { echo "$c"; return 0; }
  done

  return 1
}

# ---------------------------------------------------------------------
# 2/3. Garantir venv criado e dependencias instaladas (idempotente: so
#    reinstala se o venv acabou de ser criado ou se o conteudo combinado
#    dos requirements.txt mudou desde a ultima instalacao).
# ---------------------------------------------------------------------
garantir_venv_e_dependencias() {
  local python_bin
  python_bin="$(encontrar_python || true)"
  if [ -z "$python_bin" ]; then
    echo "" >&2
    echo "Não encontrei um Python instalado de verdade nesta máquina" >&2
    echo "(o 'python'/'py' do Windows aqui costuma ser só o atalho da Microsoft Store)." >&2
    echo "Instale o Python (https://www.python.org/downloads/) ou o Anaconda" >&2
    echo "e rode este script de novo." >&2
    exit 1
  fi
  echo "Usando Python: $python_bin ($("$python_bin" --version 2>&1))"

  if [ ! -d "$VENV_DIR" ]; then
    echo "Criando ambiente virtual em $VENV_DIR ..."
    "$python_bin" -m venv "$VENV_DIR"
  fi

  if [ -x "$VENV_DIR/Scripts/python.exe" ]; then
    VENV_PYTHON="$VENV_DIR/Scripts/python.exe"
  elif [ -x "$VENV_DIR/bin/python" ]; then
    VENV_PYTHON="$VENV_DIR/bin/python"
  else
    echo "Não consegui localizar o python dentro do ambiente virtual criado em $VENV_DIR." >&2
    exit 1
  fi

  local hash_atual hash_salvo
  hash_atual="$(cat "$REQUISITOS_API" "$REQUISITOS_SCRIPTS" 2>/dev/null | sha256sum | cut -d' ' -f1)"
  hash_salvo=""
  [ -f "$MARCADOR_INSTALADO" ] && hash_salvo="$(cat "$MARCADOR_INSTALADO")"

  if [ "$hash_atual" != "$hash_salvo" ]; then
    echo "Instalando dependências (primeira vez, ou requirements.txt mudou)..."
    "$VENV_PYTHON" -m pip install --upgrade pip --quiet
    "$VENV_PYTHON" -m pip install -r "$REQUISITOS_API" -r "$REQUISITOS_SCRIPTS" --quiet
    echo "$hash_atual" > "$MARCADOR_INSTALADO"
    echo "Dependências instaladas."
  else
    echo "Dependências já instaladas — pulando instalação."
  fi
}

# ---------------------------------------------------------------------
# Detecta se ja tem uma instancia do simulador (ou outra coisa) na porta
# configurada. So derruba o processo se o command-line dele bater com
# uvicorn + api.main. Preenche PORTA_STATUS com: "parou" | "nada" |
# "ocupada_por_outro".
#
# Implementacao via arquivo .ps1 temporario, nao via "-Command <string>":
# chamar powershell.exe como subprocesso de dentro do Git Bash com uma
# string complexa (aspas aninhadas) quebra silenciosamente — a conversao
# MSYS de argv pra linha de comando do Windows bagunça o escaping. Um
# arquivo evita isso de vez.
#
# "-State Listen" e importante: sem isso, conexoes antigas em TimeWait
# (processo ja morto, OwningProcess = 0) geram falso positivo de "porta
# ocupada".
# ---------------------------------------------------------------------
verificar_e_parar_simulador_na_porta() {
  local porta="$1"
  PORTA_STATUS="nada"

  if ! command -v powershell.exe >/dev/null 2>&1; then
    return 0
  fi

  local script_ps1 script_ps1_win
  script_ps1="$(mktemp -t liberar_porta.XXXXXX.ps1 2>/dev/null || echo "/tmp/liberar_porta_$$.ps1")"
  cat > "$script_ps1" <<'PS1EOF'
param([int]$Porta)
$pids = Get-NetTCPConnection -LocalPort $Porta -State Listen -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique
foreach ($procId in $pids) {
  $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue
  if ($proc -and $proc.CommandLine -match 'uvicorn' -and $proc.CommandLine -match 'api\.main') {
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    Write-Output "killed:$procId"
  } else {
    Write-Output "skipped:$procId"
  }
}
PS1EOF
  script_ps1_win="$(cygpath -w "$script_ps1" 2>/dev/null || echo "$script_ps1")"

  local saida
  saida=$(powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$script_ps1_win" -Porta "$porta" 2>/dev/null | tr -d '\r')
  rm -f "$script_ps1"

  if [ -z "$saida" ]; then
    PORTA_STATUS="nada"
    return 0
  fi

  if echo "$saida" | grep -q '^killed:'; then
    PORTA_STATUS="parou"
    sleep 1
  fi

  if echo "$saida" | grep -q '^skipped:'; then
    PORTA_STATUS="ocupada_por_outro"
  fi
}

# ---------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------

cmd_start() {
  garantir_venv_e_dependencias

  verificar_e_parar_simulador_na_porta "$PORT"
  case "$PORTA_STATUS" in
    parou)
      echo "Uma instância anterior do simulador ainda estava rodando na porta $PORT — parei ela pra subir já com o banco de questões atualizado."
      ;;
    ocupada_por_outro)
      echo "" >&2
      echo "AVISO: a porta $PORT já está em uso por outro processo, que não parece ser o simulador (não vou derrubar ele)." >&2
      echo "Feche esse processo manualmente ou rode com outra porta, ex.: SIMULADOR_PORT=8080 bash iniciar-simulador.bash --start" >&2
      exit 1
      ;;
  esac

  mkdir -p "$LOG_DIR"
  cd "$PROJETO_DIR"
  nohup "$VENV_PYTHON" -m uvicorn api.main:app --host "$HOST" --port "$PORT" > "$LOG_FILE" 2>&1 &
  local pid=$!
  disown

  echo ""
  echo "Subindo o servidor (PID $pid), log em $LOG_FILE ..."
  local subiu=""
  for _ in $(seq 1 20); do
    if grep -q "Uvicorn running" "$LOG_FILE" 2>/dev/null; then
      subiu="1"
      break
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      break
    fi
    sleep 1
  done

  if [ "$subiu" != "1" ]; then
    echo "" >&2
    echo "O servidor não respondeu a tempo. Veja o log: $LOG_FILE" >&2
    exit 1
  fi

  echo "Servidor no ar: http://localhost:$PORT"
  if [ "$HOST" = "0.0.0.0" ]; then
    echo "Acessível também por outros dispositivos na mesma rede local (ex.: celular), usando o IP deste notebook em vez de 'localhost'."
  fi
  echo "Pra parar: bash iniciar-simulador.bash --stop"
}

cmd_stop() {
  verificar_e_parar_simulador_na_porta "$PORT"
  case "$PORTA_STATUS" in
    parou)
      echo "Servidor parado (porta $PORT liberada)."
      ;;
    nada)
      echo "Nenhuma instância do simulador estava rodando na porta $PORT."
      ;;
    ocupada_por_outro)
      echo "A porta $PORT está em uso, mas o processo não parece ser o simulador — não mexi nele." >&2
      ;;
  esac
}

cmd_reset() {
  local nome="$1"
  garantir_venv_e_dependencias

  local db="$PROJETO_DIR/dados/simulados.db"
  if [ ! -f "$db" ]; then
    echo "Ainda não existe nenhum histórico salvo (o banco $db nem existe)."
    return 0
  fi

  local total
  total="$("$VENV_PYTHON" - "$db" "$nome" <<'PYEOF'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
n = conn.execute("SELECT COUNT(*) FROM tentativas WHERE nome_usuario = ?", (sys.argv[2],)).fetchone()[0]
print(n)
conn.close()
PYEOF
  )"

  if [ "$total" = "0" ]; then
    echo "Nenhum histórico encontrado pro nome '$nome'."
    return 0
  fi

  echo "Isso vai apagar $total tentativa(s) (e todas as respostas associadas) do usuário '$nome'."
  read -r -p "Confirma? [s/N] " confirmacao
  case "$confirmacao" in
    [sS]|[sS][iI][mM]) ;;
    *)
      echo "Cancelado."
      return 0
      ;;
  esac

  "$VENV_PYTHON" - "$db" "$nome" <<'PYEOF'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
nome = sys.argv[2]
ids = [r[0] for r in conn.execute("SELECT id FROM tentativas WHERE nome_usuario = ?", (nome,)).fetchall()]
conn.executemany("DELETE FROM respostas WHERE tentativa_id = ?", [(i,) for i in ids])
conn.execute("DELETE FROM tentativas WHERE nome_usuario = ?", (nome,))
conn.commit()
conn.close()
print(f"Histórico de '{nome}' removido: {len(ids)} tentativa(s).")
PYEOF
}

# ---------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------

COMANDO="${1:-}"

echo "== Simulador ENEM =="
echo "Projeto em: $PROJETO_DIR"

case "$COMANDO" in
  --start)
    cmd_start
    ;;
  --stop)
    cmd_stop
    ;;
  --reset)
    NOME_RESET="${2:-}"
    if [ -z "$NOME_RESET" ]; then
      echo "" >&2
      echo "Uso: bash iniciar-simulador.bash --reset <nome>" >&2
      exit 1
    fi
    cmd_reset "$NOME_RESET"
    ;;
  --help|-h|"")
    mostrar_ajuda
    ;;
  *)
    echo "Parâmetro desconhecido: $COMANDO" >&2
    echo "" >&2
    mostrar_ajuda >&2
    exit 1
    ;;
esac
