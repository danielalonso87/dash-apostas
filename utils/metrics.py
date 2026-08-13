import pandas as pd
import math
import unicodedata
import streamlit as st

@st.cache_data(show_spinner=False)
def calculate_kpis(df):
    """Calcula indicadores principais para trading esportivo"""
    total_apostas = len(df)
    total_green = df['Resultado_Binario'].sum() if 'Resultado_Binario' in df.columns else 0
    lucro_total = df['L/P Líquido'].sum() if 'L/P Líquido' in df.columns else 0
    total_stakes = df['Stake/Responsabilidade'].sum() if 'Stake/Responsabilidade' in df.columns else 0

    kpis = {
        'Lucro Total': lucro_total,
        'Total de Apostas': total_apostas,
        'Green %': (total_green / total_apostas * 100) if total_apostas > 0 else 0,
        'ROI %': (lucro_total / total_stakes * 100) if total_stakes > 0 else 0,
        'Odd Média': df['Odd'].mean() if 'Odd' in df.columns else 0,
        'Ticket Médio': df['Stake/Responsabilidade'].mean() if 'Stake/Responsabilidade' in df.columns else 0,
        'Lucro Líquido': df['L/P Líquido'].sum() if 'L/P Líquido' in df.columns else 0,
        'Lucro Bruto': df['L/P Bruto'].sum() if 'L/P Bruto' in df.columns else 0,
        'Comissão Total': df['ComissãoR$'].sum() if 'ComissãoR$' in df.columns else 0,
        'Maior Odd Green': df.loc[df['Resultado_Binario'] == 1, 'Odd'].max() if 'Odd' in df.columns and 'Resultado_Binario' in df.columns else 0,
    }

    # Lucro acumulado ao longo do tempo — agregado por DIA (curva suave)
    if 'Data' in df.columns and 'L/P Líquido' in df.columns:
        # Agrupa por dia: soma o lucro de todas as apostas do mesmo dia
        df_daily = df.groupby(df['Data'].dt.date)['L/P Líquido'].sum().reset_index()
        df_daily.columns = ['Data', 'L/P Líquido']
        df_daily = df_daily.sort_values('Data')
        df_daily['Lucro_Acumulado'] = df_daily['L/P Líquido'].cumsum()
        df_daily['Data'] = pd.to_datetime(df_daily['Data'])
        kpis['curva_lucro'] = df_daily
    else:
        kpis['curva_lucro'] = pd.DataFrame()

    # Lucro por Exchange
    if 'Exchange' in df.columns and 'L/P Líquido' in df.columns:
        kpis['lucro_exchange'] = df.groupby('Exchange')['L/P Líquido'].sum().sort_values(ascending=False)
    else:
        kpis['lucro_exchange'] = pd.Series(dtype=float)

    # Lucro por Campeonato
    if 'Campeonato' in df.columns and 'L/P Líquido' in df.columns:
        kpis['lucro_campeonato'] = df.groupby('Campeonato')['L/P Líquido'].sum().sort_values(ascending=False).head(10)
    else:
        kpis['lucro_campeonato'] = pd.Series(dtype=float)

    # Odd mínima e máxima
    kpis['Odd Mínima'] = df['Odd'].min() if 'Odd' in df.columns else 0
    kpis['Odd Máxima'] = df['Odd'].max() if 'Odd' in df.columns else 0

    # Red máximo e Red médio (% da stake, convertido de decimal para %)
    if 'Stakes' in df.columns and 'Resultado_Binario' in df.columns:
        reds = df[df['Resultado_Binario'] == 0]['Stakes']
        kpis['Red Máximo %'] = reds.min() * 100 if not reds.empty else 0
        kpis['Red Médio %'] = reds.mean() * 100 if not reds.empty else 0

        greens = df[df['Resultado_Binario'] == 1]['Stakes']
        kpis['Green Médio %'] = greens.mean() * 100 if not greens.empty else 0
    else:
        kpis['Red Máximo %'] = 0
        kpis['Red Médio %'] = 0
        kpis['Green Médio %'] = 0

    # Média de apostas por mês
    if 'Data' in df.columns:
        total_apostas_periodo = len(df)
        dias_periodo = (df['Data'].max() - df['Data'].min()).days
        if dias_periodo > 0:
            kpis['Apostas/Mês'] = round((total_apostas_periodo / dias_periodo) * 30, 1)
        else:
            kpis['Apostas/Mês'] = total_apostas_periodo  # só 1 dia
    else:
        kpis['Apostas/Mês'] = 0

    # Soma total de Stakes
    kpis['Total Stakes'] = df['Stakes'].sum() if 'Stakes' in df.columns else 0

    return kpis

