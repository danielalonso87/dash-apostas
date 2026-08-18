import pandas as pd
import os, time, json
from dotenv import load_dotenv
import streamlit as st
import subprocess
import unicodedata
import re
import requests
import pickle

load_dotenv()

@st.cache_data(ttl=86400, show_spinner=False)   # 5 min
def load_data():
    path = os.getenv("DATA_PATH", "data/Trading Esportivo.xlsx")
    sheet = os.getenv("SHEET_NAME", "Base")
    df = pd.read_excel(path, sheet_name=sheet, header=1)
    df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]
    df = df.dropna(how='all')
    for col in ['Data', 'Data de liquidação']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    if 'Horário' in df.columns and 'Data' in df.columns:
        hora_td = pd.to_timedelta(df['Horário'].dt.time.astype(str), errors='coerce')
        df['Data'] = df['Data'] + hora_td.fillna(pd.Timedelta(0))
    num_cols = ['L/P Líquido', 'Comissão%', 'L/P Bruto', 'Odd',
                'Stake/Responsabilidade', 'ComissãoR$', 'Stakes', 'Resultado_Binario']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    if 'Campeonato' in df.columns:
        df['Campeonato'] = df['Campeonato'].fillna('Não informado')
    return df

# ============================================================
# GOOGLE SHEETS — LEITURA E GRAVAÇÃO via Web App Apps Script
# ============================================================
METODOS_URL = os.getenv("METODOS_URL", "https://script.google.com/macros/s/AKfycbw_ARXW6wdw5ty4owuQWYQrPDh6ZcyH9p6NWBDG67834H474DAeKbkEmt6o_QPV75gg/exec")

@st.cache_data(ttl=86400, show_spinner=False)
def _get_gs(fonte):
    """GET no web app com parâmetro fonte (metodos|config|depara|paises|metodos_stats)."""
    try:
        url = METODOS_URL + "?fonte=" + str(fonte)
        r = requests.get(url, timeout=30)   # SEM allow_redirects=False — segue o 302
        return r.json()
    except Exception as e:
        print(f"[aviso] _get_gs({fonte}): {e}")
        return None

def _post_gs(payload):
    """POST no web app (campo 'destino' controla a aba)."""
    try:
        r = requests.post(METODOS_URL, json=payload, allow_redirects=False, timeout=30)
        # 302/301 = doPost executou e gravou; não seguimos o redirect (evita o 405)
        if r.status_code in (301, 302, 303, 307, 308):
            return {"ok": True}
        try:
            return r.json()
        except Exception:
            return {"ok": True}
    except Exception as e:
        print(f"[aviso] _post_gs: {e}")
        return None

def load_metodos():
    """Estatísticas por MÉTODO — aba MetodosStats (Sheets). Fallback: metodos.xlsx local."""
    d = _get_gs("metodos_stats")
    if d and d.get("ok") and d.get("rows"):
        df = pd.DataFrame(d["rows"])
        df.columns = [str(c).strip() for c in df.columns]
        return df
    for path in [os.getenv("METODOS_STATS_PATH", "Data/metodos.xlsx"),
                 os.getenv("METODOS_STATS_PATH", "data/metodos.xlsx")]:
        if os.path.exists(path):
            df = pd.read_excel(path)
            df.columns = [str(c).strip() for c in df.columns]
            return df
    return pd.DataFrame()

@st.cache_data(ttl=86400, show_spinner=False)
def load_paises_elegiveis():
    """Aba Paises (Sheets). Fallback: paises.csv local. Cache em disco."""
    return _cache_local("paises", _fetch_paises, ttl=21600)

def _fetch_paises():
    d = _get_gs("paises")
    if d and d.get("ok"):
        return set(str(p).strip().lower() for p in d.get("paises", []) if str(p).strip())
    for path in [os.getenv("PAISES_PATH", "Data/paises.csv"),
                 os.getenv("PAISES_PATH", "data/paises.csv")]:
        if os.path.exists(path):
            df = pd.read_csv(path, header=None)
            col = df.columns[0]
            return set(df[col].dropna().astype(str).str.strip().str.lower().tolist())
    return set()

@st.cache_data(ttl=86400, show_spinner=False)
def load_depara():
    """Aba Depara (Sheets). Fallback: depara.csv local. Cache em disco."""
    return _cache_local("depara", _fetch_depara, ttl=21600)

