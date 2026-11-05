"""Carregamento e gravação de dados do dashboard.

Estratégia de desempenho:
- Excel lido com o motor `calamine` (Rust, ~8x mais rápido que openpyxl) e cache
  atrelado à data de modificação do arquivo: abriu o Excel e salvou -> o app
  recarrega sozinho; não mudou -> leitura instantânea do cache.
- Dados de referência do Google Sheets (paises, depara, campeonatos, métodos
  stats, base extra) baixados EM PARALELO, com cache em memória + disco (6h).
- Dados que você grava (métodos por jogo e config de stakes) ficam num
  "store" em memória: depois de salvar, o store é atualizado localmente em vez
  de baixar tudo de novo — a gravação custa só o POST.
"""
from __future__ import annotations

import io
import os
import pickle
import re
import subprocess
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "utils", ".cache")

METODOS_URL = os.getenv(
    "METODOS_URL",
    "https://script.google.com/macros/s/AKfycbw_ARXW6wdw5ty4owuQWYQrPDh6ZcyH9p6NWBDG67834H474DAeKbkEmt6o_QPV75gg/exec",
)
SHEET_ID = "1WH5N3qLvzbw5Vxkpv7TK5-u6xEpCZrZ0q3HWni9uTSo"
SHEET_GID = 1612712257  # aba "Jogos Futuros do PAINEL"

TTL_REFERENCIA = 6 * 3600   # paises, depara, campeonatos, métodos stats, base extra
TTL_GRAVAVEL = 10 * 60      # métodos por jogo / config (podem mudar em outro dispositivo)
HTTP_TIMEOUT = 30


def caminho(env_var: str, padrao: str) -> str:
    """Resolve caminhos relativos a partir da pasta do projeto (não do cwd)."""
    p = os.getenv(env_var, padrao)
    return p if os.path.isabs(p) else os.path.join(BASE_DIR, p)


DATA_PATH = caminho("DATA_PATH", "data/Trading Esportivo.xlsx")
LISTA_JOGOS_PATH = caminho("LISTA_JOGOS_PATH", "data/lista_jogos.xlsx")
CONFIG_LOCAL = os.path.join(BASE_DIR, "data", "config_stakes.json")


def _read_excel(path, **kw):
    try:
        return pd.read_excel(path, engine="calamine", **kw)
    except ImportError:  # python-calamine não instalado -> mais lento, mas funciona
        return pd.read_excel(path, **kw)


def _mtime(path: str) -> float:
    return os.path.getmtime(path) if os.path.exists(path) else 0.0


# ============================================================
# NORMALIZAÇÃO
# ============================================================
_RE_ESPACOS = re.compile(r"[\s  -​  　]+")
_RE_APOSTROFOS = re.compile(r"['‘’ʼ‛′]")


def _normalizar_nome(nome) -> str:
    """Padroniza nome de time: sem acentos, apóstrofos, espaços extras; minúsculo."""
    if not isinstance(nome, str):
        return ""
    n = _RE_APOSTROFOS.sub("", _RE_ESPACOS.sub(" ", nome))
    n = unicodedata.normalize("NFD", n)
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    return " ".join(n.lower().split())


def norm_data(v) -> str:
    """Qualquer data (ISO, 'AAAA-MM-DD', 'DD/MM/AAAA') -> 'AAAA-MM-DD'."""
    if not v:
        return ""
    s = str(v).split("T")[0].split(" ")[0]
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}" if m else s


def chave_jogo(data, pais, mandante, visitante) -> str:
    """Chave única de um jogo na aba Métodos."""
    return "|".join([norm_data(data), str(pais), str(mandante), str(visitante)]).lower()


# ============================================================
# BASE DE APOSTAS (Trading Esportivo.xlsx)
# ============================================================
def load_data() -> pd.DataFrame:
    return _load_data(DATA_PATH, os.getenv("SHEET_NAME", "Base"), _mtime(DATA_PATH))


