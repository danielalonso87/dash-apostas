"""Coleta dos jogos dos próximos dias no SoccerSTATS e gravação da lista_jogos.xlsx.

Substitui o processo manual (copiar/colar da página Matches + digitar a data).
Fonte: página "Daily Matches" em modo tabela, escopo Home vs Away:
    https://www.soccerstats.com/nodeweb/en-gb/dailymatches/<dia>/homevsaway/table

Cada linha da tabela traz:
    - data-matchid  -> ID único do jogo (usado para não duplicar)
    - data-utc      -> horário de início em UTC (convertido para Brasília)
    - link da competição -> código da liga (ex.: "italy", "england2"), o mesmo
      código usado na aba "Paises" do Google Sheets.

O site fica atrás do Cloudflare, que bloqueia o `requests` comum (HTTP 403);
por isso o download usa `curl_cffi`, que se apresenta como o Chrome. O HTML é
lido com o html.parser da própria linguagem.
"""
from __future__ import annotations

import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

import pandas as pd

try:
    from zoneinfo import ZoneInfo
    TZ_BR = ZoneInfo("America/Sao_Paulo")
except Exception:  # Windows sem tzdata: Brasília não tem horário de verão
    TZ_BR = timezone(timedelta(hours=-3))

BASE_URL = "https://www.soccerstats.com/nodeweb/en-gb/dailymatches/{dia}/homevsaway/table"
# Só as colunas usadas (GP e PPG o site sempre envia) -> página menor e mais rápida
COLS = "gf_ga_o35,gf_ga_o25,gf_ga_o15,ga,gf,gf_ga"
DIAS_SITE = ["today", "tomorrow", "day2", "day3", "day4"]
SHEET = "jogos"
SHEET_CONTROLE = "controle"   # quando cada data foi buscada no site

# Cabeçalho do site -> sufixo da coluna na planilha
_MAPA_STATS = {
    "GP": "gp", "PPG": "ppg", "GF": "gf", "GA": "ga", "TG": "tg",
    "TG_1.5+": "over15", "TG_2.5+": "over25", "TG_3.5+": "over35",
}
_STATS = ["gp", "ppg", "gf", "ga", "tg", "over15", "over25", "over35"]
COLUNAS = (
    ["id_jogo", "data", "hora", "pais", "competicao", "mandante", "visitante"]
    + [f"casa_{s}" for s in _STATS]
    + [f"fora_{s}" for s in _STATS]
    + ["inicio_utc", "atualizado_em"]
)


class SoccerStatsErro(RuntimeError):
    pass


# ============================================================
# 1) DOWNLOAD
# ============================================================
_SESSAO = None


def _sessao():
    """Sessão que se apresenta como o Chrome (TLS + cabeçalhos).

    O site fica atrás do Cloudflare, que devolve 403 para o `requests` comum.
    A sessão é reaproveitada entre as páginas (mantém os cookies do Cloudflare).
    """
    global _SESSAO
    if _SESSAO is None:
        try:
            from curl_cffi import requests as creq
        except ImportError:
            raise SoccerStatsErro(
                "Falta a biblioteca curl_cffi. No terminal, com o venv ativado, rode: "
                "pip install -r requirements.txt  (o atualizar_jogos.bat faz isso sozinho)."
            )
        _SESSAO = creq.Session(impersonate="chrome")
        _SESSAO.headers.update({"Accept-Language": "en-GB,en;q=0.9,pt-BR;q=0.8"})
        try:  # passa pela home primeiro, como um navegador faria
            _SESSAO.get("https://www.soccerstats.com/en-gb/", timeout=40)
        except Exception:
            pass
    return _SESSAO


def _baixar(url: str, tentativas: int = 3) -> str:
    ultimo_erro = None
    for i in range(tentativas):
        try:
            r = _sessao().get(url, timeout=60,
                              headers={"Referer": "https://www.soccerstats.com/en-gb/dailymatches"})
            if r.status_code == 200 and "symmetricMatchTable" in r.text:
                return r.text
            ultimo_erro = f"HTTP {r.status_code}"
        except SoccerStatsErro:
            raise
        except Exception as e:  # rede instável -> tenta de novo
            ultimo_erro = str(e)
        time.sleep(3 * (i + 1))
    raise SoccerStatsErro(f"O SoccerSTATS recusou o download ({ultimo_erro}) em {url}")


