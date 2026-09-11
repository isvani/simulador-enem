# Simulador ENEM

Simulador de provas do ENEM (e, no futuro, FUVEST/ITA/UNICAMP): banco de
questões classificado por área/subtópico/dificuldade, motor de simulados
com amostragem ponderada e dashboard de desempenho/tempo de resposta.

Planejamento completo, decisões de arquitetura e progresso das fases:
[planejamento-simulados-enem-fuvest.md](planejamento-simulados-enem-fuvest.md).

## Uso rápido

```bash
bash iniciar-simulador.bash --start              # instala (1ª vez) e sobe o servidor
bash iniciar-simulador.bash --stop               # para o servidor
bash iniciar-simulador.bash --update-questions   # re-extrai ENEM 2024/2025 dos PDFs
bash iniciar-simulador.bash --reset <nome>        # apaga o histórico de um usuário
```

Depois de `--start`, acesse `http://localhost:8000` (ou o IP do notebook
na rede local, ex.: pelo celular).

## Estrutura

```
dados/    banco_questoes.json (banco de questões) e simulados.db (SQLite, não versionado)
api/      backend FastAPI
web/      frontend estático (HTML/CSS/JS puro)
scripts/  extração dos PDFs oficiais do INEP e patches manuais
```
