import pandas as pd
import os
from dotenv import load_dotenv
import streamlit as st

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

    # Converte colunas numéricas
    num_cols = ['L/P Líquido', 'Comissão%', 'L/P Bruto', 'Odd',
                'Stake/Responsabilidade', 'ComissãoR$', 'Stakes',
                'Resultado_Binario']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    if 'Campeonato' in df.columns:
        df['Campeonato'] = df['Campeonato'].fillna('Não informado')

    return df

def load_metodos():
    """Carrega a base manual dos métodos (Data/metodos.xlsx)."""
    path = os.getenv("METODOS_PATH", "Data/metodos.xlsx")
    # Fallback caso a pasta seja minúscula ("data/")
    if not os.path.exists(path):
        path = os.getenv("METODOS_PATH", "data/metodos.xlsx")
    df = pd.read_excel(path)
    return df