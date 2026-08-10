import pandas as pd
import os
from dotenv import load_dotenv
import streamlit as st
import subprocess

load_dotenv()

@st.cache_data
def load_data():
    path = os.getenv("DATA_PATH", "data/Trading Esportivo.xlsx")
    sheet = os.getenv("SHEET_NAME", "Base")

    df = pd.read_excel(path, sheet_name=sheet, header=1)

    # Remove APENAS colunas 'Unnamed' (lixo visual fora da tabela "base")
    df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]

    # Remove linhas totalmente vazias (se houver)
    df = df.dropna(how='all')

    # Converte colunas de data
    for col in ['Data', 'Data de liquidação']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    # Combina Data + Horário para ter data e hora completas
    if 'Horário' in df.columns and 'Data' in df.columns:
        hora_td = pd.to_timedelta(
            df['Horário'].dt.time.astype(str), errors='coerce'
        )
        df['Data'] = df['Data'] + hora_td.fillna(pd.Timedelta(0))

    # Converte colunas numéricas
    num_cols = ['L/P Líquido', 'Comissão%', 'L/P Bruto', 'Odd',
                'Stake/Responsabilidade', 'ComissãoR$', 'Stakes',
                'Resultado_Binario']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    if 'Campeonato' in df.columns:
        df['Campeonato'] = df['Campeonato'].fillna('Não informado')

    # Envia o Excel para o GitHub se houver mudança
    _push_excel_para_github()

    return df

def _push_excel_para_github():
    """Envia o Trading Esportivo.xlsx para o GitHub se houver mudança."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        rel = os.path.relpath(os.getenv("DATA_PATH", "data/Trading Esportivo.xlsx"),
                              base_dir).replace(os.sep, '/')

        subprocess.run(['git', 'add', rel], cwd=base_dir,
                       capture_output=True, text=True, check=True)
        r = subprocess.run(['git', 'commit', '-m', 'Atualiza Trading Esportivo.xlsx'],
                           cwd=base_dir, capture_output=True, text=True)
        # Só faz push se realmente houve commit (evita push desnecessário)
        if r.returncode == 0:
            subprocess.run(['git', 'push'], cwd=base_dir,
                           capture_output=True, text=True, check=True)
            st.success("✅ Excel enviado para o GitHub!")
    except Exception as e:
        st.warning(f"⚠️ Não foi possível enviar o Excel ao GitHub: {e}")

def load_metodos():
    """Carrega a base manual dos métodos (Data/metodos.xlsx)."""
    path = os.getenv("METODOS_PATH", "Data/metodos.xlsx")
    # Fallback caso a pasta seja minúscula ("data/")
    if not os.path.exists(path):
        path = os.getenv("METODOS_PATH", "data/metodos.xlsx")
    df = pd.read_excel(path)
    return df