def _normalizar(nome):
    """Remove acentos e caracteres especiais para comparar nomes de colunas."""
    nome = unicodedata.normalize('NFKD', str(nome)).encode('ascii', 'ignore').decode('utf-8')
    return ''.join(c for c in nome.lower() if c.isalnum())

def calcular_stakes(df_metodos, banca, dd_pct, tipo_red='Red Médio'):
    """Calcula EV, perdas consecutivas e stake para cada método.

    df_metodos: DataFrame com Nome, WR, Green Médio, Red Médio, Red Máximo, Apostas/mês
    banca: valor atual da banca (R$)
    dd_pct: drawdown máximo em % (ex: 10 = 10%)
    tipo_red: 'Red Médio' ou 'Red Máximo'
    """
    # --- Mapeia colunas por nome normalizado (aceita variações de grafia) ---
    col_map = {_normalizar(c): c for c in df_metodos.columns}
    def pegar(*nomes):
        for n in nomes:
            if n in col_map:
                return col_map[n]
        return None

    col_nome    = pegar('nome', 'metodo', 'metodos')
    col_wr      = pegar('wr', 'winrate')
    col_green   = pegar('greenmedio', 'green')
    col_red_med = pegar('redmedio', 'red')
    col_red_max = pegar('redmaximo', 'redmax')
    col_apostas = pegar('apostasmes', 'apostas', 'apostaspor mes')

    if col_nome is None or col_wr is None:
        return None, f"Colunas obrigatórias não encontradas. Existentes: {list(df_metodos.columns)}"

    df_m = pd.DataFrame({
        'Método':      df_metodos[col_nome].astype(str),
        'WR':          pd.to_numeric(df_metodos[col_wr], errors='coerce'),
        'Green Médio': pd.to_numeric(df_metodos[col_green], errors='coerce').abs() if col_green else 0,
        'Red Médio':   pd.to_numeric(df_metodos[col_red_med], errors='coerce').abs() if col_red_med else 0,
        'Red Máximo':  pd.to_numeric(df_metodos[col_red_max], errors='coerce').abs() if col_red_max else 0,
        'Apostas/mês': pd.to_numeric(df_metodos[col_apostas], errors='coerce').fillna(0) if col_apostas else 0,
    }).dropna(subset=['Método', 'WR'])

    # WR: se estiver em % (ex: 62), converte para fração (0.62)
    if df_m['WR'].max() > 1:
        df_m['WR'] = df_m['WR'] / 100.0

    # --- Máximo de perdas consecutivas (N) com teste <= 5% ---
    def perdas_consecutivas(wr, apostas_mes):
        if wr >= 1:
            return 1
        if wr <= 0:
            return 999
        p_loss = 1 - wr
        trials = max(int(apostas_mes * 12), 1)
        n = 1
        while True:
            prob = 1 - (1 - p_loss ** n) ** trials
            if prob <= 0.05:
                return n
            n += 1
            if n > 1000:
                return 1000

    df_m['Perdas Cons.'] = df_m.apply(
        lambda r: perdas_consecutivas(r['WR'], r['Apostas/mês']), axis=1)

    # --- EV (em pontos percentuais) ---
    # EV = WR * Green - (1 - WR) * Red, tudo em %
    df_m['EV'] = df_m['WR'] * df_m['Green Médio'] - (1 - df_m['WR']) * df_m['Red Médio']

    # --- Stake ---
    dd_max = dd_pct / 100.0
    red_usado = df_m['Red Máximo'] if tipo_red == 'Red Máximo' else df_m['Red Médio']
    # Red já é % (ex: 5 = 5%). Perda máx por aposta = red% * stake
    # stake = (DD * banca) / N / red%
    df_m['Stake (R$)'] = (dd_max * banca) / df_m['Perdas Cons.'] / red_usado
    df_m['Stake %'] = df_m['Stake (R$)'] / banca * 100.0

    # --- Expectativa de Resultado em Stakes (EV * apostas/mês, piso 1 casa) ---
    import math as _math
    df_m['Exp. Resultado (stakes)'] = df_m.apply(
        lambda r: _math.floor(r['EV'] * r['Apostas/mês'] * 10) / 10.0, axis=1)

    return df_m, None