def _fetch_depara():
    d = _get_gs("depara")
    if d and d.get("ok"):
        depara = {}
        for item in d.get("depara", []):
            de = _normalizar_nome(str(item.get("de", "")))
            para = _normalizar_nome(str(item.get("para", "")))
            if de and para:
                depara[de] = para
        return depara
    path = os.getenv("DEPARA_PATH", "Data/depara.csv")
    if not os.path.exists(path):
        path = os.getenv("DEPARA_PATH", "data/depara.csv")
    depara = {}
    if os.path.exists(path):
        try:
            df = pd.read_csv(path, dtype=str, sep=None, engine="python", encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(path, dtype=str, sep=None, engine="python", encoding="latin-1")
        col_de = next((c for c in df.columns if c.strip().lower() in ("de", "origem")), df.columns[0])
        col_para = next((c for c in df.columns if c.strip().lower() in ("para", "destino")),
                        df.columns[1] if len(df.columns) > 1 else df.columns[0])
        for _, row in df.iterrows():
            de = _normalizar_nome(row[col_de]) if pd.notna(row[col_de]) else ""
            para = _normalizar_nome(row[col_para]) if pd.notna(row[col_para]) else ""
            if de and para:
                depara[de] = para
    return depara

def salvar_depara(de, para):
    """Grava (ou atualiza) mapeamento na aba Depara (Sheets). Fallback: csv local."""
    resp = _post_gs({"destino": "depara", "linhas": [{"de": de, "para": para}]})
    if resp and resp.get("ok"):
        return True
    path = os.getenv("DEPARA_PATH", "Data/depara.csv")
    if not os.path.exists(path):
        path = os.getenv("DEPARA_PATH", "data/depara.csv")
    de_n = _normalizar_nome(de)
    registros = []
    if os.path.exists(path):
        registros = pd.read_csv(path, dtype=str).values.tolist()
    registros = [r for r in registros if _normalizar_nome(str(r[0])) != de_n]
    registros.append([de, para])
    pd.DataFrame(registros, columns=["De", "Para"]).to_csv(path, index=False)
    return False

def _push_excel_para_github():
    """Envia o Trading Esportivo.xlsx e a lista de jogos para o GitHub se houver mudança."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))

        # MESMA resolução do código original (que funcionava)
        rel_excel = os.path.relpath(
            os.getenv("DATA_PATH", "data/Trading Esportivo.xlsx"), base_dir
        ).replace(os.sep, '/')

        # Pasta real onde o Excel está, derivada do próprio caminho resolvido
        pasta = os.path.dirname(os.path.normpath(os.path.join(base_dir, rel_excel)))

        # Adiciona os .xlsx da pasta (só os 2: Trading Esportivo + lista de jogos)
        for nome in os.listdir(pasta):
            if nome.lower().endswith(".xlsx"):
                rel = os.path.relpath(os.path.join(pasta, nome), base_dir).replace(os.sep, '/')
                subprocess.run(['git', 'add', rel], cwd=base_dir,
                               capture_output=True, text=True, check=True)

        r = subprocess.run(['git', 'commit', '-m', 'Atualiza bases do dashboard (Trading Esportivo + lista de jogos)'],
                           cwd=base_dir, capture_output=True, text=True)
        # Só faz push se realmente houve commit (evita push desnecessário)
        if r.returncode == 0:
            subprocess.run(['git', 'push'], cwd=base_dir,
                           capture_output=True, text=True, check=True)
            st.success("✅ Excel e lista de jogos enviados para o GitHub!")
    except Exception as e:
        st.warning(f"⚠️ Não foi possível enviar ao GitHub: {e}")

@st.cache_data(ttl=86400, show_spinner=False)   # 5 min — arquivo muda raramente
def load_lista_jogos():
    """Carrega a aba 'jogos', extrai o país do hyperlink e filtra os elegíveis."""
    import openpyxl
    from urllib.parse import urlparse, parse_qs
    path = os.getenv("LISTA_JOGOS_PATH", "Data/lista_jogos.xlsx")
    if not os.path.exists(path):
        path = os.getenv("LISTA_JOGOS_PATH", "data/lista_jogos.xlsx")
    df = pd.read_excel(path, sheet_name="jogos", header=0)
    # Abre com openpyxl para acessar os hyperlinks (pandas não os lê)
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["jogos"]
    # Coluna A (Country) = primeira coluna; pula o cabeçalho (min_row=2)
    links = []
    for row in ws.iter_rows(min_row=2, max_col=1):
        cell = row[0]
        target = cell.hyperlink.target if cell.hyperlink else ""
        links.append(target)
    links = links[:len(df)]  # garante alinhamento com o DataFrame
    def extrair_pais(link):
        if not link:
            return None
        try:
            qs = parse_qs(urlparse(link).query)
            if "league" in qs and qs["league"]:
                # Retorna minúsculo, igual ao formato do paises.csv
                return qs["league"][0].strip().lower()
        except Exception:
            pass
        return None
    df["País"] = [extrair_pais(l) for l in links]
    # Filtra apenas os países elegíveis (se o paises.csv existir)
    try:
        paises_elegiveis = load_paises_elegiveis()
        if paises_elegiveis:
            df = df[df["País"].isin(paises_elegiveis)]
    except Exception:
        pass  # se não conseguir carregar o CSV, mostra tudo
    return df

def _normalizar_nome(nome):
    """Padroniza nome de time de forma robusta.
    - Colapsa todos os tipos de espaço (incluindo invisíveis)
    - Remove apóstrofos e variações (O'Higgins -> OHiggins)
    - Remove acentos, minúsculas, sem espaços duplos"""
    if not isinstance(nome, str):
        return ""
    # 1) colapsa todos os tipos de espaço
    n = re.sub(r"[\s\u00a0\u2000-\u200b\u202f\u205f\u3000]+", " ", nome)
    # 2) remove apóstrofos e variações (reto, curvo, modificador, etc.)
    n = re.sub(r"['\u2018\u2019\u02bc\u201b\u2032]", "", n)
    # 3) remove acentos
    n = unicodedata.normalize("NFD", n)
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    # 4) minúsculas, sem espaços duplos
    n = n.strip().lower()
    n = " ".join(n.split())
    return n


SHEET_ID = "1PULV-NfTqPNwOUMbsV2YJYWb_CfirDoFn4b1vG7hHFE"
SHEET_GID = 1612712257  # aba "Jogos Futuros do PAINEL"

@st.cache_data(ttl=86400, show_spinner=False)
def load_base_extra():
    """Lê a base direto do Google Sheets. Cache em disco (evita refetch no restart)."""
    return _cache_local("base_extra", _fetch_base_extra, ttl=21600)

def _fetch_base_extra():
    url = (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
        f"/export?format=csv&gid={SHEET_GID}"
    )
    df = pd.read_csv(url)
    base = pd.DataFrame({
        "Nome Casa": df["Nome Casa"],
        "Nome Fora": df["Nome Fora"],
        "Classif Geral Casa": pd.to_numeric(df["Classif Geral Casa"], errors="coerce").fillna(0).astype(int),
        "Classif Geral Fora": pd.to_numeric(df["Classif Geral Fora"], errors="coerce").fillna(0).astype(int),
        "Odd Abertura Casa": pd.to_numeric(
            df["Odd Abertura Casa"].astype(str).str.replace(",", ".").str.strip(),
            errors="coerce",
        ).fillna(0.0),
        "Odd Abertura Visitante": pd.to_numeric(
            df["Odd Abertura Visitante"].astype(str).str.replace(",", ".").str.strip(),
            errors="coerce",
        ).fillna(0.0),
    })
    base["Casa_N"] = base["Nome Casa"].map(_normalizar_nome)
    base["Fora_N"] = base["Nome Fora"].map(_normalizar_nome)
    base = base.drop_duplicates(subset=["Casa_N", "Fora_N"], keep="first")
    return base

@st.cache_data(ttl=86400, show_spinner=False)
def load_metodos_jogos():
    """Retorna lista de dicts: data, pais, mandante, horario, visitante, metodos. Só cache em memória."""
    return _fetch_metodos_jogos()

def _fetch_metodos_jogos():
    try:
        r = requests.get(METODOS_URL, timeout=30)
        dados = r.json().get("rows", [])
        # Garante que seja SEMPRE uma lista de dicts (nunca DataFrame)
        if isinstance(dados, pd.DataFrame):
            dados = dados.to_dict("records")
        if not isinstance(dados, list):
            return []
        return [dict(d) for d in dados if isinstance(d, dict)]
    except Exception as e:
        print(f"[aviso] _fetch_metodos_jogos: {e}")
        return []

def salvar_metodos(linhas):
    """Grava os métodos em lote. O Apps Script responde 302 quando o doPost roda.
    Seguir o redirect com POST causa 405 HTML — então tratamos o 302 como sucesso."""
    try:
        r = requests.post(METODOS_URL, json={"rows": linhas}, allow_redirects=False, timeout=30)
        # 302/301 = doPost executou e gravou; não seguimos o redirect (evita o 405)
        if r.status_code in (301, 302, 303, 307, 308):
            return {"ok": True, "saved": len(linhas)}
        # Se já vier JSON direto, usa
        try:
            return r.json()
        except Exception:
            return {"ok": True, "saved": len(linhas)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def deletar_metodos(linhas):
    """Remove os jogos (linhas inteiras) da aba Métodos no Google Sheets."""
    try:
        r = requests.post(METODOS_URL, json={"destino": "limpar", "linhas": linhas},
                          allow_redirects=False, timeout=30)
        # 302/301 = doPost executou e removeu; não seguimos o redirect (evita o 405)
        if r.status_code in (301, 302, 303, 307, 308):
            return {"ok": True, "saved": len(linhas)}
        # Se já vier JSON direto, usa
        try:
            return r.json()
        except Exception:
            return {"ok": True, "saved": len(linhas)}
    except Exception as e:
        return {"ok": False, "erro": str(e)}

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def _cache_local(nome, funcao, ttl=21600):
    """Lê de um cache em disco; se estiver velho, refaz a rede e regrava."""
    path = os.path.join(CACHE_DIR, nome + ".pkl")
    if os.path.exists(path):
        idade = time.time() - os.path.getmtime(path)
        if idade < ttl:
            try:
                with open(path, "rb") as f:
                    return pickle.load(f)
            except Exception:
                pass  # arquivo corrompido -> refaz a rede
    dado = funcao()
    try:
        with open(path, "wb") as f:
            pickle.dump(dado, f)
    except Exception as e:
        print(f"[aviso] _cache_local({nome}): {e}")
    return dado