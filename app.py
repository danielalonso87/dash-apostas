import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import math
from utils.data_loader import load_data
from utils.metrics import calculate_kpis
from utils.data_loader import load_data, load_metodos
from utils.metrics import calculate_kpis, calcular_stakes

# --- CONFIG DA PÁGINA (PRIMEIRO COMANDO) ---
st.set_page_config(
    page_title="Dashboard Trading Esportivo",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CARREGA DADOS ---
with st.spinner("Carregando base de dados..."):
    df = load_data()

# --- SIDEBAR: FILTROS ---
st.sidebar.header("🔍 Filtros")

# Data — seletor de mês rápido + range flexível
if 'Data' in df.columns:
    min_date = df['Data'].min().date()
    max_date = df['Data'].max().date()

    # Seletor de mês/ano para navegação rápida
    meses_disponiveis = df['Data'].dt.to_period('M').unique()
    meses_ordenados = sorted(meses_disponiveis, reverse=True)
    meses_labels = [str(m) for m in meses_ordenados]

    with st.sidebar.expander("📅 Filtro de Data", expanded=True):
        mes_selecionado = st.selectbox(
            "Mês (atalho)",
            options=["Todos"] + meses_labels,
            index=0
        )

        if mes_selecionado != "Todos":
            periodo = pd.Period(mes_selecionado, freq='M')
            default_start = max(periodo.start_time.date(), min_date)
            default_end = min(periodo.end_time.date(), max_date)
        else:
            default_start = min_date
            default_end = max_date

        date_range = st.date_input(
            "Período (ajuste fino)",
            value=(default_start, default_end),
            min_value=min_date,
            max_value=max_date
        )

    if len(date_range) == 2:
        df_filtered = df[
            (df['Data'] >= pd.Timestamp(date_range[0])) &
            (df['Data'] < pd.Timestamp(date_range[1]) + pd.Timedelta(days=1))
        ].copy()
    else:
        df_filtered = df.copy()

# Método (multiselect)
if 'Método' in df.columns:
    metodos = sorted(df_filtered['Método'].dropna().unique())
    selected_metodos = st.sidebar.multiselect(
        "Método", options=metodos, default=[]
    )
    if selected_metodos:
        df_filtered = df_filtered[df_filtered['Método'].isin(selected_metodos)]

# Filtro de Placar como "Submétodo" (dependente do Método selecionado)
if 'Placar' in df.columns and 'Método' in df.columns:
    # Se método(s) foi/foram selecionado(s), mostra só os placares deles
    if selected_metodos:
        placar_disponiveis = df_filtered[df_filtered['Método'].isin(selected_metodos)]['Placar'].dropna().unique()
    else:
        placar_disponiveis = df['Placar'].dropna().unique()

    submétodos = sorted(placar_disponiveis)
    selected_sub = st.sidebar.multiselect(
        "Submétodo", options=submétodos, default=[]
    )
    if selected_sub:
        df_filtered = df_filtered[df_filtered['Placar'].isin(selected_sub)]

# Filtro de Odd (inputs manuais com valor mínimo e máximo)
if 'Odd' in df.columns:
    odd_min = float(df['Odd'].min())
    odd_max = float(df['Odd'].max())
    st.sidebar.markdown("**🎲 Odd**")
    col_odd1, col_odd2 = st.sidebar.columns(2)
    with col_odd1:
        odd_min_input = st.number_input(
            "Mín",
            min_value=0.0,
            value=odd_min,
            step=0.1,
            format="%.2f",
            label_visibility="collapsed"
        )
    with col_odd2:
        odd_max_input = st.number_input(
            "Máx",
            min_value=0.0,
            value=odd_max,
            step=0.1,
            format="%.2f",
            label_visibility="collapsed"
        )
    df_filtered = df_filtered[
        df_filtered['Odd'].isna() | (  # ← mantém linhas sem Odd
            (df_filtered['Odd'] >= odd_min_input) &
            (df_filtered['Odd'] <= odd_max_input)
        )
    ]

# --- Configuração do gráfico de faixas de odd ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Gráfico de Faixas")
passo_faixa = st.sidebar.slider(
    "Tamanho da faixa de odd",
    min_value=1, max_value=10, value=2, step=1,
    help="Ex: 2 = agrupa de 2 em 2 (1–3, 3–5, 5–7...)"
)

# Mostrar dados brutos na sidebar
st.sidebar.markdown("---")

    # ... (último filtro)

    # --- COLA: Datas de início dos métodos ---
st.sidebar.markdown("### 📋 Cola")
st.sidebar.markdown(
        """
| Método | Desde |
|---|---|
| 🦓 **Lay Zebra** | `12/03/2026` |
| 📋 **Masterlist** | `29/06/2026` |
| ✅ **Valida** | `26/06/2026` |
| 🎯 **Lay CS** | `06/03/2026` |
"""
    )

tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "🧮 Calculadora", "🎯 Stakes"])

