"""Atualiza data/lista_jogos.xlsx com os jogos de hoje + 4 dias do SoccerSTATS.

Uso (com o venv ativado, na pasta do projeto):
    python atualizar_jogos.py              # hoje + 4 dias, mantém 2 dias de histórico
    python atualizar_jogos.py --historico 5
    python atualizar_jogos.py --forcar     # baixa tudo, mesmo o que foi buscado há pouco

Também dá para rodar pelo botão "🔄 Atualizar jogos" na aba Jogos do Dia,
ou com duplo clique em atualizar_jogos.bat (útil no Agendador de Tarefas).
"""
import argparse
import sys

from utils.data_loader import LISTA_JOGOS_PATH
from utils.soccerstats import SoccerStatsErro, atualizar_planilha

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--historico", type=int, default=2,
                    help="dias passados que continuam na planilha (padrão: 2)")
    ap.add_argument("--forcar", action="store_true",
                    help="ignora o controle de 6h e baixa todos os dias de novo")
    args = ap.parse_args()
    try:
        atualizar_planilha(LISTA_JOGOS_PATH, dias_historico=args.historico, forcar=args.forcar)
    except SoccerStatsErro as e:
        print(f"ERRO: {e}")
        sys.exit(1)