@st.cache_data(show_spinner=False, max_entries=2)
def _load_data(path, sheet, mtime):
    df = _read_excel(path, sheet_name=sheet, header=1)
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")].dropna(how="all")

    # Placar SEMPRE texto ("0x0" não pode virar 0)
    if "Placar" in df.columns:
        df["Placar"] = df["Placar"].astype(str).str.strip().replace({"nan": "", "None": ""})
    for col in ("Data", "Data de liquidação"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    if "Horário" in df.columns and "Data" in df.columns:
        h = df["Horário"]
        if pd.api.types.is_datetime64_any_dtype(h):
            hora = h - h.dt.normalize()
        else:  # célula só com hora (datetime.time) ou texto
            hora = pd.to_timedelta(h.astype(str), errors="coerce")
        df["Data"] = df["Data"] + hora.fillna(pd.Timedelta(0))
    for col in ("L/P Líquido", "Comissão%", "L/P Bruto", "Odd", "Stake/Responsabilidade",
                "ComissãoR$", "Stakes", "Resultado_Binario"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "Campeonato" in df.columns:
        df["Campeonato"] = df["Campeonato"].fillna("Não informado")
    return df.reset_index(drop=True)


# ============================================================
# LISTA DE JOGOS (gerada por utils/soccerstats.py)
# ============================================================
def load_lista_jogos() -> pd.DataFrame:
    """Lista de jogos já filtrada pelos países elegíveis (aba Paises)."""
    df = _load_lista_jogos(LISTA_JOGOS_PATH, _mtime(LISTA_JOGOS_PATH))
    paises = load_paises_elegiveis()
    if paises and not df.empty:
        df = df[df["pais"].isin(paises)]
    return df.reset_index(drop=True)


@st.cache_data(show_spinner=False, max_entries=2)
def _load_lista_jogos(path, mtime):
    from utils.soccerstats import ler_planilha
    return ler_planilha(path)


# ============================================================
# GOOGLE SHEETS (Web App do Apps Script)
# ============================================================
def _get_gs(fonte: str | None = None):
    """GET no web app (fonte = metodos_stats | config | depara | paises | campeonatos)."""
    try:
        params = {"fonte": fonte} if fonte else None
        r = requests.get(METODOS_URL, params=params, timeout=HTTP_TIMEOUT)
        return r.json()
    except Exception as e:
        print(f"[aviso] GET {fonte or 'metodos'}: {e}")
        return None


def _post_gs(payload: dict) -> dict:
    """POST no web app.

    O Apps Script responde 302 apontando para a resposta do doPost. Seguir o
    redirect com POST dá 405, então lemos a resposta com GET (não reexecuta
    nada) para confirmar de verdade se gravou.
    """
    try:
        r = requests.post(METODOS_URL, json=payload, allow_redirects=False, timeout=HTTP_TIMEOUT)
    except Exception as e:
        return {"ok": False, "erro": str(e)}
    if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("Location"):
        try:
            r = requests.get(r.headers["Location"], timeout=10)
        except Exception:
            return {"ok": True}       # o doPost já rodou; só não deu para ler a resposta
    elif r.status_code >= 400:
        return {"ok": False, "erro": f"HTTP {r.status_code}"}
    try:
        resp = r.json()
    except Exception:
        return {"ok": True}
    if not isinstance(resp, dict):
        return {"ok": True}
    if resp.get("ok") is False or resp.get("error") or resp.get("erro"):
        resp["ok"] = False
    else:
        resp["ok"] = True
    return resp


def _baixar_base_extra():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={SHEET_GID}"
    r = requests.get(url, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.content.decode("utf-8")))


# ---------- Referências: baixadas em paralelo, cache memória + disco ----------
_FONTES_REF = {
    "metodos_stats": lambda: _get_gs("metodos_stats"),
    "paises": lambda: _get_gs("paises"),
    "depara": lambda: _get_gs("depara"),
    "campeonatos": lambda: _get_gs("campeonatos"),
    "base_extra": lambda: _baixar_base_extra(),
}


def _baixar_em_paralelo(tarefas: dict) -> dict:
    def seguro(f):
        try:
            return f()
        except Exception as e:
            print(f"[aviso] download: {e}")
            return None
    with ThreadPoolExecutor(max_workers=len(tarefas) or 1) as ex:
        futuros = {k: ex.submit(seguro, f) for k, f in tarefas.items()}
        return {k: f.result() for k, f in futuros.items()}


@st.cache_data(ttl=TTL_REFERENCIA, show_spinner=False)
def _referencias() -> dict:
    path = os.path.join(CACHE_DIR, "referencias.pkl")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < TTL_REFERENCIA:
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    tarefas = dict(_FONTES_REF)
    # Aproveita a mesma rodada paralela para aquecer os dados graváveis
    for nome, store in (("metodos_jogos", _store_metodos()), ("config", _store_config())):
        if store["dados"] is None:
            tarefas[nome] = (lambda n=nome: _get_gs(None if n == "metodos_jogos" else n))
    dados = _baixar_em_paralelo(tarefas)
    if "metodos_jogos" in dados:
        _store_metodos().update(dados=_parse_metodos_jogos(dados.pop("metodos_jogos")), ts=time.time())
    if "config" in dados:
        _store_config().update(dados=_parse_config(dados.pop("config")), ts=time.time())
    ref = {
        "metodos_stats": _parse_metodos_stats(dados["metodos_stats"]),
        "paises": _parse_paises(dados["paises"]),
        "depara": _parse_depara(dados["depara"]),
        "campeonatos": _parse_campeonatos(dados["campeonatos"]),
        "base_extra": _parse_base_extra(dados["base_extra"]),
    }
    # Só grava em disco se tudo veio (não persiste falha de rede por 6h)
    if all(v is not None and len(v) for v in ref.values()):
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(path, "wb") as f:
                pickle.dump(ref, f)
        except Exception as e:
            print(f"[aviso] cache em disco: {e}")
    return ref


def _parse_metodos_stats(d):
    if d and d.get("ok") and d.get("rows"):
        df = pd.DataFrame(d["rows"])
        df.columns = [str(c).strip() for c in df.columns]
        return df
    for p in (caminho("METODOS_STATS_PATH", "data/metodos.xlsx"),):
        if os.path.exists(p):
            df = _read_excel(p)
            df.columns = [str(c).strip() for c in df.columns]
            return df
    return pd.DataFrame()


def _parse_paises(d):
    if d and d.get("ok"):
        return {str(p).strip().lower() for p in d.get("paises", []) if str(p).strip()}
    p = caminho("PAISES_PATH", "data/paises.csv")
    if os.path.exists(p):
        s = pd.read_csv(p, header=None).iloc[:, 0]
        return set(s.dropna().astype(str).str.strip().str.lower())
    return set()


def _parse_depara(d):
    depara = {}
    if d and d.get("ok"):
        for item in d.get("depara", []):
            de, para = _normalizar_nome(str(item.get("de", ""))), _normalizar_nome(str(item.get("para", "")))
            if de and para:
                depara[de] = para
        return depara
    p = caminho("DEPARA_PATH", "data/depara.csv")
    if os.path.exists(p):
        try:
            df = pd.read_csv(p, dtype=str, sep=None, engine="python", encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(p, dtype=str, sep=None, engine="python", encoding="latin-1")
        for de, para in zip(df.iloc[:, 0], df.iloc[:, min(1, df.shape[1] - 1)]):
            de, para = _normalizar_nome(de), _normalizar_nome(para)
            if de and para:
                depara[de] = para
    return depara


def _parse_campeonatos(d):
    if d and d.get("ok"):
        c = {str(x).strip() for x in d.get("campeonatos", []) if str(x).strip()}
        if c:
            return sorted(c)
    p = caminho("CAMPEONATOS_PATH", "data/campeonatos.csv")
    if os.path.exists(p):
        s = pd.read_csv(p, header=None).iloc[:, 0]
        return sorted(set(s.dropna().astype(str).str.strip()))
    return []


def _parse_base_extra(df):
    """Classificação e odds de abertura (aba 'Jogos Futuros do PAINEL')."""
    if df is None or df.empty:
        return pd.DataFrame()

    def num(col):
        return pd.to_numeric(df[col].astype(str).str.replace(",", ".").str.strip(), errors="coerce")

    base = pd.DataFrame({
        "Casa_N": df["Nome Casa"].map(_normalizar_nome),
        "Fora_N": df["Nome Fora"].map(_normalizar_nome),
        "Classif Casa": num("Classif Geral Casa").fillna(0).astype(int),
        "Classif Fora": num("Classif Geral Fora").fillna(0).astype(int),
        "Odd Casa": num("Odd Abertura Casa").fillna(0.0),
        "Odd Fora": num("Odd Abertura Visitante").fillna(0.0),
        "Data_N": pd.to_datetime(df["Date"], errors="coerce", dayfirst=True).dt.strftime("%Y-%m-%d")
        if "Date" in df.columns else None,
    })
    return base.drop_duplicates(subset=["Casa_N", "Fora_N", "Data_N"], keep="first").reset_index(drop=True)


def load_metodos() -> pd.DataFrame:
    return _referencias()["metodos_stats"]


def load_paises_elegiveis() -> set:
    return _referencias()["paises"]


def load_depara() -> dict:
    return _referencias()["depara"]


def load_campeonatos() -> list:
    return _referencias()["campeonatos"]


def load_base_extra() -> pd.DataFrame:
    return _referencias()["base_extra"]


# ---------- Dados graváveis: store em memória atualizado localmente ----------
@st.cache_resource
def _store_metodos() -> dict:
    return {"dados": None, "ts": 0.0}


@st.cache_resource
def _store_config() -> dict:
    return {"dados": None, "ts": 0.0}


def _parse_metodos_jogos(d) -> list[dict]:
    rows = (d or {}).get("rows", []) if isinstance(d, dict) else []
    return [dict(r) for r in rows if isinstance(r, dict)]


def load_metodos_jogos() -> list[dict]:
    """Métodos marcados por jogo (aba Métodos). Lista de dicts."""
    s = _store_metodos()
    if s["dados"] is None or time.time() - s["ts"] > TTL_GRAVAVEL:
        s.update(dados=_parse_metodos_jogos(_get_gs()), ts=time.time())
    return [dict(r) for r in s["dados"]]


def _aplicar_local(linhas: list[dict], remover: bool):
    s = _store_metodos()
    if s["dados"] is None:
        return
    chaves = {chave_jogo(l.get("data"), l.get("pais"), l.get("mandante"), l.get("visitante")): l
              for l in linhas}
    atual = [r for r in s["dados"]
             if chave_jogo(r.get("data"), r.get("pais"), r.get("mandante"), r.get("visitante")) not in chaves]
    if not remover:
        atual += [{**l, "data": norm_data(l.get("data"))} for l in chaves.values()]
    s["dados"] = atual


def salvar_metodos(linhas: list[dict]) -> dict:
    resp = _post_gs({"rows": linhas})
    if resp.get("ok"):
        resp.setdefault("saved", len(linhas))
        _aplicar_local(linhas, remover=False)
    return resp


def deletar_metodos(linhas: list[dict]) -> dict:
    resp = _post_gs({"destino": "limpar", "linhas": linhas})
    if resp.get("ok"):
        resp.setdefault("saved", len(linhas))
        _aplicar_local(linhas, remover=True)
    return resp


def _parse_config(d) -> dict:
    cfg = {"stakes_manuais": {}}
    if d and d.get("ok"):
        for k, v in (d.get("config") or {}).items():
            if k.startswith("stake_manual|"):
                try:
                    cfg["stakes_manuais"][k.split("|", 1)[1]] = float(v)
                except (TypeError, ValueError):
                    pass
            else:
                cfg[k] = v
    elif os.path.exists(CONFIG_LOCAL):
        import json
        try:
            with open(CONFIG_LOCAL, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    for k, padrao in (("banca", 1000.0), ("dd", 10.0)):
        try:
            cfg[k] = float(cfg.get(k, padrao))
        except (TypeError, ValueError):
            cfg[k] = padrao
    cfg.setdefault("tipo_red", "Red Médio")
    return cfg


def load_config() -> dict:
    s = _store_config()
    if s["dados"] is None or time.time() - s["ts"] > TTL_GRAVAVEL:
        s.update(dados=_parse_config(_get_gs("config")), ts=time.time())
    return {**s["dados"], "stakes_manuais": dict(s["dados"].get("stakes_manuais", {}))}


def salvar_config(cfg: dict) -> bool:
    """Grava banca/dd/tipo_red/stakes manuais na aba Config. Fallback: json local."""
    payload = {"banca": cfg.get("banca", 1000.0), "dd": cfg.get("dd", 10.0),
               "tipo_red": cfg.get("tipo_red", "Red Médio")}
    for nome, valor in (cfg.get("stakes_manuais") or {}).items():
        payload[f"stake_manual|{nome}"] = valor
    ok = _post_gs({"destino": "config", "config": payload}).get("ok")
    if not ok:
        import json
        try:
            os.makedirs(os.path.dirname(CONFIG_LOCAL), exist_ok=True)
            with open(CONFIG_LOCAL, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            ok = True
        except Exception:
            return False
    _store_config().update(dados=dict(cfg), ts=time.time())
    return True


# ============================================================
# MANUTENÇÃO
# ============================================================
def limpar_caches():
    """Zera cache em memória, stores e cache em disco (botão 'Limpar Cache')."""
    import shutil
    st.cache_data.clear()
    st.cache_resource.clear()
    shutil.rmtree(CACHE_DIR, ignore_errors=True)


def push_github() -> tuple[bool, str]:
    """Commit + push das duas bases (Trading Esportivo + lista de jogos), se mudaram."""
    try:
        arquivos = [os.path.relpath(p, BASE_DIR) for p in (DATA_PATH, LISTA_JOGOS_PATH) if os.path.exists(p)]
        subprocess.run(["git", "add", "--", *arquivos], cwd=BASE_DIR,
                       capture_output=True, text=True, check=True)
        r = subprocess.run(["git", "commit", "-m", "Atualiza bases do dashboard (Trading Esportivo + lista de jogos)"],
                           cwd=BASE_DIR, capture_output=True, text=True)
        if r.returncode != 0:
            return True, "Nada novo para enviar."
        subprocess.run(["git", "push"], cwd=BASE_DIR, capture_output=True, text=True, check=True)
        return True, "Excel e lista de jogos enviados para o GitHub!"
    except subprocess.CalledProcessError as e:
        return False, (e.stderr or str(e)).strip()
    except Exception as e:
        return False, str(e)