with tab1:
    # --- TÍTULO ---
    st.title("📊 Dashboard de Trading Esportivo")
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
                # Descobre o case real da pasta (evita ambiguidade no Windows)
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
        try:
            with open(CONFIG_STAKES, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _push_para_github():
        """Envia o config_stakes.json para o GitHub após salvar."""
        import subprocess
        try:
            rel = os.path.relpath(CONFIG_STAKES, BASE_DIR).replace(os.sep, '/')

            subprocess.run(['git', 'add', rel], cwd=BASE_DIR,
                           capture_output=True, text=True, check=True)
            subprocess.run(['git', 'commit', '-m', 'Atualiza config_stakes.json'],
                           cwd=BASE_DIR, capture_output=True, text=True)
            subprocess.run(['git', 'push'], cwd=BASE_DIR,
                           capture_output=True, text=True, check=True)

            st.success("✅ Config enviada para o GitHub!")
            return True
        except Exception as e:
            st.warning(f"⚠️ Não foi possível enviar ao GitHub: {e}")
            return False

    def _salvar_config(cfg):
        try:
            pasta = os.path.dirname(CONFIG_STAKES)
            os.makedirs(pasta, exist_ok=True)
            with open(CONFIG_STAKES, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            return _push_para_github()
        except Exception:
            return False

    cfg = _carregar_config()

    # ---- Entradas ----
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

    if st.button("💾 Salvar configurações", type="secondary"):
        cfg_novo = _carregar_config()  # carrega o que JÁ existe no arquivo
        cfg_novo['banca'] = banca
        cfg_novo['dd'] = dd_pct
        cfg_novo['tipo_red'] = tipo_red
        if _salvar_config(cfg_novo):
            st.success("Configurações salvas em Data/config_stakes.json")
        else:
            st.warning("Não foi possível salvar. Verifique permissão de escrita na pasta Data.")

    st.markdown("---")
    st.subheader("📋 Métodos e Stakes")

    # ---- Carrega a base de métodos ----
    try:
        df_metodos = load_metodos()
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

            # ---- Stake manual por método (dentro de expander, abaixo da tabela) ----
            with st.expander("🎚️ Stake manual por método"):
                stakes_manuais = cfg.get('stakes_manuais', {})
                nomes_metodos = df_stakes['Método'].astype(str).tolist()

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

                if st.button("💾 Salvar stakes manuais", type="secondary"):
                    cfg_novo = _carregar_config()  # carrega o que JÁ existe no arquivo
                    novos = {}
                    for nome in nomes_metodos:
                        novos[nome] = float(st.session_state.get(f"stake_manual_{nome}", 0.0))
                    cfg_novo['stakes_manuais'] = novos
                    if _salvar_config(cfg_novo):
                        st.success("Stakes manuais salvas em Data/config_stakes.json")
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