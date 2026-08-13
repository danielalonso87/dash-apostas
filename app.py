import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import math
from utils.data_loader import _push_excel_para_github, load_data, load_metodos, load_metodos_jogos, load_lista_jogos, load_base_extra, load_depara, _normalizar_nome, salvar_depara, salvar_metodos, _get_gs, _post_gs, deletar_metodos, CACHE_DIR
from utils.metrics import calculate_kpis, calcular_stakes
import re

# --- CONFIG DA PÁGINA (PRIMEIRO COMANDO) ---
st.set_page_config(
    page_title="Dashboard Trading Esportivo",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILO GLOBAL: fonte menor, margens reduzidas, visual uniforme ---
st.markdown("""
<style>
    /* Fonte base menor (compensa o zoom de 80%) */
    html, body, [class*="css"], .stApp {
        font-size: 13px !important;
    }
    /* Reduz margens/padding do app */
    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 1rem !important;
        padding-left: 1.2rem !important;
        padding-right: 1.2rem !important;
        max-width: 100% !important;
    }
    /* Reduz espaçamento vertical entre elementos */
    .stVerticalBlock {
        gap: 0.4rem !important;
    }
    /* Títulos menores e mais compactos */
    h1 { font-size: 1.5rem !important; margin-bottom: 0.3rem !important; }
    h2 { font-size: 1.2rem !important; margin-bottom: 0.2rem !important; }
    h3 { font-size: 1.05rem !important; margin-bottom: 0.2rem !important; }
    /* Compacta métricas (KPIs) */
    [data-testid="stMetric"] {
        padding: 0.4rem !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.3rem !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.8rem !important;
    }
    /* Reduz altura das tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.3rem !important;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 0.3rem 0.6rem !important;
        font-size: 0.9rem !important;
    }
    /* Botões compactos */
    .stButton > button {
        font-size: 0.85rem !important;
        padding: 0.3rem 0.7rem !important;
    }
    /* Esconde o "Deploy"/menu padrão para visual limpo */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- CARREGA DADOS ---
with st.spinner("Carregando base de dados..."):
    df = load_data()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 Dashboard", "🧮 Calculadora", "🎯 Stakes", "📋 Critérios", "⚽ Jogos do Dia", "🎯 Métodos"])

with tab1:
    # --- TÍTULO ---
    st.title("📊 Dashboard de Trading Esportivo")

    # --- AÇÕES (pequenas, discretas, só na tab1) ---
    col_acao1, col_acao2 = st.columns([1, 1])
    with col_acao1:
        if st.button("🗑️ Limpar cache", help="Recarrega os dados do Google Sheets", use_container_width=True):
            import shutil
            shutil.rmtree(CACHE_DIR, ignore_errors=True)
            os.makedirs(CACHE_DIR, exist_ok=True)
            st.cache_data.clear()
            st.rerun()
    with col_acao2:
        if st.button("📤 Enviar Excel p/ GitHub", help="Sobe a base atualizada para o repositório", use_container_width=True):
            _push_excel_para_github()

   # ============================================================
    # Constantes usadas pelo filtro (métodos/submétodos padrão)
    # ============================================================
    METODOS_PADRAO = [
        "BnR", "Lay CS", "Lay Zebra", "Masterlist",
        "Over Limite Lay Fora", "Projeto +EV", "Valida"
    ]
    SUB_PADRAO = [
        "0x0", "0x1", "0x1 Favorito", "0x1 Zebra",
        "1x0 Zebra", "1x1", "2x0", "BTTS",
        "Casa", "HT/FT Casa", "HT/FT Neutro",
        "HT/FT Visitante", "Lay Fora", "Neutro", "Visitante"
    ]
    if "prev_sel_padrao" not in st.session_state:
        st.session_state.prev_sel_padrao = False

    with st.expander("🔍 Filtros", expanded=False):
        # ---- Checkbox (definido ANTES dos multiselects, que usam o valor) ----
        selecionar_padrao = st.checkbox(
            "⚡ Selecionar métodos padrão", key="sel_padrao",
            help="Marca todos os métodos e submétodos padrão de uma vez"
        )
        if selecionar_padrao != st.session_state.prev_sel_padrao:
            st.session_state.prev_sel_padrao = selecionar_padrao
            for k in ["metodos_ms", "sub_ms"]:
                if k in st.session_state:
                    del st.session_state[k]

        # ===== LINHA 1: Mês | Período | Método | Submétodo =====
        c_f1, c_f2, c_f3, c_f4 = st.columns([1, 1.4, 1.6, 1.6])
        with c_f1:
            if 'Data' in df.columns:
                min_date = df['Data'].min().date()
                max_date = df['Data'].max().date()
                meses_disponiveis = df['Data'].dt.to_period('M').unique()
                meses_ordenados = sorted(meses_disponiveis, reverse=True)
                meses_labels = [str(m) for m in meses_ordenados]
                mes_selecionado = st.selectbox("Mês", options=["Todos"] + meses_labels, index=0)
                if mes_selecionado != "Todos":
                    periodo = pd.Period(mes_selecionado, freq='M')
                    default_start = max(periodo.start_time.date(), min_date)
                    default_end = min(periodo.end_time.date(), max_date)
                else:
                    default_start = min_date
                    default_end = max_date
        with c_f2:
            if 'Data' in df.columns:
                date_range = st.date_input("Período", value=(default_start, default_end),
                                           min_value=min_date, max_value=max_date)
                if len(date_range) == 2:
                    df_filtered = df[(df['Data'] >= pd.Timestamp(date_range[0])) &
                                     (df['Data'] < pd.Timestamp(date_range[1]) + pd.Timedelta(days=1))].copy()
                else:
                    df_filtered = df.copy()
        with c_f3:
            if 'Método' in df.columns:
                metodos = sorted(df_filtered['Método'].dropna().unique())
                metodos_padrao_validos = [m for m in METODOS_PADRAO if m in metodos]
                selected_metodos = st.multiselect("Método", options=metodos,
                                                  default=metodos_padrao_validos if selecionar_padrao else [],
                                                  key="metodos_ms")
                if selected_metodos:
                    df_filtered = df_filtered[df_filtered['Método'].isin(selected_metodos)]
        with c_f4:
            if 'Placar' in df.columns and 'Método' in df.columns:
                if selected_metodos:
                    placar_disponiveis = df_filtered[df_filtered['Método'].isin(selected_metodos)]['Placar'].dropna().unique()
                else:
                    placar_disponiveis = df['Placar'].dropna().unique()
                submétodos = sorted(placar_disponiveis)
                sub_padrao_validos = [s for s in SUB_PADRAO if s in submétodos]
                selected_sub = st.multiselect("Submétodo", options=submétodos,
                                              default=sub_padrao_validos if selecionar_padrao else [],
                                              key="sub_ms")
                if selected_sub:
                    df_filtered = df_filtered[df_filtered['Placar'].isin(selected_sub)]

        # ===== LINHA 2: Odd mín | Odd máx | Faixa odd =====
        c_g1, c_g2, c_g3 = st.columns([1, 1, 1])
        with c_g1:
            if 'Odd' in df.columns:
                odd_min_input = st.number_input("Odd mín", min_value=0.0,
                                                value=float(df['Odd'].min()), step=0.1, format="%.2f")
        with c_g2:
            if 'Odd' in df.columns:
                odd_max_input = st.number_input("Odd máx", min_value=0.0,
                                                value=float(df['Odd'].max()), step=0.1, format="%.2f")
        with c_g3:
            passo_faixa = st.slider("Faixa odd", min_value=1, max_value=10, value=2, step=1,
                                    help="Ex: 2 = agrupa de 2 em 2 (1–3, 3–5, 5–7...)")

        # Aplica o filtro de Odd (após os inputs da linha 2)
        if 'Odd' in df.columns:
            df_filtered = df_filtered[df_filtered['Odd'].isna() |
                                      ((df_filtered['Odd'] >= odd_min_input) &
                                       (df_filtered['Odd'] <= odd_max_input))]

    st.markdown(f"*{len(df_filtered):,} operações analisadas*")      
    # --- KPIs ---
    kpis = calculate_kpis(df_filtered)

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        lucro = kpis['Lucro Líquido']
        cor_lucro = "normal" if lucro >= 0 else "inverse"
        st.metric("💰 Lucro Líquido", f"R$ {lucro:,.2f}")

    with col2:
        st.metric("✅ WR %", f"{kpis['Green %']:.1f}%")

    with col3:
        st.metric("📈 ROI %", f"{kpis['ROI %']:.2f}%")

    with col4:
        st.metric("🎲 Total Stakes", f"{kpis['Total Stakes']:.1f}") 

    with col5:
        st.metric("📊 Total de Apostas", f"{kpis['Total de Apostas']:,}")

    with col6:
        st.metric("📅 Média Apostas/Mês", f"{kpis['Apostas/Mês']:.1f}")

    # Segunda fileira de KPIs
    col7, col8, col9, col10, col11, col12 = st.columns(6)

    with col7:
        st.metric("🔽 Odd Mínima", f"{kpis['Odd Mínima']:.2f}")

    with col8:
        st.metric("🔼 Odd Máxima", f"{kpis['Odd Máxima']:.2f}")

    with col9:
        st.metric("🟰 Odd Média", f"{kpis['Odd Média']:.2f}")

    with col10:
        st.metric("🟢 Green Médio (%)", f"{kpis['Green Médio %']:.1f}%")

    with col11:
        st.metric("🔴 Red Médio (%)", f"{kpis['Red Médio %']:.1f}%")

    with col12:
        st.metric("❌ Red Máximo (%)", f"{kpis['Red Máximo %']:.1f}%")


    st.markdown("---")

    # --- GRÁFICOS EM DUAS COLUNAS ---
    graf_acum, graf_mensal= st.columns(2)
    # --- GRÁFICO 1: CURVA DE LUCRO ACUMULADO (O GRÁFICO MAIS IMPORTANTE) ---
    with graf_acum:
        st.subheader("📈 Curva de Lucro Acumulado")
        curva = kpis['curva_lucro']
        if not curva.empty:
            fig_curva = px.line(
                curva,
                x='Data',
                y='Lucro_Acumulado',
                title="Evolução do Lucro ao Longo do Tempo",
                markers=False
            )
            fig_curva.update_traces(line=dict(color='#00C853', width=2))
            fig_curva.update_layout(
                hovermode='x unified',
                yaxis=dict(tickprefix="R$ "),
                xaxis=dict(title="")
            )
            # Área preenchida abaixo da curva
            fig_curva.update_traces(fill='tozeroy', fillcolor='rgba(0, 200, 83, 0.1)')
            st.plotly_chart(fig_curva, use_container_width=True)
        else:
            st.info("Dados insuficientes para gerar a curva de lucro.")

    with graf_mensal:
        st.subheader("💰 Lucro por Mês")
        if 'Data' in df_filtered.columns and 'L/P Líquido' in df_filtered.columns:
            df_filtered['Mês/Ano'] = df_filtered['Data'].dt.to_period('M').astype(str)
            lucro_mes = df_filtered.groupby('Mês/Ano')['L/P Líquido'].sum().reset_index()
            fig_lucro_mes = px.bar(
                lucro_mes,
                x='Mês/Ano',
                y='L/P Líquido',
                title="Lucro Líquido por Mês",
                color='L/P Líquido',
                color_continuous_scale=['#FF5252', '#FFD740', '#00C853'],
                text_auto='.2s'
            )
            fig_lucro_mes.update_layout(
                xaxis=dict(title=""),
                yaxis=dict(title="", tickprefix="R$ "),
                showlegend=False,
                coloraxis_showscale=False,
            )
            fig_lucro_mes.update_traces(textposition='outside')
            st.plotly_chart(fig_lucro_mes, use_container_width=True)

    # --- GRÁFICOS EM DUAS COLUNAS ---
    col_esq, col_dir = st.columns(2)

    with col_esq:
        st.subheader("📊 Apostas por Mês")
        if 'Data' in df_filtered.columns:
            df_filtered['Mês/Ano'] = df_filtered['Data'].dt.to_period('M').astype(str)
            apostas_mes = df_filtered.groupby('Mês/Ano').size().reset_index(name='Quantidade')
            fig_mes = px.bar(
                apostas_mes,
                x='Mês/Ano',
                y='Quantidade',
                title="Quantidade de Apostas por Mês",
                color='Quantidade',
                color_continuous_scale='Blues'
            )
            fig_mes.update_layout(
                xaxis=dict(title=""), yaxis=dict(title=""),
                showlegend=False,
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig_mes, use_container_width=True)

    with col_dir:
        st.subheader("📊 Lucro Líquido e Winrate por Faixa de Odd")

        cols_necessarias = ['Odd', 'Método', 'Resultado_Binario', 'L/P Líquido']
        if all(c in df_filtered.columns for c in cols_necessarias):
            # Exige pelo menos um método selecionado na sidebar
            if not selected_metodos:
                st.info("👈 Selecione pelo menos **um método** na sidebar para visualizar o gráfico de faixas de odd.")
            else:
                df_faixa = df_filtered[df_filtered['Método'].isin(selected_metodos)].copy()
                df_faixa = df_faixa.dropna(subset=['Odd', 'Método', 'Resultado_Binario'])

                if not df_faixa.empty:
                    # Formata número sem casas desnecessárias: 8.0 → "8", 8.5 → "8.5"
                    def fmt_num(x):
                        if x == int(x):
                            return str(int(x))
                        return f"{x:.2f}".rstrip('0').rstrip('.')

                    # Cria faixas fixas por método (passo escolhido na sidebar)
                    df_faixa['Faixa Odd'] = 'Única'
                    df_faixa['Odd Min'] = df_faixa['Odd']
                    for metodo in df_faixa['Método'].unique():
                        mask = df_faixa['Método'] == metodo
                        grupo = df_faixa.loc[mask]
                        if not grupo.empty:
                            inicio = math.floor(grupo['Odd'].min())
                            fim = math.ceil(grupo['Odd'].max())
                            bins = list(range(inicio, fim + passo_faixa, passo_faixa))
                            # Garante que o maior valor caiba no último bin (evita NaN)
                            if bins[-1] <= fim:
                                bins.append(bins[-1] + passo_faixa)
                            faixas = pd.cut(grupo['Odd'], bins=bins, right=False, include_lowest=True)
                            df_faixa.loc[mask, 'Faixa Odd'] = faixas.map(
                                lambda i: f"[{fmt_num(i.left)}, {fmt_num(i.right)})"
                                if isinstance(i, pd.Interval) else 'Única'
                            )
                            df_faixa.loc[mask, 'Odd Min'] = [
                                i.left if isinstance(i, pd.Interval) else grupo['Odd'].min()
                                for i in faixas
                            ]

                    # Agrega por método + faixa
                    agg_faixa = df_faixa.groupby(['Método', 'Faixa Odd'], as_index=False).agg(
                        Lucro=('L/P Líquido', 'sum'),
                        Apostas=('Resultado_Binario', 'count'),
                        Vitorias=('Resultado_Binario', 'sum'),
                        OddMin=('Odd Min', 'min')
                    )
                    agg_faixa['Winrate'] = (agg_faixa['Vitorias'] / agg_faixa['Apostas'] * 100).round(1)
                    agg_faixa['Winrate_label'] = agg_faixa['Winrate'].astype(str) + '%'

                    # Ordena para o eixo X ficar em ordem crescente de odd
                    agg_faixa = agg_faixa.sort_values(['Método', 'OddMin'])

                    # Altura: padrão (igual aos outros) com 1 linha; cresce se houver muitos métodos
                    n_metodos = agg_faixa['Método'].nunique()
                    n_linhas = (n_metodos + 1) // 2
                    altura_grafico = max(450, n_linhas * 280)

                    # Monta gráfico: barras = lucro, texto = winrate (%) — título curto, sem legenda
                    fig_faixa = px.bar(
                        agg_faixa,
                        x='Faixa Odd',
                        y='Lucro',
                        color='Método',
                        barmode='group',
                        facet_col='Método',
                        facet_col_wrap=2,
                        facet_row_spacing=0.04,
                        text='Winrate_label',
                        title="Lucro por Faixa de Odd",
                        custom_data=['Apostas', 'Winrate'],
                    )

                    fig_faixa.update_layout(
                        height=altura_grafico,
                        xaxis=dict(title=""),
                        yaxis=dict(title="", tickprefix="R$ "),
                        showlegend=False,
                    )
                    fig_faixa.update_traces(
                        textposition='outside',
                        hovertemplate=(
                            '<b>%{x}</b><br>'
                            'Método: %{fullData.name}<br>'
                            'Apostas: %{customdata[0]}<br>'
                            'Lucro: R$ %{y:,.2f}<br>'
                            'Winrate: %{customdata[1]}%'
                            '<extra></extra>'
                        )
                    )

                    st.plotly_chart(fig_faixa, use_container_width=True)
                else:
                    st.info("Sem dados para exibir nos métodos selecionados.")
        else:
            st.info("Colunas necessárias não encontradas nos dados.")

    st.markdown("---")
    st.subheader("🥧 Distribuição do Lucro")

    col_pizza1, col_pizza2 = st.columns(2)

    with col_pizza1:
        st.markdown("**Por Método**")
        if 'Método' in df_filtered.columns and 'L/P Líquido' in df_filtered.columns:
            lucro_metodo = df_filtered.groupby('Método')['L/P Líquido'].sum().reset_index()
            lucro_metodo = lucro_metodo[lucro_metodo['L/P Líquido'] != 0]
            lucro_metodo = lucro_metodo[lucro_metodo['Método'].notna()]

            if not lucro_metodo.empty:
                lucro_metodo = lucro_metodo.sort_values('L/P Líquido', ascending=True)

                fig_metodo = px.bar(
                    lucro_metodo,
                    x='L/P Líquido',
                    y='Método',
                    orientation='h',
                    title="Lucro por Método",
                    color='L/P Líquido',
                    color_continuous_scale=['#FF5252', '#FFD740', '#00C853'],
                    text_auto='.2s'
                )
                fig_metodo.update_layout(
                    xaxis=dict(title="", tickprefix="R$ ", tickfont=dict(size=10)),
                    yaxis=dict(title="", tickfont=dict(size=10)),
                    showlegend=False,
                    coloraxis_showscale=False,
                    height=400
                )
                fig_metodo.update_traces(
                    textposition='outside',
                    hoverinfo='none',
                    textfont=dict(size=12)
                )
                st.plotly_chart(fig_metodo, use_container_width=True, config={'staticPlot': True})
            else:
                st.info("Sem dados para exibir")

    with col_pizza2:
        st.markdown("**Por Submétodo (Placar)**")
        if 'Placar' in df_filtered.columns and 'L/P Líquido' in df_filtered.columns:
            # Filtra apenas os submétodos do(s) método(s) selecionado(s)
            if selected_metodos:
                df_pizza_sub = df_filtered[df_filtered['Método'].isin(selected_metodos)]
            else:
                df_pizza_sub = df_filtered.copy()

            lucro_sub = df_pizza_sub.groupby('Placar')['L/P Líquido'].sum().reset_index()
            lucro_sub = lucro_sub[lucro_sub['L/P Líquido'] != 0]
            # Remove valores vazios ou com espaço só
            lucro_sub = lucro_sub[lucro_sub['Placar'].notna()]
            lucro_sub = lucro_sub[lucro_sub['Placar'].str.strip() != '']

            if not lucro_sub.empty:
                # Ordena do maior lucro para o menor
                lucro_sub = lucro_sub.sort_values('L/P Líquido', ascending=True)

                fig_sub = px.bar(
                    lucro_sub,
                    x='L/P Líquido',
                    y='Placar',
                    orientation='h',
                    title="Lucro por Submétodo",
                    color='L/P Líquido',
                    color_continuous_scale=['#FF5252', '#FFD740', '#00C853'],
                    text_auto='.2s'
                )
                fig_sub.update_layout(
                    xaxis=dict(title="", tickprefix="R$ ", tickfont=dict(size=10)),
                    yaxis=dict(title="", tickfont=dict(size=10)),
                    showlegend=False,
                    coloraxis_showscale=False,
                    height=400
                )
                fig_sub.update_traces(
                    textposition='outside',
                    hoverinfo='none',
                    textfont=dict(size=12)
                )
                st.plotly_chart(fig_sub, use_container_width=True, config={'staticPlot': True})
            else:
                st.info("Sem dados para exibir")

    # --- TABELA INTERATIVA ---
    with st.expander("📋 Ver dados completos da base filtrada"):
        # Mostra apenas colunas relevantes
        cols_mostrar = [c for c in [
            'Data', 'Evento / Mercado', 'Exchange', 'Campeonato',
            'L/P Líquido', 'Odd', 'Stake/Responsabilidade',
            'Resultado_Binario', 'Método', 'Placar'
        ] if c in df_filtered.columns]

        df_exibicao = df_filtered[cols_mostrar].copy()
        if 'Resultado_Binario' in df_exibicao.columns:
            df_exibicao['Resultado'] = df_exibicao['Resultado_Binario'].map({1: '✅ Green', 0: '❌ Red'})
            df_exibicao = df_exibicao.drop(columns=['Resultado_Binario'])

        # Garante que 'Data' seja datetime e mantenha a hora
        if 'Data' in df_exibicao.columns:
            df_exibicao['Data'] = pd.to_datetime(df_exibicao['Data'], errors='coerce')
            df_exibicao = df_exibicao.sort_values('Data', ascending=False)

        st.dataframe(
            df_exibicao,
            use_container_width=True,
            height=500,
            column_config={
                "Data": st.column_config.DatetimeColumn(
                    "Data/Hora",
                    format="DD/MM/YYYY HH:mm:ss",
                ),
                "L/P Líquido": st.column_config.NumberColumn("Lucro/Prejuízo", format="R$ %.2f"),
                "Stake/Responsabilidade": st.column_config.NumberColumn("Stake", format="R$ %.2f"),
                "Odd": st.column_config.NumberColumn("Odd", format="%.2f"),
            }
        )


with tab2:
    st.header("🧮 Calculadora de Métodos")

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("🏠 Mandante")
        odds_mandante = st.number_input("Odds", min_value=1.0, value=2.0, step=0.01, format="%.2f", key="c_odds_mand")
        gols_marcados_mandante = st.number_input("Média Gols Marcados (casa)", min_value=0.0, value=1.50, step=0.01, format="%.2f", key="c_gm_mand")
        gols_sofridos_mandante = st.number_input("Média Gols Sofridos (casa)", min_value=0.0, value=1.00, step=0.01, format="%.2f", key="c_gs_mand")
        over25_mandante = st.number_input("Over 2.5%", min_value=0.0, max_value=100.0, value=50.0, step=0.1, format="%.1f", key="c_ov25_mand")

    with col_b:
        st.subheader("✈️ Visitante")
        odds_visitante = st.number_input("Odds", min_value=1.0, value=3.0, step=0.01, format="%.2f", key="c_odds_vis")
        gols_marcados_visitante = st.number_input("Média Gols Marcados (fora)", min_value=0.0, value=1.20, step=0.01, format="%.2f", key="c_gm_vis")
        gols_sofridos_visitante = st.number_input("Média Gols Sofridos (fora)", min_value=0.0, value=1.50, step=0.01, format="%.2f", key="c_gs_vis")
        over25_visitante = st.number_input("Over 2.5%", min_value=0.0, max_value=100.0, value=45.0, step=0.1, format="%.1f", key="c_ov25_vis")

    st.markdown("---")

    col_c, col_d = st.columns(2)

    with col_c:
        st.subheader("🎯 Odds Específicas")
        odd_0x1 = st.number_input("Odd 0x1", min_value=1.0, value=12.0, step=0.5, format="%.2f", key="c_odd_0x1")
        odd_1x0 = st.number_input("Odd 1x0", min_value=1.0, value=10.0, step=0.5, format="%.2f", key="c_odd_1x0")

    with col_d:
        st.subheader("📊 Métricas Calculadas")

        xg_mandante = (gols_marcados_mandante + gols_sofridos_visitante) / 2
        xg_visitante = (gols_marcados_visitante + gols_sofridos_mandante) / 2
        media_over25 = (over25_mandante + over25_visitante) / 2
        total_gols_mandante = gols_marcados_mandante + gols_sofridos_mandante
        total_gols_visitante = gols_marcados_visitante + gols_sofridos_visitante
        total_gols_media = (total_gols_mandante + total_gols_visitante) / 2

        df_metrics = pd.DataFrame({
            "Métrica": ["xG Mandante", "xG Visitante", "Média Over 2.5%", "Total Gols Mandante", "Total Gols Visitante", "Total Gols Média"],
            "Valor": [f"{xg_mandante:.2f}", f"{xg_visitante:.2f}", f"{media_over25:.1f}%", f"{total_gols_mandante:.2f}", f"{total_gols_visitante:.2f}", f"{total_gols_media:.2f}"]
        })
        st.table(df_metrics.set_index("Métrica"))

        st.markdown("---")
    st.subheader("✅ Autorização de Métodos")

    # ============================================================
    # 1x0 ZEBRA
    # ============================================================
    with st.expander("🦓 1x0 Zebra", expanded=True):
        c_odd_mand_maior = odds_mandante > odds_visitante
        c_odd_1x0_ok = odd_1x0 <= 30
        c_over_mand_ok = over25_mandante >= 40
        c_over_vis_ok = over25_visitante >= 40
        c_media_over_ok = media_over25 >= 50
        c_tg_mand_ok = total_gols_mandante >= 2.8
        c_tg_vis_ok = total_gols_visitante >= 2.8

        outros_falha = sum([not c_odd_1x0_ok, not c_over_mand_ok, not c_over_vis_ok,
                            not c_media_over_ok, not c_tg_mand_ok, not c_tg_vis_ok])

        if not c_odd_mand_maior:
            r_zebra, cor_zebra, motivo_zebra = "❌ REJEITADO", "red", "Odd mandante ≤ odd visitante (critério obrigatório)"
        elif outros_falha == 0:
            r_zebra, cor_zebra, motivo_zebra = "✅ APROVADO", "green", "Todos os critérios atendidos"
        elif outros_falha >= 2:
            r_zebra, cor_zebra, motivo_zebra = "❌ REJEITADO", "red", f"{outros_falha} critérios não atendidos (2 ou mais = rejeitado)"
        else:
            r_zebra, cor_zebra, motivo_zebra = "⚠️ AVALIAR", "orange", f"{outros_falha} critério não atendido — avaliar manualmente"

        col_r1, col_r2 = st.columns([1, 3])
        with col_r1:
            st.markdown(f"### <span style='color:{cor_zebra}'>{r_zebra}</span>", unsafe_allow_html=True)
        with col_r2:
            st.caption(motivo_zebra)

        st.table(pd.DataFrame([
            ("Odd Mandante > Visitante",        f"{odds_mandante:.2f} > {odds_visitante:.2f}", "✅" if c_odd_mand_maior else "❌", "Obrigatório"),
            ("Odd 1x0 ≤ 30",                    f"{odd_1x0:.2f} ≤ 30",                         "✅" if c_odd_1x0_ok else "❌", "Normal"),
            ("Over 2.5% Mandante ≥ 40%",        f"{over25_mandante:.1f}% ≥ 40%",              "✅" if c_over_mand_ok else "❌", "Normal"),
            ("Over 2.5% Visitante ≥ 40%",       f"{over25_visitante:.1f}% ≥ 40%",            "✅" if c_over_vis_ok else "❌", "Normal"),
            ("Média Over 2.5% ≥ 50%",           f"{media_over25:.1f}% ≥ 50%",                 "✅" if c_media_over_ok else "❌", "Normal"),
            ("Total Gols Mandante ≥ 2.8",        f"{total_gols_mandante:.2f} ≥ 2.8",           "✅" if c_tg_mand_ok else "❌", "Normal"),
            ("Total Gols Visitante ≥ 2.8",       f"{total_gols_visitante:.2f} ≥ 2.8",         "✅" if c_tg_vis_ok else "❌", "Normal"),
        ], columns=["Critério", "Valor", "Status", "Tipo"]).set_index("Critério"))

    # ============================================================
    # 0x1 FAVORITO
    # ============================================================
    with st.expander("⭐ 0x1 Favorito", expanded=True):
        c_odd_fav = odds_mandante > odds_visitante
        c_odd_0x1_ok = 10 <= odd_0x1 <= 18
        c_over_mand_fav = over25_mandante >= 40
        c_over_vis_fav = over25_visitante >= 40
        c_media_over_fav = media_over25 >= 50
        c_gs_mand_fav = gols_sofridos_mandante >= 1.0
        c_gm_vis_fav = gols_marcados_visitante >= 1.5

        outros_falha_fav = sum([not c_odd_0x1_ok, not c_over_mand_fav, not c_over_vis_fav,
                                not c_media_over_fav, not c_gs_mand_fav, not c_gm_vis_fav])

        if not c_odd_fav:
            r_fav, cor_fav, motivo_fav = "❌ REJEITADO", "red", "Odd mandante ≤ odd visitante (critério obrigatório)"
        elif outros_falha_fav == 0:
            r_fav, cor_fav, motivo_fav = "✅ APROVADO", "green", "Todos os critérios atendidos"
        elif outros_falha_fav >= 2:
            r_fav, cor_fav, motivo_fav = "❌ REJEITADO", "red", f"{outros_falha_fav} critérios não atendidos (2 ou mais = rejeitado)"
        else:
            r_fav, cor_fav, motivo_fav = "⚠️ AVALIAR", "orange", f"{outros_falha_fav} critério não atendido — avaliar manualmente"

        col_f1, col_f2 = st.columns([1, 3])
        with col_f1:
            st.markdown(f"### <span style='color:{cor_fav}'>{r_fav}</span>", unsafe_allow_html=True)
        with col_f2:
            st.caption(motivo_fav)

        st.table(pd.DataFrame([
            ("Odd Mandante > Visitante",          f"{odds_mandante:.2f} > {odds_visitante:.2f}", "✅" if c_odd_fav else "❌", "Obrigatório"),
            ("Odd 0x1 (10 a 18)",                 f"{odd_0x1:.2f}",                              "✅" if c_odd_0x1_ok else "❌", "Normal"),
            ("Over 2.5% Mandante ≥ 40%",          f"{over25_mandante:.1f}% ≥ 40%",              "✅" if c_over_mand_fav else "❌", "Normal"),
            ("Over 2.5% Visitante ≥ 40%",         f"{over25_visitante:.1f}% ≥ 40%",            "✅" if c_over_vis_fav else "❌", "Normal"),
            ("Média Over 2.5% ≥ 50%",             f"{media_over25:.1f}% ≥ 50%",                 "✅" if c_media_over_fav else "❌", "Normal"),
            ("Gols Sofridos Mandante ≥ 1.0",      f"{gols_sofridos_mandante:.2f} ≥ 1.0",        "✅" if c_gs_mand_fav else "❌", "Normal"),
            ("Gols Marcados Visitante ≥ 1.5",     f"{gols_marcados_visitante:.2f} ≥ 1.5",       "✅" if c_gm_vis_fav else "❌", "Normal"),
        ], columns=["Critério", "Valor", "Status", "Tipo"]).set_index("Critério"))

    # ============================================================
    # 0x1 ZEBRA
    # ============================================================
    with st.expander("🦓 0x1 Zebra", expanded=True):
        c_odd_vis_maior = odds_mandante < odds_visitante
        c_odd_0x1_ok = odd_0x1 <= 30
        c_over_mand_ok = over25_mandante >= 40
        c_over_vis_ok = over25_visitante >= 40
        c_media_over_ok = media_over25 >= 50
        c_tg_mand_ok = total_gols_mandante >= 2.8
        c_tg_vis_ok = total_gols_visitante >= 2.8

        outros_falha = sum([not c_odd_0x1_ok, not c_over_mand_ok, not c_over_vis_ok,
                            not c_media_over_ok, not c_tg_mand_ok, not c_tg_vis_ok])

        if not c_odd_vis_maior:
            r_zebra, cor_zebra, motivo_zebra = "❌ REJEITADO", "red", "Odd mandante > odd visitante (critério obrigatório)"
        elif outros_falha == 0:
            r_zebra, cor_zebra, motivo_zebra = "✅ APROVADO", "green", "Todos os critérios atendidos"
        elif outros_falha >= 2:
            r_zebra, cor_zebra, motivo_zebra = "❌ REJEITADO", "red", f"{outros_falha} critérios não atendidos (2 ou mais = rejeitado)"
        else:
            r_zebra, cor_zebra, motivo_zebra = "⚠️ AVALIAR", "orange", f"{outros_falha} critério não atendido — avaliar manualmente"

        col_r1, col_r2 = st.columns([1, 3])
        with col_r1:
            st.markdown(f"### <span style='color:{cor_zebra}'>{r_zebra}</span>", unsafe_allow_html=True)
        with col_r2:
            st.caption(motivo_zebra)

        st.table(pd.DataFrame([
            ("Odd Mandante < Visitante",        f"{odds_mandante:.2f} < {odds_visitante:.2f}", "✅" if c_odd_vis_maior else "❌", "Obrigatório"),
            ("Odd 0x1 ≤ 30",                    f"{odd_0x1:.2f} ≤ 30",                         "✅" if c_odd_0x1_ok else "❌", "Normal"),
            ("Over 2.5% Mandante ≥ 40%",        f"{over25_mandante:.1f}% ≥ 40%",              "✅" if c_over_mand_ok else "❌", "Normal"),
            ("Over 2.5% Visitante ≥ 40%",       f"{over25_visitante:.1f}% ≥ 40%",            "✅" if c_over_vis_ok else "❌", "Normal"),
            ("Média Over 2.5% ≥ 50%",           f"{media_over25:.1f}% ≥ 50%",                 "✅" if c_media_over_ok else "❌", "Normal"),
            ("Total Gols Mandante ≥ 2.8",        f"{total_gols_mandante:.2f} ≥ 2.8",           "✅" if c_tg_mand_ok else "❌", "Normal"),
            ("Total Gols Visitante ≥ 2.8",       f"{total_gols_visitante:.2f} ≥ 2.8",         "✅" if c_tg_vis_ok else "❌", "Normal"),
        ], columns=["Critério", "Valor", "Status", "Tipo"]).set_index("Critério"))

    # ============================================================
    # LAY ZEBRA
    # ============================================================
    with st.expander("🦓❌ Lay Zebra", expanded=True):
        c_lay_odd_vis = 8 <= odds_visitante <= 30
        c_lay_over_mand = over25_mandante >= 40
        c_lay_over_vis = over25_visitante >= 40
        c_lay_media_over = media_over25 >= 50
        c_lay_gm_mand = gols_marcados_mandante >= 1.5
        c_lay_gs_mand = gols_sofridos_mandante <= 1.3
        c_lay_gm_vis = gols_marcados_visitante <= 1.4
        c_lay_gs_vis = gols_sofridos_visitante >= 1.4
        c_lay_gm_vis_leq = gols_marcados_visitante <= gols_sofridos_visitante

        falhas_lay = sum([not c_lay_odd_vis, not c_lay_over_mand, not c_lay_over_vis,
                          not c_lay_media_over, not c_lay_gm_mand, not c_lay_gs_mand,
                          not c_lay_gm_vis, not c_lay_gs_vis, not c_lay_gm_vis_leq])

        if falhas_lay == 0:
            r_lay, cor_lay, motivo_lay = "✅ APROVADO", "green", "Todos os 9 critérios atendidos"
        elif falhas_lay <= 2:
            r_lay, cor_lay, motivo_lay = "⚠️ AVALIAR", "orange", f"{falhas_lay} critério(s) não atendido(s) — avaliar manualmente"
        else:
            r_lay, cor_lay, motivo_lay = "❌ REJEITADO", "red", f"{falhas_lay} critérios não atendidos (3 ou mais = rejeitado)"

        col_l1, col_l2 = st.columns([1, 3])
        with col_l1:
            st.markdown(f"### <span style='color:{cor_lay}'>{r_lay}</span>", unsafe_allow_html=True)
        with col_l2:
            st.caption(motivo_lay)

        st.table(pd.DataFrame([
            ("Odd Visitante (8 a 30)",                    f"{odds_visitante:.2f}",                                   "✅" if c_lay_odd_vis else "❌", "Normal"),
            ("Over 2.5% Mandante ≥ 40%",                  f"{over25_mandante:.1f}% ≥ 40%",                          "✅" if c_lay_over_mand else "❌", "Normal"),
            ("Over 2.5% Visitante ≥ 40%",                 f"{over25_visitante:.1f}% ≥ 40%",                        "✅" if c_lay_over_vis else "❌", "Normal"),
            ("Média Over 2.5% ≥ 50%",                     f"{media_over25:.1f}% ≥ 50%",                            "✅" if c_lay_media_over else "❌", "Normal"),
            ("Gols Marcados Mandante ≥ 1.5",               f"{gols_marcados_mandante:.2f} ≥ 1.5",                   "✅" if c_lay_gm_mand else "❌", "Normal"),
            ("Gols Sofridos Mandante ≤ 1.3",               f"{gols_sofridos_mandante:.2f} ≤ 1.3",                   "✅" if c_lay_gs_mand else "❌", "Normal"),
            ("Gols Marcados Visitante ≤ 1.4",              f"{gols_marcados_visitante:.2f} ≤ 1.4",                  "✅" if c_lay_gm_vis else "❌", "Normal"),
            ("Gols Sofridos Visitante ≥ 1.4",              f"{gols_sofridos_visitante:.2f} ≥ 1.4",                  "✅" if c_lay_gs_vis else "❌", "Normal"),
            ("Gols Marcados Vis ≤ Gols Sofridos Vis",      f"{gols_marcados_visitante:.2f} ≤ {gols_sofridos_visitante:.2f}", "✅" if c_lay_gm_vis_leq else "❌", "Normal"),
        ], columns=["Critério", "Valor", "Status", "Tipo"]).set_index("Critério"))

# ============================================================
# ABA STAKES
# ============================================================
with tab3:
    st.header("🎯 Stakes por Método")

    # ---- Persistência das configurações ----
    import os, json
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    def _encontrar_config():
        """Procura em Data/ ou data/ usando o nome REAL da pasta no disco."""
        for pasta in ['Data', 'data']:
            if os.path.isdir(os.path.join(BASE_DIR, pasta)):
                nome_real = pasta
                try:
                    nome_real = next(
                        (d for d in os.listdir(BASE_DIR)
                         if os.path.isdir(os.path.join(BASE_DIR, d))
                         and d.lower() == pasta.lower()),
                        pasta
                    )
                except Exception:
                    pass
                return os.path.join(BASE_DIR, nome_real, 'config_stakes.json')
        return os.path.join(BASE_DIR, 'data', 'config_stakes.json')

    CONFIG_STAKES = _encontrar_config()

    def _carregar_config():
        """Lê a configuração da aba Config (Sheets). Fallback: config_stakes.json local."""
        d = _get_gs("config")
        if d and d.get("ok"):
            raw = d.get("config", {})
            cfg = {"stakes_manuais": {}}
            for k, v in raw.items():
                if k.startswith("stake_manual|"):
                    try:
                        cfg["stakes_manuais"][k.split("|", 1)[1]] = float(v)
                    except Exception:
                        pass
                else:
                    cfg[k] = v
            try:
                cfg["banca"] = float(cfg.get("banca", 1000.0))
            except Exception:
                cfg["banca"] = 1000.0
            try:
                cfg["dd"] = float(cfg.get("dd", 10.0))
            except Exception:
                cfg["dd"] = 10.0
            return cfg
        try:
            with open(CONFIG_STAKES, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _salvar_config(cfg):
        """Grava a configuração na aba Config (Sheets). Fallback: json local."""
        payload = {"destino": "config", "config": {
            "banca": cfg.get("banca", 1000.0),
            "dd": cfg.get("dd", 10.0),
            "tipo_red": cfg.get("tipo_red", "Red Médio"),
        }}
        for nome, valor in (cfg.get("stakes_manuais") or {}).items():
            payload["config"][f"stake_manual|{nome}"] = valor
        resp = _post_gs(payload)
        if resp and resp.get("ok"):
            return True
        try:
            os.makedirs(os.path.dirname(CONFIG_STAKES), exist_ok=True)
            with open(CONFIG_STAKES, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    cfg = _carregar_config()

    # ---- Entradas (DENTRO de form: só rerun ao clicar em Salvar) ----
    with st.form("form_config_stakes"):
        col_banca, col_dd, col_red = st.columns(3)
        with col_banca:
            banca = st.number_input("💰 Banca atual (R$)", min_value=0.0,
                                    value=float(cfg.get('banca', 1000.0)), step=100.0, format="%.2f")
        with col_dd:
            dd_pct = st.number_input("📉 Drawdown máximo (%)", min_value=0.0, max_value=100.0,
                                     value=float(cfg.get('dd', 10.0)), step=0.5, format="%.1f",
                                     help="Ex: 10 = 10% da banca")
        with col_red:
            tipo_red = st.radio("🎯 Stake calculada por:",
                                ["Red Médio", "Red Máximo"],
                                index=0 if cfg.get('tipo_red', 'Red Médio') == 'Red Médio' else 1,
                                horizontal=True)
        salvar_cfg = st.form_submit_button("💾 Salvar configurações", type="secondary")

    if salvar_cfg:
        cfg_novo = _carregar_config()  # carrega o que JÁ existe no arquivo
        cfg_novo['banca'] = banca
        cfg_novo['dd'] = dd_pct
        cfg_novo['tipo_red'] = tipo_red
        if _salvar_config(cfg_novo):
            st.success("Configurações salvas no Google Sheets")
        else:
            st.warning("Não foi possível salvar. Verifique permissão de escrita na pasta Data.")

    st.markdown("---")
    st.subheader("📋 Métodos e Stakes")

    # ---- Carrega a base de métodos ----
    try:
        df_metodos = pd.DataFrame(load_metodos())
    except Exception as e:
        st.error(f"Não foi possível carregar metodos.xlsx: {e}")
    else:
        df_stakes, erro = calcular_stakes(df_metodos, banca, dd_pct, tipo_red)

        if erro:
            st.error(erro)
        else:
            # Stake manual escolhida pelo usuário (salva no JSON)
            stakes_manuais = cfg.get('stakes_manuais', {})
            df_stakes['Stake Manual (R$)'] = df_stakes['Método'].map(
                lambda m: float(stakes_manuais.get(m, 0.0)))

            # Stake manual / banca
            df_stakes['Stake Manual %'] = df_stakes['Stake Manual (R$)'] / banca * 100.0

            # Financeiro = stake manual * expectativa de resultado em stakes
            df_stakes['Financeiro (R$)'] = df_stakes['Stake Manual (R$)'] * df_stakes['Exp. Resultado (stakes)']

            # Sobre a banca = financeiro / banca
            df_stakes['Sobre a Banca %'] = df_stakes['Financeiro (R$)'] / banca * 100.0

            df_display = df_stakes[['Método', 'WR', 'Apostas/mês', 'Green Médio', 'Red Médio',
                                    'Red Máximo', 'Perdas Cons.', 'EV', 'Stake (R$)',
                                    'Stake Manual (R$)', 'Stake Manual %',
                                    'Exp. Resultado (stakes)', 'Financeiro (R$)',
                                    'Sobre a Banca %']].copy()
            df_display['WR'] = (df_display['WR'] * 100).round(2)

            def cor_ev(v):
                if pd.isna(v):
                    return ''
                if v > 0:
                    return 'background-color: #d4edda; color: #155724; font-weight: bold;'
                if v < 0:
                    return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
                return ''

            styler = df_display.style.format({
                'WR': '{:.2f}%',
                'Apostas/mês': '{:.0f}',
                'Green Médio': lambda v: f'{v*100:.2f}%',
                'Red Médio': lambda v: f'{v*100:.2f}%',
                'Red Máximo': lambda v: f'{v*100:.2f}%',
                'Perdas Cons.': '{:.0f}',
                'EV': lambda v: f'{v*100:.2f}%',
                'Stake (R$)': 'R$ {:.2f}',
                'Stake Manual (R$)': 'R$ {:.2f}',
                'Stake Manual %': '{:.2f}%',
                'Exp. Resultado (stakes)': '{:.1f}',
                'Financeiro (R$)': 'R$ {:.2f}',
                'Sobre a Banca %': '{:.2f}%',
            })
            if hasattr(styler, 'map'):
                styler = styler.map(cor_ev, subset=['EV'])
            else:
                styler = styler.applymap(cor_ev, subset=['EV'])

            st.dataframe(styler, use_container_width=True, hide_index=True)

            # ---- Stake manual por método (DENTRO de form: só rerun ao Salvar) ----
            with st.expander("🎚️ Stake manual por método"):
                nomes_metodos = df_stakes['Método'].astype(str).tolist()
                with st.form("form_stakes_manuais"):
                    col_stake_inputs = st.columns(3)
                    for i, nome in enumerate(nomes_metodos):
                        with col_stake_inputs[i % 3]:
                            st.number_input(
                                f"{nome}",
                                min_value=0.0,
                                value=float(stakes_manuais.get(nome, 0.0)),
                                step=1.0,
                                format="%.2f",
                                key=f"stake_manual_{nome}",
                            )
                    salvar_stakes = st.form_submit_button("💾 Salvar stakes manuais", type="secondary")

                if salvar_stakes:
                    cfg_novo = _carregar_config()  # carrega o que JÁ existe no arquivo
                    novos = {}
                    for nome in nomes_metodos:
                        novos[nome] = float(st.session_state.get(f"stake_manual_{nome}", 0.0))
                    cfg_novo['stakes_manuais'] = novos
                    if _salvar_config(cfg_novo):
                        cfg['stakes_manuais'] = novos   # atualiza o cfg local
                        st.success("Stakes manuais salvas no Google Sheets")
                        _get_gs.clear()                 # só invalida o cache do Sheets
                        st.rerun()                      # recalcula a tabela automaticamente
                    else:
                        st.warning("Não foi possível salvar.")

            # ---- Estimativa financeira total ----
            total_financeiro = df_stakes['Financeiro (R$)'].sum()
            total_sobre_banca = total_financeiro / banca * 100.0 if banca > 0 else 0
            st.markdown("---")
            st.subheader("💰 Estimativa Financeira Mensal")
            col_f1, col_f2, col_f3 = st.columns(3)
            col_f1.metric("Financeiro Total (R$)", f"R$ {total_financeiro:,.2f}")
            col_f2.metric("Sobre a Banca (%)", f"{total_sobre_banca:.2f}%")
            col_f3.metric("Banca Atual", f"R$ {banca:,.2f}")

            # ---- Resumo ----
            ev_positivos = int((df_stakes['EV'] > 0).sum())
            st.markdown(
                f"✅ **{ev_positivos} de {len(df_stakes)}** métodos com EV positivo "
                f"| Stake com base em **{tipo_red}** "
                f"| DD: **{dd_pct:.1f}%** "
                f"| Banca: **R$ {banca:,.2f}**"
            )

            with st.expander("ℹ️ Como os cálculos são feitos"):
                st.markdown("""
- **EV** = WR × Green Médio − (1 − WR) × Red Médio
- **Perdas consecutivas (N)** = menor N tal que `1 − (1 − (1−WR)^N)^(Apostas/mês × 30) ≤ 5%`
- **Stake** = (DD Máximo × Banca) ÷ N ÷ Red escolhido
- **Stake %** = Stake ÷ Banca × 100
""")


with tab4:
    st.header("📋 Critérios dos Métodos")
    st.caption("Referência rápida dos critérios de seleção de cada método.")

    # Helper para renderizar um critério compacto (valor + descrição)
    def _criterio(valor, cor, descricao):
        st.markdown(f"<span style='font-size:1.1rem;font-weight:bold;color:{cor}'>{valor}</span>", unsafe_allow_html=True)
        st.caption(descricao)

    # ============================================================
    # BnR 0x1
    # ============================================================
    st.markdown("**🎯 BnR 0x1**")
    c1, c2 = st.columns(2)
    with c1:
        _criterio("≤ 26", "#FF9800", "Odd máxima do jogo")
    with c2:
        _criterio("≤ 1,7", "#FF9800", "Odd do mandante (casa)")

    # ============================================================
    # BnR Lay Fora
    # ============================================================
    st.markdown("**🔄 BnR Lay Fora**")
    c1, c2 = st.columns(2)
    with c1:
        _criterio("≥ 7", "#00C853", "Odd do visitante (fora)")
    with c2:
        _criterio("1,33 a 2,67", "#00C853", "Faixa de odd para Over 2,5 gols")

    # ============================================================
    # Over Limite Lay Fora
    # ============================================================
    st.markdown("**📈 Over Limite Lay Fora**")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _criterio("0x0 ≥ 1,35", "#2196F3", "Odd mínima Over")
    with c2:
        _criterio("0x1 ≥ 1,26", "#2196F3", "Odd mínima Over")
    with c3:
        _criterio("1x1 ≥ 1,30", "#2196F3", "Odd mínima Over")
    with c4:
        _criterio("2x0 ≥ 1,26", "#2196F3", "Odd mínima Over")

    st.markdown("---")

    # ============================================================
    # Datas de início dos métodos
    # ============================================================
    st.markdown("**🗓️ Datas de Início dos Métodos**")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("🦓 Lay Zebra", "12/03/2026", delta=None)
    with c2:
        st.metric("📋 Masterlist", "29/06/2026", delta=None)
    with c3:
        st.metric("✅ Valida", "26/06/2026", delta=None)
    with c4:
        st.metric("🎯 Lay CS", "06/03/2026", delta=None)

with tab5:
    st.header("⚽ Jogos do Dia")
    st.caption("Jogos do mundo todo com filtros por métricas de mandante e visitante")
    try:
        df = load_lista_jogos()   # agora CACHEADA
        # 
        # 1. Extrai colunas por posição (pula a coluna 0 = número do jogo / link)
        # 
        dados = pd.DataFrame({
            "Over 2.5": df.iloc[:, 2],
            "Gols Sofridos": df.iloc[:, 4],
            "Gols Marcados": df.iloc[:, 5],
            "Total de Gols": df.iloc[:, 6],
            "GP": df.iloc[:, 8],
            "Time Mandante": df.iloc[:, 10],
            "Horário": df.iloc[:, 11],
            "Time Visitante": df.iloc[:, 12],
            "GP Visitante": df.iloc[:, 14],
            "Total de Gols Visitante": df.iloc[:, 16],
            "Gols Marcados Visitante": df.iloc[:, 17],
            "Gols Sofridos Visitante": df.iloc[:, 18],
            "Over 2.5 Visitante": df.iloc[:, 20],
            "Data": df.iloc[:, 23],   # coluna X do Excel (24ª coluna)
        })
        # 
        # 2. Converte colunas numéricas (vêm como TEXTO com ponto)
        # 
        num_cols = [
            "Over 2.5", "Gols Sofridos", "Gols Marcados", "Total de Gols", "GP",
            "GP Visitante", "Total de Gols Visitante", "Gols Marcados Visitante",
            "Gols Sofridos Visitante", "Over 2.5 Visitante"
        ]
        for c in num_cols:
            dados[c] = pd.to_numeric(
                dados[c].astype(str).str.replace(",", "."),
                errors="coerce"
            )
        # Over 2.5: converte para percentual (0.40 -> 40)
        for c in ["Over 2.5", "Over 2.5 Visitante"]:
            dados[c] = dados[c] * 100
        # Data: converte para DD/MM/AAAA
        if "Data" in dados.columns:
            dados["Data"] = (
                pd.to_datetime(dados["Data"], errors="coerce", dayfirst=True)
                .dt.strftime("%d/%m/%Y")
                .fillna(dados["Data"].astype(str))
            )
        # Horário: converte para texto "HH:MM" (vem como tipo tempo)
        if "Horário" in dados.columns:
            dados["Horário"] = dados["Horário"].apply(
                lambda x: x.strftime("%H:%M") if hasattr(x, "strftime") else str(x)
            )
        # País extraído do link da coluna Country (já filtrado no carregamento)
        if "País" in df.columns:
            dados["País"] = df["País"].values
        else:
            dados["País"] = "—"
        # 
        # 3. Limpeza: remove linhas sem info nas colunas 2.5+ (mandante e visitante)
        # 
        dados = dados.dropna(subset=["Over 2.5", "Over 2.5 Visitante"])
        # 
        # 4. Filtra: ambas as colunas GP >= 3
        # 
        dados = dados[(dados["GP"] >= 3) & (dados["GP Visitante"] >= 3)]
        # 
        # 4.5 Enriquecimento: classificação e odds (base extra do Drive) — CACHEADA
        # 
        try:
            base = load_base_extra()
        except Exception:
            base = None
        if base is not None and len(base) > 0:
            depara = load_depara()   # CACHEADA
            dados["Casa_N"] = (
                dados["Time Mandante"].map(_normalizar_nome).map(lambda x: depara.get(x, x))
            )
            dados["Fora_N"] = (
                dados["Time Visitante"].map(_normalizar_nome).map(lambda x: depara.get(x, x))
            )
            classif_map = {}
            for _, r in base.iterrows():
                if isinstance(r["Casa_N"], str) and r["Casa_N"]:
                    classif_map[r["Casa_N"]] = int(r["Classif Geral Casa"])
                if isinstance(r["Fora_N"], str) and r["Fora_N"]:
                    classif_map[r["Fora_N"]] = int(r["Classif Geral Fora"])
            odds_map = {}
            for _, r in base.iterrows():
                chave = (r["Casa_N"], r["Fora_N"])
                odds_map.setdefault(chave, (float(r["Odd Abertura Casa"]), float(r["Odd Abertura Visitante"])))
            dados["Classif Casa"] = dados["Casa_N"].map(classif_map).fillna(0).astype(int)
            dados["Classif Fora"] = dados["Fora_N"].map(classif_map).fillna(0).astype(int)
            chaves = list(zip(dados["Casa_N"], dados["Fora_N"]))
            dados["Odd Casa"] = [odds_map.get(k, (0.0, 0.0))[0] for k in chaves]
            dados["Odd Fora"] = [odds_map.get(k, (0.0, 0.0))[1] for k in chaves]
            n_classif = ((dados["Classif Casa"] != 0) | (dados["Classif Fora"] != 0)).sum()
            n_odds = ((dados["Odd Casa"] != 0) | (dados["Odd Fora"] != 0)).sum()
            st.caption(f"📊 {n_classif}/{len(dados)} com classificação · {n_odds}/{len(dados)} com odds")
        else:
            dados["Classif Casa"] = 0
            dados["Classif Fora"] = 0
            dados["Odd Casa"] = 0.0
            dados["Odd Fora"] = 0.0
        # 
        # 5. Filtros pré-definidos (checkboxes)
        # 
        st.markdown("### ⚡ Filtros pré-definidos")
        col_p1, col_p2, col_p3, col_p4 = st.columns(4)
        with col_p1:
            filtra_lay_0x1 = st.checkbox("🦓 0x1 Zebra", key="filtro_lay_0x1",
                help="Over 2.5 ≥ 40% (casa e fora), média ≥ 50%, total de gols ≥ 2.8. Odd visitante > odd mandante e classif visitante > mandante (0 libera)")
        with col_p2:
            filtra_lay_1x0 = st.checkbox("🦓 Lay 1x0 Zebra", key="filtro_lay_1x0",
                help="Over 2.5 ≥ 40% (casa e fora), média ≥ 50%, total de gols ≥ 2.8. Odd mandante > odd visitante e classif mandante > visitante (0 libera)")
        with col_p3:
            filtra_lay_fav = st.checkbox("⭐ Lay 0x1 Favorito", key="filtro_lay_fav",
                help="Over 2.5 ≥ 40% (casa e fora), média ≥ 50%, gols sofridos casa ≥ 1, gols marcados fora ≥ 1.5. Odd mandante > odd visitante e classif mandante > visitante (0 libera)")
        with col_p4:
            filtra_lay_zebra_novo = st.checkbox("🦓 Lay Zebra", key="filtro_lay_zebra_novo",
                help="Over 2.5 ≥ 40% (casa e fora), média ≥ 50%, gols marcados casa ≥ 1.5, gols sofridos casa ≤ 1.3, gols marcados fora ≤ 1.4, gols sofridos fora ≥ 1.4, gols marcados fora ≤ gols sofridos fora. Odd visitante > odd mandante e classif visitante > mandante (0 libera)")
        # 
        # 6. Filtros numéricos manuais (mín e máx)
        # 
        with st.expander("🎛️ Filtros por métricas (mín e máx)", expanded=True):
            def _limites(series, padrao=(0.0, 10.0)):
                s = pd.to_numeric(series, errors="coerce").dropna()
                if len(s) == 0:
                    return padrao
                return (float(s.min()), float(s.max()))
            def _min_max_input(label, series, key, step=0.01, format="%.2f"):
                lo, hi = _limites(series)
                c1, c2 = st.columns(2)
                with c1:
                    v_min = st.number_input(f"{label} mín", min_value=lo, max_value=hi,
                        value=lo, step=step, format=format, key=f"{key}_min")
                with c2:
                    v_max = st.number_input(f"{label} máx", min_value=lo, max_value=hi,
                        value=hi, step=step, format=format, key=f"{key}_max")
                return (v_min, v_max)
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                st.markdown("**🏠 Mandante**")
                o_m = _min_max_input("Over 2.5 (%)", dados["Over 2.5"], "o_m_pct", step=1.0, format="%.0f")
                gf_m = _min_max_input("Gols Marcados", dados["Gols Marcados"], "gf_m")
                ga_m = _min_max_input("Gols Sofridos", dados["Gols Sofridos"], "ga_m")
                ttg_m = _min_max_input("Total de Gols", dados["Total de Gols"], "ttg_m")
                class_m = _min_max_input("Classificação", dados["Classif Casa"], "class_m", step=1.0, format="%.0f")
            with col_f2:
                st.markdown("**✈️ Visitante**")
                o_v = _min_max_input("Over 2.5 (%)", dados["Over 2.5 Visitante"], "o_v_pct", step=1.0, format="%.0f")
                gf_v = _min_max_input("Gols Marcados", dados["Gols Marcados Visitante"], "gf_v")
                ga_v = _min_max_input("Gols Sofridos", dados["Gols Sofridos Visitante"], "ga_v")
                ttg_v = _min_max_input("Total de Gols", dados["Total de Gols Visitante"], "ttg_v")
                class_v = _min_max_input("Classificação", dados["Classif Fora"], "class_v", step=1.0, format="%.0f")
        # 
        # 7. Aplica os filtros pré-definidos (se marcados)
        if filtra_lay_0x1:
            dados = dados[(dados["Over 2.5"] >= 40) & (dados["Over 2.5 Visitante"] >= 40)]
            media_over = (dados["Over 2.5"] + dados["Over 2.5 Visitante"]) / 2
            dados = dados[media_over >= 50]
            dados = dados[(dados["Total de Gols"] >= 2.8) & (dados["Total de Gols Visitante"] >= 2.8)]
            cond_odd = ((dados["Odd Fora"] == 0) | (dados["Odd Casa"] == 0) | (dados["Odd Fora"] > dados["Odd Casa"]))
            cond_class = ((dados["Classif Fora"] == 0) | (dados["Classif Casa"] == 0) | (dados["Classif Fora"] > dados["Classif Casa"]))
            dados = dados[cond_odd & cond_class]
        if filtra_lay_1x0:
            dados = dados[(dados["Over 2.5"] >= 40) & (dados["Over 2.5 Visitante"] >= 40)]
            media_over = (dados["Over 2.5"] + dados["Over 2.5 Visitante"]) / 2
            dados = dados[media_over >= 50]
            dados = dados[(dados["Total de Gols"] >= 2.8) & (dados["Total de Gols Visitante"] >= 2.8)]
            cond_odd = ((dados["Odd Casa"] == 0) | (dados["Odd Fora"] == 0) | (dados["Odd Casa"] > dados["Odd Fora"]))
            cond_class = ((dados["Classif Casa"] == 0) | (dados["Classif Fora"] == 0) | (dados["Classif Casa"] > dados["Classif Fora"]))
            dados = dados[cond_odd & cond_class]
        if filtra_lay_fav:
            dados = dados[(dados["Over 2.5"] >= 40) & (dados["Over 2.5 Visitante"] >= 40)]
            media_over = (dados["Over 2.5"] + dados["Over 2.5 Visitante"]) / 2
            dados = dados[media_over >= 50]
            dados = dados[dados["Gols Sofridos"] >= 1.0]
            dados = dados[dados["Gols Marcados Visitante"] >= 1.5]
            cond_odd = ((dados["Odd Casa"] == 0) | (dados["Odd Fora"] == 0) | (dados["Odd Casa"] > dados["Odd Fora"]))
            cond_class = ((dados["Classif Casa"] == 0) | (dados["Classif Fora"] == 0) | (dados["Classif Casa"] > dados["Classif Fora"]))
            dados = dados[cond_odd & cond_class]
        if filtra_lay_zebra_novo:
            dados = dados[(dados["Over 2.5"] >= 40) & (dados["Over 2.5 Visitante"] >= 40)]
            media_over = (dados["Over 2.5"] + dados["Over 2.5 Visitante"]) / 2
            dados = dados[media_over >= 50]
            dados = dados[dados["Gols Marcados"] >= 1.5]
            dados = dados[dados["Gols Sofridos"] <= 1.3]
            dados = dados[dados["Gols Marcados Visitante"] <= 1.4]
            dados = dados[dados["Gols Sofridos Visitante"] >= 1.4]
            dados = dados[dados["Gols Marcados Visitante"] <= dados["Gols Sofridos Visitante"]]
            cond_odd = ((dados["Odd Fora"] == 0) | (dados["Odd Casa"] == 0) | (dados["Odd Fora"] > dados["Odd Casa"]))
            cond_class = ((dados["Classif Fora"] == 0) | (dados["Classif Casa"] == 0) | (dados["Classif Fora"] > dados["Classif Casa"]))
            dados = dados[cond_odd & cond_class]
        # 
        # 8. Aplica os filtros numéricos manuais
        # 
        dados = dados[
            (dados["Over 2.5"] >= o_m[0]) & (dados["Over 2.5"] <= o_m[1]) &
            (dados["Gols Marcados"] >= gf_m[0]) & (dados["Gols Marcados"] <= gf_m[1]) &
            (dados["Gols Sofridos"] >= ga_m[0]) & (dados["Gols Sofridos"] <= ga_m[1]) &
            (dados["Total de Gols"] >= ttg_m[0]) & (dados["Total de Gols"] <= ttg_m[1]) &
            (dados["Over 2.5 Visitante"] >= o_v[0]) & (dados["Over 2.5 Visitante"] <= o_v[1]) &
            (dados["Gols Marcados Visitante"] >= gf_v[0]) & (dados["Gols Marcados Visitante"] <= gf_v[1]) &
            (dados["Gols Sofridos Visitante"] >= ga_v[0]) & (dados["Gols Sofridos Visitante"] <= ga_v[1]) &
            (dados["Total de Gols Visitante"] >= ttg_v[0]) & (dados["Total de Gols Visitante"] <= ttg_v[1]) &
            (dados["Classif Casa"] >= class_m[0]) & (dados["Classif Casa"] <= class_m[1]) &
            (dados["Classif Fora"] >= class_v[0]) & (dados["Classif Fora"] <= class_v[1])
        ]
        # 
        # 9. Feedback visual
        # 
        st.caption(f"**{len(dados)} jogos** após os filtros")
        if len(dados) == 0:
            st.warning("Nenhum jogo encontrado com os filtros atuais. Ajuste os filtros para ampliar a busca.")
        # 
        # 10. Tabela + MÉTODOS editáveis
        # 
        ordem_colunas = [
            "Data", "País",
            "Over 2.5", "Gols Sofridos", "Gols Marcados", "Total de Gols", "GP",  "Classif Casa", "Odd Casa",
            "Time Mandante", "Horário", "Time Visitante",
            "Odd Fora", "Classif Fora","GP Visitante", "Total de Gols Visitante", "Gols Sofridos Visitante", "Gols Marcados Visitante", "Over 2.5 Visitante",
        ]
        dados = dados[[c for c in ordem_colunas if c in dados.columns]]
        METODOS = [
            "0x1 Zebra", "Lay 1x0", "Lay 0x1 Favorito", "Lay Zebra",
            "BnR 0x1", "BnR Lay Fora", "Masterlist", "Over Limite Lay Fora",
        ]
        def _norm_data(v):
            if not v:
                return ""
            s = str(v)
            s = s.split("T")[0].split(" ")[0]
            m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
            if m:
                return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
            return s
        def _chave(linha):
            return "|".join([
                _norm_data(linha["Data"]), str(linha["País"]),
                str(linha["Time Mandante"]), str(linha["Time Visitante"])
            ]).lower()
        # carrega os métodos salvos (Google Sheets) — CACHEADO
        metodos_salvos = load_metodos_jogos()
        chave_metodos = {}
        for m in metodos_salvos:
            k = "|".join([
                _norm_data(m.get("data", "")), str(m.get("pais", "")),
                str(m.get("mandante", "")), str(m.get("visitante", ""))
            ]).lower()
            chave_metodos[k] = set(p.strip() for p in str(m.get("metodos", "")).split(";") if p.strip())
        # VETORIZADO: monta a chave de cada linha de uma vez (sem apply por linha)
        chaves_linha = (
            dados["Data"].map(_norm_data).astype(str) + "|" +
            dados["País"].astype(str) + "|" +
            dados["Time Mandante"].astype(str) + "|" +
            dados["Time Visitante"].astype(str)
        ).str.lower()
        metodos_linha = chaves_linha.map(chave_metodos)   # Series de sets
        for metodo in METODOS:
            dados[metodo] = metodos_linha.apply(
                lambda s: metodo in s if isinstance(s, set) else False
            )
        # indicadores ficam travados; só os métodos são editáveis
        colunas_travadas = [c for c in dados.columns if c not in METODOS]
        column_config = {
            "Data": st.column_config.TextColumn("Data", alignment="center"),
            "País": st.column_config.TextColumn("País", alignment="center"),
            "Time Mandante": st.column_config.TextColumn("Time Mandante", alignment="center"),
            "Horário": st.column_config.TextColumn("Horário", alignment="center"),
            "Time Visitante": st.column_config.TextColumn("Time Visitante", alignment="center"),
            "Over 2.5": st.column_config.NumberColumn("Over 2.5", format="%.0f%%", alignment="center"),
            "Gols Marcados": st.column_config.NumberColumn("Gols Marcados", alignment="center"),
            "Gols Sofridos": st.column_config.NumberColumn("Gols Sofridos", alignment="center"),
            "Total de Gols": st.column_config.NumberColumn("Total de Gols", alignment="center"),
            "Over 2.5 Visitante": st.column_config.NumberColumn("Over 2.5 (Fora)", format="%.0f%%", alignment="center"),
            "Gols Marcados Visitante": st.column_config.NumberColumn("Gols Marcados (Fora)", alignment="center"),
            "Gols Sofridos Visitante": st.column_config.NumberColumn("Gols Sofridos (Fora)", alignment="center"),
            "Total de Gols Visitante": st.column_config.NumberColumn("Total de Gols (Fora)", alignment="center"),
            "GP": st.column_config.NumberColumn("GP", alignment="center"),
            "GP Visitante": st.column_config.NumberColumn("GP (Fora)", alignment="center"),
            "Classif Casa": st.column_config.NumberColumn("Classif Casa", format="%d", alignment="center"),
            "Classif Fora": st.column_config.NumberColumn("Classif Fora", format="%d", alignment="center"),
            "Odd Casa": st.column_config.NumberColumn("Odd Casa", format="%.2f", alignment="center"),
            "Odd Fora": st.column_config.NumberColumn("Odd Fora", format="%.2f", alignment="center"),
        }
        for metodo in METODOS:
            column_config[metodo] = st.column_config.CheckboxColumn(metodo, alignment="center")
        # Garante que todas as colunas de método sejam booleanas (sem NaN)
        colunas_metodos = [c for c in dados.columns if c not in colunas_travadas]
        for metodo in colunas_metodos:
            dados[metodo] = dados[metodo].fillna(False).astype(bool)
        # LIMITA as linhas renderizadas no editor (o componente é o mais pesado)
        MAX_EDITOR = 100
        dados_editor = dados.head(MAX_EDITOR).copy()
        if len(dados) > MAX_EDITOR:
            st.caption(f"⚠️ Mostrando os {MAX_EDITOR} primeiros de {len(dados)} jogos. Use os filtros para reduzir a lista.")
        salvo = False
        limpar = False
        if dados_editor.empty:
            st.info("Nenhum jogo encontrado para os filtros selecionados.")
        else:
            with st.form("form_metodos_indicadores"):
                st.caption("✏️ Marque os métodos direto na tabela. Nada é salvo até clicar em 💾 Salvar seleções.")
                editado = st.data_editor(
                    dados_editor,        # ← limitado a MAX_EDITOR linhas
                    use_container_width=True,
                    height=500,
                    hide_index=True,
                    disabled=colunas_travadas,
                    column_config=column_config,
                    key="editor_metodos",
                )
                col_botoes = st.columns(2)
                with col_botoes[0]:
                    salvo = st.form_submit_button("💾 Salvar seleções", type="primary", use_container_width=True)
                with col_botoes[1]:
                    limpar = st.form_submit_button("🧹 Limpar métodos", type="secondary", use_container_width=True)
        if salvo:
            linhas = []
            for _, r in editado.iterrows():
                marcados = [m for m in METODOS if bool(r.get(m, False))]
                if marcados or _chave(r) in chave_metodos:
                    linhas.append({
                        "data": _norm_data(r["Data"]),
                        "pais": str(r["País"]),
                        "mandante": str(r["Time Mandante"]),
                        "horario": str(r.get("Horário", "")),
                        "visitante": str(r["Time Visitante"]),
                        "metodos": "; ".join(marcados),
                    })
            if linhas:
                resp = salvar_metodos(linhas)
                if resp.get("ok"):
                    st.success(f"✅ {resp.get('saved', len(linhas))} jogos salvos com sucesso!")
                    load_metodos_jogos.clear()
                    st.rerun()
                else:
                    st.error(f"Erro ao salvar: {resp}")
            else:
                st.info("Nenhum jogo com método marcado.")
        if limpar:
            linhas = []
            for _, r in dados.iterrows():
                if _chave(r) in chave_metodos:
                    linhas.append({
                        "data": _norm_data(r["Data"]),
                        "pais": str(r["País"]),
                        "mandante": str(r["Time Mandante"]),
                        "horario": str(r.get("Horário", "")),
                        "visitante": str(r["Time Visitante"]),
                    })
            if linhas:
                resp = deletar_metodos(linhas)
                if resp.get("ok"):
                    st.success(f"✅ {resp.get('saved', len(linhas))} jogos removidos da planilha!")
                    load_metodos_jogos.clear()
                    st.rerun()
                else:
                    st.error(f"Erro ao limpar: {resp}")
            else:
                st.info("Nenhum jogo com registro na planilha para remover.")

        with st.expander("🔎 Times sem correspondência na base (alimenta o DE-PARA)"):
            sem_casa = sorted(set(dados.loc[dados["Classif Casa"] == 0, "Time Mandante"]))
            sem_fora = sorted(set(dados.loc[dados["Classif Fora"] == 0, "Time Visitante"]))
            st.write("**Mandantes sem dados:**")
            st.write(", ".join(sem_casa) if sem_casa else "—")
            st.write("**Visitantes sem dados:**")
            st.write(", ".join(sem_fora) if sem_fora else "—")
    except Exception as e:
        st.error(f"Erro ao carregar a lista de jogos: {e}")

with tab6:
    st.subheader("🎯 Métodos por Jogo")
    st.caption("Consulta dos métodos salvos por partida. Acessível de qualquer dispositivo.")

    # ---- funções de formatação (o Google Sheets devolve data/hora em formato datetime) ----
    def _fmt_data(v):
        if not v:
            return ""
        s = str(v)
        # se veio como datetime do Sheets, extrai só a parte da data (YYYY-MM-DD)
        if "T" in s:
            return s.split("T")[0]
        return s

    def _fmt_horario(v):
        if not v:
            return ""
        s = str(v)
        # se veio como datetime do Sheets, extrai só HH:MM
        if "T" in s:
            return s.split("T")[1][:5]
        return s

    # ---- carrega os métodos salvos ----
    metodos_salvos = load_metodos_jogos()

    if metodos_salvos:
        df_consulta = pd.DataFrame(metodos_salvos)

        # renomeia para nomes amigáveis
        df_consulta = df_consulta.rename(columns={
            "data": "Data",
            "pais": "País",
            "mandante": "Time Mandante",
            "horario": "Horário",
            "visitante": "Time Visitante",
            "metodos": "Métodos",
        })

        # formata data e horário (remove o lixo do datetime do Sheets)
        if "Data" in df_consulta.columns:
            df_consulta["Data"] = df_consulta["Data"].map(_fmt_data)
        if "Horário" in df_consulta.columns:
            df_consulta["Horário"] = df_consulta["Horário"].map(_fmt_horario)

        # mantém só as colunas relevantes e ordena por data
        ordem = ["Data", "País", "Time Mandante", "Horário", "Time Visitante", "Métodos"]
        df_consulta = df_consulta[[c for c in ordem if c in df_consulta.columns]]
        df_consulta = df_consulta.sort_values("Data").reset_index(drop=True)

        st.dataframe(
            df_consulta,
            hide_index=True,
            use_container_width=True,
            height=520,
        )
        st.caption(f"📋 {len(df_consulta)} partidas classificadas")
    else:
        st.info("Nenhum método salvo ainda. Marque os métodos na tabela principal e clique em 💾 Salvar seleções.")