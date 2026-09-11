# Simulador ENEM

Simulador de provas do ENEM (e, no futuro, FUVEST/ITA/UNICAMP): banco de
questões classificado por área/subtópico/dificuldade, motor de simulados
com amostragem ponderada e dashboard de desempenho/tempo de resposta.

Planejamento completo, decisões de arquitetura e progresso das fases:
[planejamento-simulados-enem-fuvest.md](planejamento-simulados-enem-fuvest.md).

## Uso rápido

```bash
bash iniciar-simulador.bash --start        # instala (1ª vez) e sobe o servidor
bash iniciar-simulador.bash --stop         # para o servidor
bash iniciar-simulador.bash --reset <nome> # apaga o histórico de um usuário
```

Depois de `--start`, acesse `http://localhost:8000` (ou o IP do notebook
na rede local, ex.: pelo celular). Se `dados/banco_questoes.json` for
editado/substituído por fora enquanto o servidor está de pé, rodar
`--start` de novo reinicia o servidor e recarrega o arquivo atualizado.

Pra re-extrair as questões de 2024/2025 dos PDFs oficiais (raro — só
quando o parser muda ou aparece um PDF novo), rode direto:

```bash
.venv/Scripts/python.exe scripts/extract_enem_2024_2025.py
.venv/Scripts/python.exe scripts/patch_enem_2024_2025_manual.py
bash iniciar-simulador.bash --start
```

As imagens das questões ficam salvas localmente em `dados/imagens/`
(baixadas do enem.dev uma vez, via `scripts/baixar_imagens.py`) — o
simulado não depende do servidor do enem.dev pra funcionar.

## Estrutura

```
dados/    banco_questoes.json (banco de questões), imagens/ (imagens das
          questões, baixadas do enem.dev) e simulados.db (SQLite, não versionado)
api/      backend FastAPI
web/      frontend estático (HTML/CSS/JS puro)
scripts/  extração dos PDFs oficiais do INEP, patches manuais e download de imagens
```