# ============================================================
# 2) PARSER (html.parser da biblioteca padrão)
# ============================================================
class _TabelaJogos(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.headers: list[str] = []
        self.rows: list[dict] = []
        self._na_tabela = False
        self._depth = 0          # profundidade de <table> dentro da tabela alvo
        self._em_thead = False
        self._em_th = False
        self._linha = None
        self._celula = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            if self._na_tabela:
                self._depth += 1
            elif a.get("id") == "symmetricMatchTable":
                self._na_tabela, self._depth = True, 1
            return
        if not self._na_tabela:
            return
        if tag == "thead":
            self._em_thead = True
        elif tag == "th" and self._em_thead:
            self._em_th = True
            self.headers.append("")
        elif tag == "tr" and not self._em_thead and "data-matchid" in a:
            self._linha = {"id": a.get("data-matchid"), "utc": a.get("data-utc"),
                           "cells": [], "liga_href": None, "bandeira": None}
        elif tag == "td" and self._linha is not None:
            self._celula = []
        elif self._linha is not None and self._celula is not None and len(self._linha["cells"]) == 0:
            # 1ª célula = competição (bandeira + link da liga)
            if tag == "a" and a.get("href"):
                self._linha["liga_href"] = a["href"]
            elif tag == "img" and a.get("alt"):
                self._linha["bandeira"] = a["alt"]

    def handle_endtag(self, tag):
        if not self._na_tabela:
            return
        if tag == "table":
            self._depth -= 1
            if self._depth == 0:
                self._na_tabela = False
        elif tag == "thead":
            self._em_thead = False
        elif tag == "th":
            self._em_th = False
        elif tag == "td" and self._linha is not None and self._celula is not None:
            self._linha["cells"].append(" ".join("".join(self._celula).split()))
            self._celula = None
        elif tag == "tr" and self._linha is not None:
            self.rows.append(self._linha)
            self._linha = None

    def handle_data(self, data):
        if self._em_th:
            self.headers[-1] += data.strip()
        elif self._celula is not None:
            self._celula.append(data)


def _num(txt):
    """'25%' -> 0.25 | '1.75' -> 1.75 | '-' / '' -> None"""
    t = (txt or "").strip()
    if t in ("", "-"):
        return None
    try:
        if t.endswith("%"):
            return round(float(t[:-1]) / 100.0, 4)
        return float(t)
    except ValueError:
        return None


def parse_jogos(html: str) -> list[dict]:
    """Extrai os jogos da tabela 'symmetricMatchTable' (lida pelo nome dos cabeçalhos)."""
    p = _TabelaJogos()
    p.feed(html)
    h = p.headers
    if not h or "Home" not in h or "Away" not in h:
        raise SoccerStatsErro("Layout do site mudou: cabeçalhos Home/Away não encontrados.")
    i_home, i_away = h.index("Home"), h.index("Away")
    lado_casa = {h[i]: i for i in range(1, i_home) if h[i] in _MAPA_STATS}
    lado_fora = {h[i]: i for i in range(i_away + 1, len(h)) if h[i] in _MAPA_STATS}

    jogos = []
    for r in p.rows:
        c = r["cells"]
        if len(c) < len(h) - 1:      # linha incompleta / bloqueada
            continue
        try:
            utc = datetime.strptime(r["utc"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        local = utc.astimezone(TZ_BR)
        href = (r["liga_href"] or "").rstrip("/")
        jogo = {
            "id_jogo": int(r["id"]),
            "data": local.date(),
            "hora": local.strftime("%H:%M"),
            "pais": href.rsplit("/", 1)[-1].lower() if href else "",
            "competicao": c[0],
            "mandante": c[i_home],
            "visitante": c[i_away],
            "inicio_utc": utc.strftime("%Y-%m-%d %H:%M"),
        }
        for nome, idx in lado_casa.items():
            jogo[f"casa_{_MAPA_STATS[nome]}"] = _num(c[idx])
        for nome, idx in lado_fora.items():
            jogo[f"fora_{_MAPA_STATS[nome]}"] = _num(c[idx])
        jogos.append(jogo)
    return jogos


# ============================================================
# 3) ATUALIZAÇÃO DA PLANILHA
# ============================================================
def buscar_jogos(dias=DIAS_SITE, pausa: float = 1.0, log=print) -> pd.DataFrame:
    """Baixa e consolida os jogos das páginas pedidas (sem duplicar)."""
    todos = []
    for i, dia in enumerate(dias):
        url = f"{BASE_URL.format(dia=dia)}?cols={COLS}"
        jogos = parse_jogos(_baixar(url))
        log(f"  {dia:>8}: {len(jogos)} jogos")
        todos.extend(jogos)
        if i < len(dias) - 1:
            time.sleep(pausa)   # educação com o site
    df = pd.DataFrame(todos)
    if df.empty:
        return pd.DataFrame(columns=COLUNAS)
    df["atualizado_em"] = datetime.now(TZ_BR).strftime("%Y-%m-%d %H:%M")
    return df.drop_duplicates("id_jogo", keep="last").reindex(columns=COLUNAS)


def ler_planilha(path: str) -> pd.DataFrame:
    """Lê a lista no formato novo. Formato antigo (copiar/colar) -> DataFrame vazio."""
    if not os.path.exists(path):
        return pd.DataFrame(columns=COLUNAS)
    df = pd.read_excel(path, sheet_name=SHEET, engine="calamine")
    if "id_jogo" not in df.columns:
        return pd.DataFrame(columns=COLUNAS)
    df["data"] = pd.to_datetime(df["data"], errors="coerce").dt.date
    df["hora"] = df["hora"].astype(str).str.slice(0, 5)
    return df.reindex(columns=COLUNAS)


def ler_controle(path: str) -> dict:
    """{data: datetime da última busca} — usado para não baixar de novo o que é recente."""
    try:
        c = pd.read_excel(path, sheet_name=SHEET_CONTROLE, engine="calamine")
        return {pd.Timestamp(d).date(): pd.Timestamp(t).to_pydatetime()
                for d, t in zip(c["data"], c["buscado_em"]) if pd.notna(d) and pd.notna(t)}
    except Exception:
        return {}


def _gravar_xlsx(df: pd.DataFrame, path: str, controle: dict) -> None:
    """Grava formatada (tabela do Excel, filtros, % e larguras) de forma atômica."""
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.table import Table, TableStyleInfo

    pasta = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(suffix=".xlsx", dir=pasta)
    os.close(fd)
    try:
        with pd.ExcelWriter(tmp, engine="openpyxl") as w:
            df.to_excel(w, sheet_name=SHEET, index=False)
            ws = w.sheets[SHEET]
            ws.freeze_panes = "H2"
            larguras = {"data": 11, "hora": 6, "pais": 14, "competicao": 22,
                        "mandante": 22, "visitante": 22, "inicio_utc": 16, "atualizado_em": 16}
            for j, col in enumerate(df.columns, start=1):
                letra = get_column_letter(j)
                ws.column_dimensions[letra].width = larguras.get(col, 9)
                if col.endswith(("over15", "over25", "over35")):
                    fmt = "0%"
                elif col.endswith(("ppg", "gf", "ga", "tg")):
                    fmt = "0.00"
                elif col == "data":
                    fmt = "DD/MM/YYYY"
                else:
                    continue
                for cell in ws[letra][1:]:
                    cell.number_format = fmt
            if len(df):
                ref = f"A1:{get_column_letter(df.shape[1])}{len(df) + 1}"
                tab = Table(displayName="Jogos", ref=ref)
                tab.tableStyleInfo = TableStyleInfo(name="TableStyleLight9", showRowStripes=True)
                ws.add_table(tab)
            ctl = pd.DataFrame(sorted(controle.items()), columns=["data", "buscado_em"])
            ctl.to_excel(w, sheet_name=SHEET_CONTROLE, index=False)
            wc = w.sheets[SHEET_CONTROLE]
            wc.column_dimensions["A"].width, wc.column_dimensions["B"].width = 12, 18
            for cell in wc["A"][1:]:
                cell.number_format = "DD/MM/YYYY"
            for cell in wc["B"][1:]:
                cell.number_format = "DD/MM/YYYY HH:MM"
        os.replace(tmp, path)   # troca de uma vez: o app nunca lê arquivo pela metade
    except PermissionError:
        raise SoccerStatsErro(f"Feche o arquivo {os.path.basename(path)} no Excel e tente de novo.")
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def atualizar_planilha(path: str, dias=DIAS_SITE, dias_historico: int = 2,
                       horas_validade: float = 6, forcar: bool = False, log=print) -> dict:
    """Busca os jogos de hoje até D+4 e mescla na planilha pelo id_jogo.

    Uma data já buscada há menos de `horas_validade` horas é pulada (rodar de
    novo no mesmo dia é instantâneo). Depois disso ela é baixada de novo, de
    propósito: os jogos futuros mudam de estatística a cada rodada disputada,
    e o site inclui jogos e altera horários ao longo dos dias.
    Jogos com mais de `dias_historico` dias saem da planilha.

    Retorna: {"novos", "atualizados", "removidos", "total", "pulados"}.
    """
    hoje = datetime.now(TZ_BR).date()
    agora = datetime.now(TZ_BR).replace(tzinfo=None)
    controle = {} if forcar else ler_controle(path)
    paginas, pulados = [], []
    for i, dia in enumerate(dias):
        data = hoje + timedelta(days=DIAS_SITE.index(dia) if dia in DIAS_SITE else i)
        ultima = controle.get(data)
        if ultima and (agora - ultima).total_seconds() < horas_validade * 3600:
            pulados.append(data)
        else:
            paginas.append((dia, data))
    for d in pulados:
        log(f"  {d:%d/%m}: já buscado às {controle[d]:%H:%M}, pulando")

    atual = ler_planilha(path)
    if not paginas:
        log("Tudo atualizado, nada a baixar.")
        return {"novos": 0, "atualizados": 0, "removidos": 0, "total": len(atual), "pulados": len(pulados)}

    log("Buscando jogos no SoccerSTATS...")
    novos = buscar_jogos([p for p, _ in paginas], log=log)

    # Formato antigo (copiar/colar): guarda uma cópia antes de substituir
    if os.path.exists(path) and "id_jogo" not in pd.read_excel(path, nrows=0, engine="calamine").columns:
        backup = path.replace(".xlsx", "_formato_antigo.xlsx")
        try:
            if not os.path.exists(backup):
                import shutil
                shutil.copy2(path, backup)
                log(f"Formato antigo salvo como {os.path.basename(backup)}")
        except OSError:
            pass

    ids_antes = set(atual["id_jogo"].dropna().astype(int))
    ids_novos = set(novos["id_jogo"].astype(int))

    base = pd.concat([atual, novos], ignore_index=True) if len(atual) else novos.copy()
    base = base.drop_duplicates("id_jogo", keep="last")   # site = dado mais recente
    corte = hoje - timedelta(days=dias_historico)
    n_antes = len(base)
    base = base[pd.to_datetime(base["data"]).dt.date >= corte]
    removidos = n_antes - len(base)

    base["id_jogo"] = base["id_jogo"].astype(int)
    for c in ("casa_gp", "fora_gp"):
        base[c] = pd.to_numeric(base[c], errors="coerce").astype("Int64")
    base = base.sort_values(["data", "hora", "pais", "mandante"]).reset_index(drop=True)

    if forcar:
        controle = ler_controle(path)
    controle.update({data: agora for _, data in paginas})
    controle = {d: t for d, t in controle.items() if d >= corte}
    _gravar_xlsx(base, path, controle)

    resumo = {
        "novos": len(ids_novos - ids_antes),
        "atualizados": len(ids_novos & ids_antes),
        "removidos": removidos,
        "total": len(base),
        "pulados": len(pulados),
    }
    log(f"OK: {resumo['novos']} novos, {resumo['atualizados']} atualizados, "
        f"{resumo['removidos']} antigos removidos, {resumo['total']} na planilha.")
    return resumo
