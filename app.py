import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from utils import data_loader as dl
from utils.data_loader import _normalizar_nome, chave_jogo, norm_data
from utils.metrics import calcular_stakes, calculate_kpis

# ============================================================
# CONFIGURAÇÃO (ligue/desligue métodos comentando/descomentando)
# ============================================================
# Dashboard -> "⚡ Selecionar métodos padrão"
METODOS_PADRAO = [
    "Lay Super Zebra",
    "Projeto +EV",
    # "Lay CS", "Lay Fora", "Masterlist", "Over Limite Lay Fora", "1x0 | 0x1", "Botbet",
]
SUB_PADRAO = [
    "BTTS", "Casa", "HT/FT Casa", "HT/FT Neutro", "HT/FT Visitante", "Neutro",
    "Visitante", "Visitante LTD", "HT Visitante",
    # "0x0", "0x1", "1x1", "2x0", "0x1 Favorito", "0x1 Zebra", "1x0 Zebra", "Lay 1x0 2T",
]
# Colunas de checkbox na tabela "Jogos do Dia"
METODOS_EDITOR = [
    "Lay Zebra",
    # "Lay 0x1 Zebra", "Lay 1x0 Zebra", "Lay 0x1 Favorito", "BnR Lay Fora", "Masterlist",
    # "0x1 | 1x0", "Over Limite Lay Fora",
]
# Opções do formulário "Adicionar jogo manualmente" (aba Métodos)
METODOS_MANUAIS = [
    "Lay 0x1 Zebra", "Lay 1x0 Zebra", "Lay Zebra",
    # "Lay 0x1 Favorito", "BnR Lay Fora", "Masterlist", "Over Limite Lay Fora",
]
MAX_EDITOR = 100            # linhas renderizadas no editor (componente mais pesado)

# Partes ocultas: o código continua no arquivo, só não aparece na tela.
# Para voltar a ver, troque False por True (ou tire o filtro da lista).
MOSTRAR_CALCULADORA = False
MOSTRAR_CRITERIOS = False
MOSTRAR_ABA_METODOS = False          # consulta/exclusão dos métodos salvos por jogo
MOSTRAR_ADICIONAR_MANUAL = False     # "➕ Adicionar jogo manualmente" (dentro da aba Métodos)
PRESETS_OCULTOS = {"filtro_lay_0x1", "filtro_lay_1x0", "filtro_lay_fav"}
ESCALA_LUCRO = ["#FF5252", "#FFD740", "#00C853"]

st.set_page_config(page_title="Dashboard Trading Esportivo", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    html, body, [class*="css"], .stApp { font-size: 13px !important; }
    .block-container { padding: 2.6rem 1.2rem 1rem 1.2rem !important; max-width: 100% !important; }
    .stVerticalBlock { gap: 0.4rem !important; }
    h1 { font-size: 1.5rem !important; margin-bottom: 0.3rem !important; }
    h2 { font-size: 1.2rem !important; margin-bottom: 0.2rem !important; }
    h3 { font-size: 1.05rem !important; margin-bottom: 0.2rem !important; }
    [data-testid="stMetric"] { padding: 0.4rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.3rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.8rem !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 0.3rem !important; }
    .stTabs [data-baseweb="tab"] { padding: 0.3rem 0.6rem !important; font-size: 0.9rem !important; }
    .stButton > button { font-size: 0.85rem !important; padding: 0.3rem 0.7rem !important; }
    footer { visibility: hidden; }
    /* O cabeçalho fica visível só por causa do menu ⋮ (troca de tema claro/escuro) */
    header[data-testid="stHeader"] { background: transparent; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# HELPERS
# ============================================================
def flash(aba: str, msg: str, tipo: str = "success"):
    """Mensagem que sobrevive ao st.rerun(); aparece na aba indicada."""
    st.session_state[f"_flash_{aba}"] = (tipo, msg)


def mostrar_flash(aba: str):
    if f"_flash_{aba}" in st.session_state:
        tipo, msg = st.session_state.pop(f"_flash_{aba}")
        getattr(st, tipo)(msg)


def barra_h(dados, x, y, titulo, escala, text_auto, height, xprefix=None, ordem_y=None):
    """Barra horizontal estática (sem hover) — padrão dos gráficos por categoria."""
    fig = px.bar(dados, x=x, y=y, orientation="h", title=titulo, color=x,
                 color_continuous_scale=escala, text_auto=text_auto,
                 category_orders={y: ordem_y} if ordem_y else None)
    fig.update_layout(
        xaxis=dict(title="", tickfont=dict(size=10), **({"tickprefix": xprefix} if xprefix else {})),
        yaxis=dict(title="", tickfont=dict(size=10), type="category"),
        showlegend=False, coloraxis_showscale=False, height=height,
    )
    fig.update_traces(textposition="outside", hoverinfo="none", textfont=dict(size=12))
    st.plotly_chart(fig, width="stretch", config={"staticPlot": True})


def extremos(df, col, n):
    """Os N maiores + N menores de `col` (sem repetir), em ordem crescente."""
    return (pd.concat([df.nlargest(n, col), df.nsmallest(n, col)])
            .drop_duplicates(df.columns[0]).sort_values(col))


# ============================================================
# ABA 1 — DASHBOARD
# ============================================================
@st.fragment
def aba_dashboard(df: pd.DataFrame):
    mostrar_flash("dash")
    col_titulo, col_git, col_cache = st.columns([7, 1, 1], vertical_alignment="center")
    col_titulo.title("📊 Dashboard de Trading Esportivo")
    if col_git.button("📤 GitHub", help="Sobe a base atualizada para o repositório", key="btn_envia_excel"):
        with st.spinner("Enviando para o GitHub..."):
            ok, msg = dl.push_github()
        (st.success if ok else st.warning)(("✅ " if ok else "⚠️ ") + msg)
    if col_cache.button("🧹 Limpar Cache", key="btn_limpa_cache",
                        help="Apaga todo o cache (memória e disco) e recarrega os dados"):
        dl.limpar_caches()
        flash("dash", "🧹 Cache limpo! Dados recarregados.")
        st.rerun()

    selected_metodos = []
    st.session_state.setdefault("prev_sel_padrao", False)
    with st.expander("🔍 Filtros", expanded=False):
        col_padrao, col_camp = st.columns(2)
        selecionar_padrao = col_padrao.checkbox(
            "⚡ Selecionar métodos padrão", key="sel_padrao",
            help="Marca todos os métodos e submétodos padrão de uma vez")
        filtrar_campeonatos = col_camp.checkbox(
            "🏆 Filtrar Campeonatos", key="filtro_campeonatos",
            help="Filtra a base apenas pelos campeonatos listados na aba 'Campeonatos' do Google Sheets")
        # Ao desmarcar o "padrão", esvazia os multiselects
        if selecionar_padrao != st.session_state.prev_sel_padrao:
            st.session_state.prev_sel_padrao = selecionar_padrao
            if not selecionar_padrao:
                st.session_state["metodos_ms"] = []
                st.session_state["sub_ms"] = []

        # ===== LINHA 1: Mês | Período | Método | Submétodo =====
        c_f1, c_f2, c_f3, c_f4 = st.columns([0.5, 0.7, 2.2, 2.2])
        df_f = df
        if "Data" in df.columns:
            min_date, max_date = df["Data"].min().date(), df["Data"].max().date()
            meses = [str(m) for m in sorted(df["Data"].dt.to_period("M").dropna().unique(), reverse=True)]
            mes = c_f1.selectbox("Mês", options=["Todos"] + meses, index=0)
            if mes != "Todos":
                periodo = pd.Period(mes, freq="M")
                ini = max(periodo.start_time.date(), min_date)
                fim = min(periodo.end_time.date(), max_date)
            else:
                ini, fim = min_date, max_date
            date_range = c_f2.date_input("Período", value=(ini, fim), min_value=min_date, max_value=max_date)
            if len(date_range) == 2:
                df_f = df_f[(df_f["Data"] >= pd.Timestamp(date_range[0])) &
                            (df_f["Data"] < pd.Timestamp(date_range[1]) + pd.Timedelta(days=1))]

        if filtrar_campeonatos and "Campeonato" in df_f.columns:
            camp_ok = {n for n in map(_normalizar_nome, dl.load_campeonatos()) if n}
            if camp_ok:
                raw = df_f["Campeonato"]
                txt = raw.fillna("").astype(str)
                norm = txt.map(_normalizar_nome)
                vazio = {"", "nan", "none", "null", "na", "n/a", "-", "—", "–", "sem campeonato",
                         "sem informacao", "s/info", "0", "nao informado", "não informado",
                         "nao informada", "não informada"}
                eh_vazio = raw.isna() | txt.str.strip().str.lower().isin(vazio) | (norm == "")
                df_f = df_f[norm.isin(camp_ok) | eh_vazio]

        if "Método" in df.columns:
            metodos = sorted(df["Método"].dropna().unique())   # opções da base completa
            if selecionar_padrao:
                st.session_state["metodos_ms"] = [m for m in METODOS_PADRAO if m in metodos]
            selected_metodos = c_f3.multiselect("Método", options=metodos, key="metodos_ms")
            if selected_metodos:
                df_f = df_f[df_f["Método"].isin(selected_metodos)]

        if "Placar" in df.columns and "Método" in df.columns:
            base_sub = df[df["Método"].isin(selected_metodos)] if selected_metodos else df
            submetodos = sorted(base_sub["Placar"].dropna().unique())
            if selecionar_padrao:
                st.session_state["sub_ms"] = [s for s in SUB_PADRAO if s in submetodos]
            selected_sub = c_f4.multiselect("Submétodo", options=submetodos, key="sub_ms")
            if selected_sub:
                placar = df_f["Placar"].fillna("").astype(str).str.strip()
                df_f = df_f[(placar == "") | placar.isin(selected_sub)]

        # ===== LINHA 2: Odd mín | Odd máx | Faixa odd =====
        c_g1, c_g2, c_g3 = st.columns(3)
        passo_faixa = c_g3.slider("Faixa odd", min_value=1, max_value=10, value=2, step=1,
                                  help="Ex: 2 = agrupa de 2 em 2 (1–3, 3–5, 5–7...)")
        if "Odd" in df.columns:
            odd_min = c_g1.number_input("Odd mín", min_value=0.0, value=float(df["Odd"].min()),
                                        step=0.1, format="%.2f")
            odd_max = c_g2.number_input("Odd máx", min_value=0.0, value=float(df["Odd"].max()),
                                        step=0.1, format="%.2f")
            df_f = df_f[df_f["Odd"].isna() | df_f["Odd"].between(odd_min, odd_max)]

    df_f = df_f.copy()
    if "Data" in df_f.columns:
        df_f["Mês/Ano"] = df_f["Data"].dt.to_period("M").astype(str)
    st.markdown(f"*{len(df_f):,} operações analisadas*")

    # --- KPIs ---
    k = calculate_kpis(df_f)
    for cols, itens in (
        (st.columns(6), [("💰 Lucro Líquido", f"R$ {k['Lucro Líquido']:,.2f}"),
                         ("✅ WR %", f"{k['Green %']:.1f}%"),
                         ("📈 ROI %", f"{k['ROI %']:.2f}%"),
                         ("🎲 Total Stakes", f"{k['Total Stakes']:.1f}"),
                         ("📊 Total de Apostas", f"{k['Total de Apostas']:,}"),
                         ("📅 Média Apostas/Mês", f"{k['Apostas/Mês']:.1f}")]),
        (st.columns(6), [("🔽 Odd Mínima", f"{k['Odd Mínima']:.2f}"),
                         ("🔼 Odd Máxima", f"{k['Odd Máxima']:.2f}"),
                         ("🟰 Odd Média", f"{k['Odd Média']:.2f}"),
                         ("🟢 Green Médio (%)", f"{k['Green Médio %']:.1f}%"),
                         ("🔴 Red Médio (%)", f"{k['Red Médio %']:.1f}%"),
                         ("❌ Red Máximo (%)", f"{k['Red Máximo %']:.1f}%")]),
    ):
        for col, (rotulo, valor) in zip(cols, itens):
            col.metric(rotulo, valor)

    st.markdown("---")
    graf_acum, graf_mensal = st.columns(2)
    with graf_acum:
        st.subheader("📈 Curva de Lucro Acumulado")
        curva = k["curva_lucro"]
        if not curva.empty:
            fig = px.line(curva, x="Data", y="Lucro_Acumulado",
                          title="Evolução do Lucro ao Longo do Tempo")
            fig.update_traces(line=dict(color="#00C853", width=2),
                              fill="tozeroy", fillcolor="rgba(0, 200, 83, 0.1)")
            fig.update_layout(hovermode="x unified", yaxis=dict(tickprefix="R$ "), xaxis=dict(title=""))
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Dados insuficientes para gerar a curva de lucro.")

    with graf_mensal:
        st.subheader("💰 Lucro por Mês")
        if "Mês/Ano" in df_f.columns and "L/P Líquido" in df_f.columns:
            lucro_mes = df_f.groupby("Mês/Ano")["L/P Líquido"].sum().reset_index()
            fig = px.bar(lucro_mes, x="Mês/Ano", y="L/P Líquido", title="Lucro Líquido por Mês",
                         color="L/P Líquido", color_continuous_scale=ESCALA_LUCRO, text_auto=".2s")
            fig.update_layout(xaxis=dict(title=""), yaxis=dict(title="", tickprefix="R$ "),
                              showlegend=False, coloraxis_showscale=False)
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, width="stretch")

    col_esq, col_dir = st.columns(2)
    with col_esq:
        st.subheader("📊 Apostas por Mês")
        if "Mês/Ano" in df_f.columns:
            apostas_mes = df_f.groupby("Mês/Ano").size().reset_index(name="Quantidade")
            fig = px.bar(apostas_mes, x="Mês/Ano", y="Quantidade", title="Quantidade de Apostas por Mês",
                         color="Quantidade", color_continuous_scale="Blues")
            fig.update_layout(xaxis=dict(title=""), yaxis=dict(title=""),
                              showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig, width="stretch")

    with col_dir:
        st.subheader("📊 Lucro Líquido e Winrate por Faixa de Odd")
        _grafico_faixa_odd(df_f, selected_metodos, passo_faixa)

    st.markdown("---")
    n_ext = st.slider("🏆 Mostrar top N melhores e piores por campeonato", min_value=3, max_value=20,
                      value=10, step=1,
                      help="Mostra os N campeonatos com maior lucro e os N com maior prejuízo "
                           "(ou mais apostas). O meio fica de fora para facilitar a leitura.")
    col_camp1, col_camp2 = st.columns(2)
    if "Campeonato" in df_f.columns:
        camp = df_f["Campeonato"].fillna("Não informado").astype(str).str.strip()
        n_total = camp[camp != ""].nunique()
    with col_camp1:
        st.subheader("💰 Lucro (em Stakes) por Campeonato")
        if "Campeonato" in df_f.columns and "Stakes" in df_f.columns:
            lc = df_f["Stakes"].groupby(camp).sum().rename_axis("Campeonato").reset_index()
            lc = lc[lc["Stakes"] != 0]
            if lc.empty:
                st.info("Sem dados para exibir")
            else:
                lc = extremos(lc, "Stakes", n_ext)
                fora = camp.nunique() - len(lc)
                st.caption(f"Mostrando {len(lc)} de {camp.nunique()} campeonatos" + (f" · {fora} fora" if fora > 0 else ""))
                barra_h(lc, "Stakes", "Campeonato", "Lucro (em Stakes) por Campeonato", ESCALA_LUCRO,
                        ".2f", max(400, len(lc) * 28))
        else:
            st.info("Colunas necessárias não encontradas nos dados.")
    with col_camp2:
        st.subheader("📊 Apostas por Campeonato")
        if "Campeonato" in df_f.columns:
            ac = camp[camp != ""].value_counts().rename_axis("Campeonato").reset_index(name="Quantidade")
            if ac.empty:
                st.info("Sem dados para exibir")
            else:
                ac = extremos(ac, "Quantidade", n_ext)
                fora = n_total - len(ac)
                st.caption(f"Mostrando {len(ac)} de {n_total} campeonatos" + (f" · {fora} fora" if fora > 0 else ""))
                barra_h(ac, "Quantidade", "Campeonato", "Quantidade de Apostas por Campeonato", "Blues",
                        True, max(400, len(ac) * 28))

    st.markdown("---")
    st.subheader("🥧 Distribuição do Lucro")
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        st.markdown("**Por Método**")
        if "Método" in df_f.columns and "L/P Líquido" in df_f.columns:
            lm = df_f.groupby("Método")["L/P Líquido"].sum().reset_index()
            lm = lm[lm["L/P Líquido"] != 0].nlargest(10, "L/P Líquido").sort_values("L/P Líquido")
            if lm.empty:
                st.info("Sem dados para exibir")
            else:
                barra_h(lm, "L/P Líquido", "Método", "Lucro por Método (top 10)", ESCALA_LUCRO,
                        ".2s", 400, xprefix="R$ ")
    with col_p2:
        st.markdown("**Por Submétodo (Placar)**")
        if "Placar" in df_f.columns and "L/P Líquido" in df_f.columns:
            placar = df_f["Placar"].fillna("").astype(str).str.strip().replace({"nan": "", "None": ""})
            ls = df_f.loc[placar != "", "L/P Líquido"].groupby(placar[placar != ""]).sum()
            ls = ls[ls != 0].rename_axis("Placar").reset_index()
            if ls.empty:
                st.info("Sem dados para exibir")
            else:
                barra_h(ls, "L/P Líquido", "Placar", "Lucro por Submétodo", ESCALA_LUCRO, ".2s", 400,
                        xprefix="R$ ", ordem_y=ls.sort_values("L/P Líquido")["Placar"].tolist())

    with st.expander("📋 Ver dados completos da base filtrada"):
        cols = [c for c in ["Data", "Evento / Mercado", "Exchange", "Campeonato", "L/P Líquido", "Odd",
                            "Stake/Responsabilidade", "Resultado_Binario", "Método", "Placar"]
                if c in df_f.columns]
        tabela = df_f[cols].copy()
        if "Resultado_Binario" in tabela.columns:
            tabela["Resultado"] = tabela.pop("Resultado_Binario").map({1: "✅ Green", 0: "❌ Red"})
        if "Data" in tabela.columns:
            tabela = tabela.sort_values("Data", ascending=False)
        st.dataframe(tabela, width="stretch", height=500, column_config={
            "Data": st.column_config.DatetimeColumn("Data/Hora", format="DD/MM/YYYY HH:mm:ss"),
            "L/P Líquido": st.column_config.NumberColumn("Lucro/Prejuízo", format="R$ %.2f"),
            "Stake/Responsabilidade": st.column_config.NumberColumn("Stake", format="R$ %.2f"),
            "Odd": st.column_config.NumberColumn("Odd", format="%.2f"),
        })


def _grafico_faixa_odd(df_f, selected_metodos, passo):
    if not all(c in df_f.columns for c in ["Odd", "Método", "Resultado_Binario", "L/P Líquido"]):
        st.info("Colunas necessárias não encontradas nos dados.")
        return
    if not selected_metodos:
        st.info("👈 Selecione pelo menos **um método** nos filtros para visualizar o gráfico de faixas de odd.")
        return
    d = df_f[df_f["Método"].isin(selected_metodos)].dropna(subset=["Odd", "Método", "Resultado_Binario"])
    if d.empty:
        st.info("Sem dados para exibir nos métodos selecionados.")
        return

    def fmt(x):
        return str(int(x)) if x == int(x) else f"{x:.2f}".rstrip("0").rstrip(".")

    partes = []
    for metodo, g in d.groupby("Método"):
        ini, fim = int(np.floor(g["Odd"].min())), int(np.ceil(g["Odd"].max()))
        bins = list(range(ini, fim + passo, passo))
        if bins[-1] <= fim:
            bins.append(bins[-1] + passo)
        faixas = pd.cut(g["Odd"], bins=bins, right=False)
        partes.append(pd.DataFrame({
            "Método": metodo,
            "Faixa Odd": faixas.map(lambda i: f"[{fmt(i.left)}, {fmt(i.right)})").astype(str),
            "Odd Min": faixas.map(lambda i: i.left).astype(float),
            "L/P Líquido": g["L/P Líquido"], "Resultado_Binario": g["Resultado_Binario"],
        }))
    agg = (pd.concat(partes).groupby(["Método", "Faixa Odd"], as_index=False)
           .agg(Lucro=("L/P Líquido", "sum"), Apostas=("Resultado_Binario", "count"),
                Vitorias=("Resultado_Binario", "sum"), OddMin=("Odd Min", "min"))
           .sort_values(["Método", "OddMin"]))
    agg["Winrate"] = (agg["Vitorias"] / agg["Apostas"] * 100).round(1)
    agg["Winrate_label"] = agg["Winrate"].astype(str) + "%"

    fig = px.bar(agg, x="Faixa Odd", y="Lucro", color="Método", barmode="group", facet_col="Método",
                 facet_col_wrap=2, facet_row_spacing=0.04, text="Winrate_label",
                 title="Lucro por Faixa de Odd", custom_data=["Apostas", "Winrate"])
    fig.update_layout(height=max(450, ((agg["Método"].nunique() + 1) // 2) * 280),
                      xaxis=dict(title=""), yaxis=dict(title="", tickprefix="R$ "), showlegend=False)
    fig.update_traces(textposition="outside", hovertemplate=(
        "<b>%{x}</b><br>Método: %{fullData.name}<br>Apostas: %{customdata[0]}<br>"
        "Lucro: R$ %{y:,.2f}<br>Winrate: %{customdata[1]}%<extra></extra>"))
    st.plotly_chart(fig, width="stretch")


# ============================================================
# ABA 2 — CALCULADORA
# ============================================================
def _autorizacao(titulo, criterios, obrigatorio=None, max_avaliar=1):
    """criterios: [(rótulo, valor exibido, ok)]; obrigatorio: (rótulo, valor, ok) ou None."""
    falhas = sum(not ok for _, _, ok in criterios)
    total = len(criterios) + (1 if obrigatorio else 0)
    if obrigatorio and not obrigatorio[2]:
        res, cor, motivo = "❌ REJEITADO", "red", f"{obrigatorio[0]}: não atendido (critério obrigatório)"
    elif falhas == 0:
        res, cor, motivo = "✅ APROVADO", "green", f"Todos os {total} critérios atendidos"
    elif falhas > max_avaliar:
        res, cor, motivo = "❌ REJEITADO", "red", \
            f"{falhas} critérios não atendidos ({max_avaliar + 1} ou mais = rejeitado)"
    else:
        res, cor, motivo = "⚠️ AVALIAR", "orange", f"{falhas} critério(s) não atendido(s) — avaliar manualmente"
    with st.expander(titulo, expanded=True):
        c1, c2 = st.columns([1, 3])
        c1.markdown(f"### <span style='color:{cor}'>{res}</span>", unsafe_allow_html=True)
        c2.caption(motivo)
        linhas = ([(*obrigatorio, "Obrigatório")] if obrigatorio else []) + \
                 [(*c, "Normal") for c in criterios]
        st.table(pd.DataFrame([(r, v, "✅" if ok else "❌", t) for r, v, ok, t in linhas],
                              columns=["Critério", "Valor", "Status", "Tipo"]).set_index("Critério"))


@st.fragment
def aba_calculadora():
    st.header("🧮 Calculadora de Métodos")
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🏠 Mandante")
        odd_m = st.number_input("Odds", min_value=1.0, value=2.0, step=0.01, format="%.2f", key="c_odds_mand")
        gm_m = st.number_input("Média Gols Marcados (casa)", min_value=0.0, value=1.50, step=0.01, format="%.2f", key="c_gm_mand")
        gs_m = st.number_input("Média Gols Sofridos (casa)", min_value=0.0, value=1.00, step=0.01, format="%.2f", key="c_gs_mand")
        ov_m = st.number_input("Over 2.5%", min_value=0.0, max_value=100.0, value=50.0, step=0.1, format="%.1f", key="c_ov25_mand")
    with col_b:
        st.subheader("✈️ Visitante")
        odd_v = st.number_input("Odds", min_value=1.0, value=3.0, step=0.01, format="%.2f", key="c_odds_vis")
        gm_v = st.number_input("Média Gols Marcados (fora)", min_value=0.0, value=1.20, step=0.01, format="%.2f", key="c_gm_vis")
        gs_v = st.number_input("Média Gols Sofridos (fora)", min_value=0.0, value=1.50, step=0.01, format="%.2f", key="c_gs_vis")
        ov_v = st.number_input("Over 2.5%", min_value=0.0, max_value=100.0, value=45.0, step=0.1, format="%.1f", key="c_ov25_vis")

    st.markdown("---")
    col_c, col_d = st.columns(2)
    with col_c:
        st.subheader("🎯 Odds Específicas")
        odd_0x1 = st.number_input("Odd 0x1", min_value=1.0, value=12.0, step=0.5, format="%.2f", key="c_odd_0x1")
        odd_1x0 = st.number_input("Odd 1x0", min_value=1.0, value=10.0, step=0.5, format="%.2f", key="c_odd_1x0")

    xg_m, xg_v = (gm_m + gs_v) / 2, (gm_v + gs_m) / 2
    media_ov = (ov_m + ov_v) / 2
    tg_m, tg_v = gm_m + gs_m, gm_v + gs_v
    with col_d:
        st.subheader("📊 Métricas Calculadas")
        st.table(pd.DataFrame({
            "Métrica": ["xG Mandante", "xG Visitante", "Média Over 2.5%", "Total Gols Mandante",
                        "Total Gols Visitante", "Total Gols Média"],
            "Valor": [f"{xg_m:.2f}", f"{xg_v:.2f}", f"{media_ov:.1f}%", f"{tg_m:.2f}", f"{tg_v:.2f}",
                      f"{(tg_m + tg_v) / 2:.2f}"],
        }).set_index("Métrica"))
        st.markdown("---")

    st.subheader("✅ Autorização de Métodos")
    overs = [
        ("Over 2.5% Mandante ≥ 40%", f"{ov_m:.1f}% ≥ 40%", ov_m >= 40),
        ("Over 2.5% Visitante ≥ 40%", f"{ov_v:.1f}% ≥ 40%", ov_v >= 40),
        ("Média Over 2.5% ≥ 50%", f"{media_ov:.1f}% ≥ 50%", media_ov >= 50),
    ]
    totais = [
        ("Total Gols Mandante ≥ 2.8", f"{tg_m:.2f} ≥ 2.8", tg_m >= 2.8),
        ("Total Gols Visitante ≥ 2.8", f"{tg_v:.2f} ≥ 2.8", tg_v >= 2.8),
    ]
    mand_maior = ("Odd Mandante > Visitante", f"{odd_m:.2f} > {odd_v:.2f}", odd_m > odd_v)

    _autorizacao("🦓 1x0 Zebra", [("Odd 1x0 ≤ 30", f"{odd_1x0:.2f} ≤ 30", odd_1x0 <= 30), *overs, *totais],
                 obrigatorio=mand_maior)
    _autorizacao("⭐ 0x1 Favorito", [
        ("Odd 0x1 (10 a 18)", f"{odd_0x1:.2f}", 10 <= odd_0x1 <= 18), *overs,
        ("Gols Sofridos Mandante ≥ 1.0", f"{gs_m:.2f} ≥ 1.0", gs_m >= 1.0),
        ("Gols Marcados Visitante ≥ 1.5", f"{gm_v:.2f} ≥ 1.5", gm_v >= 1.5),
    ], obrigatorio=mand_maior)
    _autorizacao("🦓 Lay 0x1 Zebra", [("Odd 0x1 ≤ 30", f"{odd_0x1:.2f} ≤ 30", odd_0x1 <= 30), *overs, *totais],
                 obrigatorio=("Odd Mandante < Visitante", f"{odd_m:.2f} < {odd_v:.2f}", odd_m < odd_v))
    _autorizacao("🦓❌ Lay Zebra (Visitante)", [
        ("Odd Visitante (8 a 30)", f"{odd_v:.2f}", 8 <= odd_v <= 30), *overs,
        ("Gols Marcados Mandante ≥ 1.5", f"{gm_m:.2f} ≥ 1.5", gm_m >= 1.5),
        ("Gols Sofridos Mandante ≤ 1.3", f"{gs_m:.2f} ≤ 1.3", gs_m <= 1.3),
        ("Gols Marcados Visitante ≤ 1.4", f"{gm_v:.2f} ≤ 1.4", gm_v <= 1.4),
        ("Gols Sofridos Visitante ≥ 1.4", f"{gs_v:.2f} ≥ 1.4", gs_v >= 1.4),
        ("Gols Marcados Vis ≤ Gols Sofridos Vis", f"{gm_v:.2f} ≤ {gs_v:.2f}", gm_v <= gs_v),
    ], max_avaliar=2)


# ============================================================
# ABA 3 — STAKES
# ============================================================
@st.fragment
def aba_stakes():
    st.header("🎯 Stakes por Método")
    mostrar_flash("stakes")
    cfg = dl.load_config()

    with st.form("form_config_stakes"):
        c1, c2, c3 = st.columns(3)
        banca = c1.number_input("💰 Banca atual (R$)", min_value=0.0, value=float(cfg["banca"]),
                                step=100.0, format="%.2f")
        dd_pct = c2.number_input("📉 Drawdown máximo (%)", min_value=0.0, max_value=100.0,
                                 value=float(cfg["dd"]), step=0.5, format="%.1f", help="Ex: 10 = 10% da banca")
        tipo_red = c3.radio("🎯 Stake calculada por:", ["Red Médio", "Red Máximo"],
                            index=0 if cfg.get("tipo_red", "Red Médio") == "Red Médio" else 1, horizontal=True)
        if st.form_submit_button("💾 Salvar configurações", type="secondary"):
            if dl.salvar_config({**cfg, "banca": banca, "dd": dd_pct, "tipo_red": tipo_red}):
                flash("stakes", "Configurações salvas no Google Sheets")
                st.rerun(scope="fragment")
            st.warning("Não foi possível salvar.")

    st.markdown("---")
    st.subheader("📋 Métodos e Stakes")
    df_metodos = dl.load_metodos()
    if df_metodos.empty:
        st.error("Não foi possível carregar as estatísticas dos métodos (aba MetodosStats).")
        return
    df_s, erro = calcular_stakes(df_metodos, banca, dd_pct, tipo_red)
    if erro:
        st.error(erro)
        return

    manuais = cfg.get("stakes_manuais", {})
    df_s["Stake Manual (R$)"] = df_s["Método"].map(lambda m: float(manuais.get(m, 0.0)))
    df_s["Stake Manual %"] = df_s["Stake Manual (R$)"] / banca * 100.0 if banca else np.nan
    df_s["Financeiro (R$)"] = df_s["Stake Manual (R$)"] * df_s["Exp. Resultado (stakes)"]
    df_s["Sobre a Banca %"] = df_s["Financeiro (R$)"] / banca * 100.0 if banca else np.nan

    exib = df_s[["Método", "WR", "Apostas/mês", "Green Médio", "Red Médio", "Red Máximo", "Perdas Cons.",
                 "EV", "Stake (R$)", "Stake Manual (R$)", "Stake Manual %", "Exp. Resultado (stakes)",
                 "Financeiro (R$)", "Sobre a Banca %"]].copy()
    exib["WR"] = (exib["WR"] * 100).round(2)

    def cor_ev(v):
        if pd.isna(v) or v == 0:
            return ""
        return ("background-color: #d4edda; color: #155724; font-weight: bold;" if v > 0 else
                "background-color: #f8d7da; color: #721c24; font-weight: bold;")

    pct = lambda v: f"{v * 100:.2f}%"  # noqa: E731
    styler = exib.style.format({
        "WR": "{:.2f}%", "Apostas/mês": "{:.0f}", "Green Médio": pct, "Red Médio": pct, "Red Máximo": pct,
        "Perdas Cons.": "{:.0f}", "EV": pct, "Stake (R$)": "R$ {:.2f}", "Stake Manual (R$)": "R$ {:.2f}",
        "Stake Manual %": "{:.2f}%", "Exp. Resultado (stakes)": "{:.1f}", "Financeiro (R$)": "R$ {:.2f}",
        "Sobre a Banca %": "{:.2f}%",
    }, na_rep="").map(cor_ev, subset=["EV"])
    st.dataframe(styler, width="stretch", hide_index=True)

    with st.expander("🎚️ Stake manual por método"):
        nomes = df_s["Método"].astype(str).tolist()
        with st.form("form_stakes_manuais"):
            cols = st.columns(3)
            for i, nome in enumerate(nomes):
                cols[i % 3].number_input(nome, min_value=0.0, value=float(manuais.get(nome, 0.0)),
                                         step=1.0, format="%.2f", key=f"stake_manual_{nome}")
            if st.form_submit_button("💾 Salvar stakes manuais", type="secondary"):
                novos = {n: float(st.session_state.get(f"stake_manual_{n}", 0.0)) for n in nomes}
                if dl.salvar_config({**cfg, "stakes_manuais": novos}):
                    flash("stakes", "Stakes manuais salvas no Google Sheets")
                    st.rerun(scope="fragment")
                st.warning("Não foi possível salvar.")

    total_fin = df_s["Financeiro (R$)"].sum()
    st.markdown("---")
    st.subheader("💰 Estimativa Financeira Mensal")
    c1, c2, c3 = st.columns(3)
    c1.metric("Financeiro Total (R$)", f"R$ {total_fin:,.2f}")
    c2.metric("Sobre a Banca (%)", f"{(total_fin / banca * 100.0 if banca > 0 else 0):.2f}%")
    c3.metric("Banca Atual", f"R$ {banca:,.2f}")
    st.markdown(f"✅ **{int((df_s['EV'] > 0).sum())} de {len(df_s)}** métodos com EV positivo "
                f"| Stake com base em **{tipo_red}** | DD: **{dd_pct:.1f}%** | Banca: **R$ {banca:,.2f}**")
    with st.expander("ℹ️ Como os cálculos são feitos"):
        st.markdown("""
- **EV** = WR × Green Médio − (1 − WR) × Red Médio
- **Perdas consecutivas (N)** = menor N tal que `1 − (1 − (1−WR)^N)^(Apostas/mês × 12) ≤ 5%` (horizonte de 1 ano)
- **Stake** = (DD Máximo × Banca) ÷ N ÷ Red escolhido
- **Stake %** = Stake ÷ Banca × 100
""")


# ============================================================
# ABA 4 — CRITÉRIOS
# ============================================================
def aba_criterios():
    st.header("📋 Critérios dos Métodos")
    st.caption("Referência rápida dos critérios de seleção de cada método.")
    st.markdown("---")
    st.markdown("**🗓️ Datas de Início dos Métodos**")
    for col, (nome, data) in zip(st.columns(4), [("🦓 Lay Zebra", "12/03/2026"), ("📋 Masterlist", "29/06/2026"),
                                                 ("✅ Valida", "26/06/2026"), ("🎯 Lay CS", "06/03/2026")]):
        col.metric(nome, data)


# ============================================================
# ABA 5 — JOGOS DO DIA
# ============================================================
NUM_COLS = ["Over 2.5", "Gols Sofridos", "Gols Marcados", "Total de Gols", "GP", "GP Visitante",
            "Total de Gols Visitante", "Gols Marcados Visitante", "Gols Sofridos Visitante", "Over 2.5 Visitante"]


@st.cache_data(show_spinner=False, max_entries=4)
def preparar_jogos(lista: pd.DataFrame, base: pd.DataFrame, depara: dict) -> pd.DataFrame:
    """Lista de jogos -> tabela da aba, enriquecida com classificação e odds (base extra).
    Cacheada: só recalcula quando a lista, a base extra ou o de-para mudam."""
    d = pd.DataFrame({
        "_data_iso": pd.to_datetime(lista["data"]).dt.strftime("%Y-%m-%d"),
        "Data": pd.to_datetime(lista["data"]).dt.strftime("%d/%m/%Y"),
        "País": lista["pais"].astype(str),
        "Over 2.5": lista["casa_over25"] * 100,
        "Gols Sofridos": lista["casa_ga"], "Gols Marcados": lista["casa_gf"],
        "Total de Gols": lista["casa_tg"], "GP": lista["casa_gp"],
        "Time Mandante": lista["mandante"].astype(str), "Horário": lista["hora"].astype(str),
        "Time Visitante": lista["visitante"].astype(str),
        "GP Visitante": lista["fora_gp"], "Total de Gols Visitante": lista["fora_tg"],
        "Gols Marcados Visitante": lista["fora_gf"], "Gols Sofridos Visitante": lista["fora_ga"],
        "Over 2.5 Visitante": lista["fora_over25"] * 100,
    })
    for c in NUM_COLS:
        d[c] = pd.to_numeric(d[c], errors="coerce").astype(float)

    d["Classif Casa"], d["Classif Fora"], d["Odd Casa"], d["Odd Fora"] = 0, 0, 0.0, 0.0
    if base is not None and not base.empty:
        casa_n = d["Time Mandante"].map(_normalizar_nome).map(lambda x: depara.get(x, x))
        fora_n = d["Time Visitante"].map(_normalizar_nome).map(lambda x: depara.get(x, x))

        # Classificação: preferência (time, data); senão, último valor visto do time
        n = len(base)
        longo = pd.concat([
            pd.DataFrame({"time": base["Casa_N"], "data": base["Data_N"], "cl": base["Classif Casa"], "o": np.arange(n) * 2}),
            pd.DataFrame({"time": base["Fora_N"], "data": base["Data_N"], "cl": base["Classif Fora"], "o": np.arange(n) * 2 + 1}),
        ]).sort_values("o")
        longo = longo[longo["time"].astype(str) != ""]
        por_time = longo.groupby("time")["cl"].last().to_dict()
        por_data = longo.dropna(subset=["data"]).groupby(["time", "data"])["cl"].last().to_dict()

        def classif(times, datas):
            return [por_data.get((t, dd), por_time.get(t, 0)) for t, dd in zip(times, datas)]

        d["Classif Casa"] = classif(casa_n, d["_data_iso"])
        d["Classif Fora"] = classif(fora_n, d["_data_iso"])
        odds = base.drop_duplicates(["Casa_N", "Fora_N"], keep="first").set_index(["Casa_N", "Fora_N"])
        odds = odds[["Odd Casa", "Odd Fora"]].to_dict("index")
        par = [odds.get(k, {"Odd Casa": 0.0, "Odd Fora": 0.0}) for k in zip(casa_n, fora_n)]
        d["Odd Casa"] = [p["Odd Casa"] for p in par]
        d["Odd Fora"] = [p["Odd Fora"] for p in par]
    return d.sort_values(["_data_iso", "Horário"], na_position="last").reset_index(drop=True)


def _azarao(d, lado):
    """Odd e classificação do `lado` maiores que as do outro (0 = sem dado, libera)."""
    a, b = ("Casa", "Fora") if lado == "casa" else ("Fora", "Casa")
    odd = (d[f"Odd {a}"] == 0) | (d[f"Odd {b}"] == 0) | (d[f"Odd {a}"] > d[f"Odd {b}"])
    cl = (d[f"Classif {a}"] == 0) | (d[f"Classif {b}"] == 0) | (d[f"Classif {a}"] > d[f"Classif {b}"])
    return odd & cl


def _overs(d):
    return ((d["Over 2.5"] >= 40) & (d["Over 2.5 Visitante"] >= 40) &
            ((d["Over 2.5"] + d["Over 2.5 Visitante"]) / 2 >= 50))


def _totais(d):
    return (d["Total de Gols"] >= 2.8) & (d["Total de Gols Visitante"] >= 2.8)


# (chave, rótulo, ajuda, máscara)
FILTROS_PRESET = [
    ("filtro_lay_0x1", "🦓 Lay 0x1 Zebra",
     "Over 2.5 ≥ 40% (casa e fora), média ≥ 50%, total de gols ≥ 2.8. Odd visitante > odd mandante e classif visitante > mandante (0 libera)",
     lambda d: _overs(d) & _totais(d) & _azarao(d, "fora")),
    ("filtro_lay_1x0", "🦓 Lay 1x0 Zebra",
     "Over 2.5 ≥ 40% (casa e fora), média ≥ 50%, total de gols ≥ 2.8. Odd mandante > odd visitante e classif mandante > visitante (0 libera)",
     lambda d: _overs(d) & _totais(d) & _azarao(d, "casa")),
    ("filtro_lay_fav", "⭐ Lay 0x1 Favorito",
     "Over 2.5 ≥ 40% (casa e fora), média ≥ 50%, gols sofridos casa ≥ 1, gols marcados fora ≥ 1.5. Odd mandante > odd visitante e classif mandante > visitante (0 libera)",
     lambda d: _overs(d) & (d["Gols Sofridos"] >= 1.0) & (d["Gols Marcados Visitante"] >= 1.5) & _azarao(d, "casa")),
    ("filtro_lay_zebra_novo", "🦓 Lay Zebra (Visitante)",
     "Over 2.5 ≥ 40% (casa e fora), média ≥ 50%, gols marcados casa ≥ 1.5, gols sofridos casa ≤ 1.3, gols marcados fora ≤ 1.4, gols sofridos fora ≥ 1.4, gols marcados fora ≤ gols sofridos fora. Odd visitante > odd mandante e classif visitante > mandante (0 libera)",
     lambda d: (_overs(d) & (d["Gols Marcados"] >= 1.5) & (d["Gols Sofridos"] <= 1.3)
                & (d["Gols Marcados Visitante"] <= 1.4) & (d["Gols Sofridos Visitante"] >= 1.4)
                & (d["Gols Marcados Visitante"] <= d["Gols Sofridos Visitante"]) & _azarao(d, "fora"))),
    ("filtro_lay_zebra_mandante", "🦓 Lay Zebra (Mandante)",
     "Over 2.5 ≥ 40% (casa e fora), média ≥ 50%, gols marcados fora ≥ 1.5, gols sofridos fora ≤ 1.3, gols marcados casa ≤ 1.4, gols sofridos casa ≥ 1.4, gols marcados casa ≤ gols sofridos casa. Odd mandante > odd visitante e classif mandante > visitante (0 libera)",
     lambda d: (_overs(d) & (d["Gols Marcados Visitante"] >= 1.5) & (d["Gols Sofridos Visitante"] <= 1.3)
                & (d["Gols Marcados"] <= 1.4) & (d["Gols Sofridos"] >= 1.4)
                & (d["Gols Marcados"] <= d["Gols Sofridos"]) & _azarao(d, "casa"))),
]

# (rótulo, coluna, chave, passo, formato)
FILTROS_FAIXA = {
    "casa": [("Over 2.5", "Over 2.5", "o_m_pct", 1.0, "%.0f"), ("Gols Marcados", "Gols Marcados", "gf_m", 0.01, "%.2f"),
             ("Gols Sofridos", "Gols Sofridos", "ga_m", 0.01, "%.2f"), ("Total de Gols", "Total de Gols", "ttg_m", 0.01, "%.2f"),
             ("Classificação", "Classif Casa", "class_m", 1.0, "%.0f"), ("Odd", "Odd Casa", "odd_m", 0.01, "%.2f")],
    "fora": [("Over 2.5", "Over 2.5 Visitante", "o_v_pct", 1.0, "%.0f"), ("Gols Marcados", "Gols Marcados Visitante", "gf_v", 0.01, "%.2f"),
             ("Gols Sofridos", "Gols Sofridos Visitante", "ga_v", 0.01, "%.2f"), ("Total de Gols", "Total de Gols Visitante", "ttg_v", 0.01, "%.2f"),
             ("Classificação", "Classif Fora", "class_v", 1.0, "%.0f"), ("Odd", "Odd Fora", "odd_v", 0.01, "%.2f")],
}


def _atualizar_lista():
    from utils.soccerstats import SoccerStatsErro, atualizar_planilha
    with st.status("Buscando jogos no SoccerSTATS...", expanded=True) as status:
        try:
            r = atualizar_planilha(dl.LISTA_JOGOS_PATH, log=st.write)
        except SoccerStatsErro as e:
            status.update(label="Falha ao atualizar", state="error")
            st.error(str(e))
            return
        status.update(label="Lista atualizada", state="complete")
    pulados = f" · {r['pulados']} dia(s) já atualizados nas últimas 6h foram pulados" if r["pulados"] else ""
    flash("jogos", f"✅ Lista atualizada: {r['novos']} jogos novos, {r['atualizados']} atualizados, "
          f"{r['removidos']} antigos removidos ({r['total']} no total){pulados}.")
    st.rerun()


@st.fragment
def aba_jogos():
    try:
        _corpo_jogos()
    except Exception as e:
        st.error(f"Erro ao carregar a lista de jogos: {e}")


def _corpo_jogos():
    c_tit, c_btn = st.columns([5, 1], vertical_alignment="center")
    c_tit.header("⚽ Jogos do Dia")
    if c_btn.button("🔄 Atualizar jogos", key="btn_atualiza_lista", width="stretch",
                    help="Busca os jogos de hoje + 4 dias no SoccerSTATS e atualiza a lista_jogos.xlsx"):
        _atualizar_lista()
    mostrar_flash("jogos")

    lista = dl.load_lista_jogos()
    if lista.empty:
        st.info("Lista de jogos vazia (ou no formato antigo). Clique em **🔄 Atualizar jogos**.")
        return
    atualizado = lista["atualizado_em"].dropna()
    st.caption("Jogos do mundo todo com filtros por métricas de mandante e visitante · "
               f"lista atualizada em {atualizado.max() if len(atualizado) else '—'}")
    base_extra = dl.load_base_extra()
    dados = preparar_jogos(lista, base_extra, dl.load_depara())
    if not base_extra.empty:
        n_cl = ((dados["Classif Casa"] != 0) | (dados["Classif Fora"] != 0)).sum()
        n_od = ((dados["Odd Casa"] != 0) | (dados["Odd Fora"] != 0)).sum()
        st.caption(f"📊 {n_cl}/{len(dados)} com classificação · {n_od}/{len(dados)} com odds")

    # Reset dos filtros (pedido na execução anterior)
    st.session_state.setdefault("_filtro_reset_n", 0)
    if st.session_state.pop("_reset_filtros", False):
        for k in ([f[0] for f in FILTROS_PRESET] + [f"so_marcados_{mt}" for mt in METODOS_EDITOR]
                  + ["filtro_data", "filtro_paises", "filtra_gp"]):
            st.session_state.pop(k, None)

    # ---- Métodos já salvos (para os checkboxes e para o filtro "só marcados") ----
    salvos = {chave_jogo(r.get("data"), r.get("pais"), r.get("mandante"), r.get("visitante")):
              {p.strip() for p in str(r.get("metodos", "")).split(";") if p.strip()}
              for r in dl.load_metodos_jogos()}
    dados = dados.assign(_chave=[chave_jogo(*v) for v in zip(
        dados["Data"], dados["País"], dados["Time Mandante"], dados["Time Visitante"])])

    st.markdown("### ⚡ Filtros rápidos")
    presets_visiveis = [f for f in FILTROS_PRESET if f[0] not in PRESETS_OCULTOS]
    cols = st.columns(len(presets_visiveis) + len(METODOS_EDITOR))
    presets = {k: col.checkbox(rot, key=k, help=h) for col, (k, rot, h, _) in zip(cols, presets_visiveis)}
    so_marcados = [mt for col, mt in zip(cols[len(presets_visiveis):], METODOS_EDITOR)
                   if col.checkbox(f"✅ Só jogos com {mt} marcado", key=f"so_marcados_{mt}",
                                   help=f"Mostra apenas os jogos já salvos com {mt} na planilha")]

    with st.expander("🎛️ Filtros por métricas (mín e máx)", expanded=False):
        c1, c2, c3 = st.columns(3)
        datas = sorted(dados["Data"].dropna().unique(), key=lambda s: pd.to_datetime(s, format="%d/%m/%Y"))
        data_filtro = c1.selectbox("📅 Filtrar por data", options=["Todas"] + datas, key="filtro_data")
        paises_filtro = c2.multiselect("🌍 Filtrar por países", options=sorted(dados["País"].dropna().unique()),
                                       key="filtro_paises", help="Selecione um ou mais países. Vazio = mostra todos.")
        filtra_gp = c3.checkbox("⚽ Remover times com menos de 3 jogos (GP)", key="filtra_gp",
                                help="Remove jogos onde o mandante OU o visitante jogaram menos de 3 partidas")
        rn = st.session_state["_filtro_reset_n"]
        faixas = {}
        for lado, titulo in (("casa", "**🏠 Mandante**"), ("fora", "**✈️ Visitante**")):
            st.markdown(titulo)
            for col, (rot, coluna, chave, passo, fmt) in zip(st.columns(6), FILTROS_FAIXA[lado]):
                s = dados[coluna].dropna()
                lo, hi = (float(s.min()), float(s.max())) if len(s) else (0.0, 10.0)
                with col:
                    faixas[coluna] = (
                        st.number_input(f"{rot} mín", min_value=lo, max_value=hi, value=lo, step=passo,
                                        format=fmt, key=f"{chave}_{rn}_min"),
                        st.number_input(f"{rot} máx", min_value=lo, max_value=hi, value=hi, step=passo,
                                        format=fmt, key=f"{chave}_{rn}_max"),
                    )
        st.markdown("---")
        if st.button("🧹 Limpar todos os filtros", key="limpar_todos_filtros", width="stretch"):
            st.session_state["_filtro_reset_n"] += 1
            st.session_state["_reset_filtros"] = True
            st.rerun(scope="fragment")

    # ---- Aplica filtros (uma máscara só) ----
    m = pd.Series(True, index=dados.index)
    for k, _, _, regra in FILTROS_PRESET:
        if presets.get(k):
            m &= regra(dados)
    for mt in so_marcados:
        m &= dados["_chave"].map(lambda k, mt=mt: mt in salvos.get(k, ()))
    if data_filtro != "Todas":
        m &= dados["Data"] == data_filtro
    if paises_filtro:
        m &= dados["País"].isin(paises_filtro)
    if filtra_gp:
        m &= (dados["GP"] >= 3) & (dados["GP Visitante"] >= 3)
    for coluna, (lo, hi) in faixas.items():      # vazio (NaN) sempre passa
        m &= dados[coluna].isna() | dados[coluna].between(lo, hi)
    dados = dados[m]

    st.caption(f"**{len(dados)} jogos** após os filtros")
    if dados.empty:
        st.warning("Nenhum jogo encontrado com os filtros atuais. Ajuste os filtros para ampliar a busca.")
        return

    chaves = dados["_chave"].tolist()

    ordem = ["Data", "País", "Over 2.5", "Gols Sofridos", "Gols Marcados", "Total de Gols", "GP", "Classif Casa",
             "Odd Casa", "Time Mandante", "Horário", "Time Visitante", "Odd Fora", "Classif Fora", "GP Visitante",
             "Total de Gols Visitante", "Gols Sofridos Visitante", "Gols Marcados Visitante", "Over 2.5 Visitante"]
    editor = dados[ordem].head(MAX_EDITOR).copy()
    for metodo in METODOS_EDITOR:
        editor[metodo] = [metodo in salvos.get(k, set()) for k in chaves[:MAX_EDITOR]]
    # Números como texto (vazio em vez de "None"); GP e Classif ficam numéricos p/ ordenar certo
    for c in ["Over 2.5", "Over 2.5 Visitante"]:
        editor[c] = editor[c].map(lambda v: "" if pd.isna(v) else f"{v:.0f}%")
    for c in ["Gols Sofridos", "Gols Marcados", "Total de Gols", "Total de Gols Visitante",
              "Gols Sofridos Visitante", "Gols Marcados Visitante", "Odd Casa", "Odd Fora"]:
        editor[c] = editor[c].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
    if len(dados) > MAX_EDITOR:
        st.caption(f"⚠️ Mostrando os {MAX_EDITOR} primeiros de {len(dados)} jogos. Use os filtros para reduzir a lista.")

    centro = lambda nome: st.column_config.TextColumn(nome, alignment="center")  # noqa: E731
    numero = lambda nome: st.column_config.NumberColumn(nome, alignment="center")  # noqa: E731
    column_config = {
        "Over 2.5": centro("Over 2.5"), "Gols Marcados": centro("Gols Marcados"),
        "Gols Sofridos": centro("Gols Sofridos"), "Total de Gols": centro("Total de Gols"),
        "Over 2.5 Visitante": centro("Over 2.5 (Fora)"), "Gols Marcados Visitante": centro("Gols Marcados (Fora)"),
        "Gols Sofridos Visitante": centro("Gols Sofridos (Fora)"), "Total de Gols Visitante": centro("Total de Gols (Fora)"),
        "GP": numero("GP"), "GP Visitante": numero("GP (Fora)"),
        "Classif Casa": numero("Classif Casa"), "Classif Fora": numero("Classif Fora"),
        "Odd Casa": centro("Odd Casa"), "Odd Fora": centro("Odd Fora"),
        **{mt: st.column_config.CheckboxColumn(mt, alignment="center") for mt in METODOS_EDITOR},
    }
    st.session_state.setdefault("_editor_n", 0)
    with st.form("form_metodos_indicadores"):
        st.caption("✏️ Marque os métodos direto na tabela. Nada é salvo até clicar em 💾 Salvar seleções.")
        editado = st.data_editor(editor, width="stretch", height=500, hide_index=True,
                                 disabled=[c for c in editor.columns if c not in METODOS_EDITOR],
                                 column_config=column_config, key=f"editor_metodos_{st.session_state['_editor_n']}")
        b1, b2 = st.columns(2)
        salvar = b1.form_submit_button("💾 Salvar seleções", type="primary", width="stretch")
        limpar = b2.form_submit_button("🧹 Limpar métodos", type="secondary", width="stretch")

    def linha(r, metodos=None):
        d = {"data": norm_data(r["Data"]), "pais": str(r["País"]), "mandante": str(r["Time Mandante"]),
             "horario": str(r["Horário"]), "visitante": str(r["Time Visitante"])}
        if metodos is not None:
            d["metodos"] = "; ".join(metodos)
        return d

    if salvar:
        linhas = []
        for r, k in zip(editado.to_dict("records"), chaves):
            marcados = [mt for mt in METODOS_EDITOR if r.get(mt)]
            if marcados or k in salvos:          # desmarcar tudo também grava (limpa a linha)
                linhas.append(linha(r, marcados))
        if not linhas:
            st.info("Nenhum jogo com método marcado.")
        else:
            with st.spinner("Salvando..."):
                resp = dl.salvar_metodos(linhas)
            if resp.get("ok"):
                st.session_state["_editor_n"] += 1
                flash("jogos", f"✅ {resp.get('saved', len(linhas))} jogos salvos com sucesso!")
                st.rerun()                        # app inteiro: a aba Métodos também muda
            st.error(f"Erro ao salvar: {resp}")
    if limpar:
        linhas = [linha(r) for r, k in zip(dados[ordem].to_dict("records"), chaves) if k in salvos]
        if not linhas:
            st.info("Nenhum jogo com registro na planilha para remover.")
        else:
            with st.spinner("Removendo..."):
                resp = dl.deletar_metodos(linhas)
            if resp.get("ok"):
                st.session_state["_editor_n"] += 1
                flash("jogos", f"✅ {resp.get('saved', len(linhas))} jogos removidos da planilha!")
                st.rerun()
            st.error(f"Erro ao limpar: {resp}")


# ============================================================
# ABA 6 — MÉTODOS POR JOGO
# ============================================================
def _fmt_horario(v):
    s = str(v or "").strip()
    if not s or s.lower() == "nan":
        return ""
    if "T" in s:
        return s.split("T")[1][:5]
    if ":" in s:
        return s[:5]
    try:                                   # fração do dia (número do Excel)
        frac = float(s)
        if 0 <= frac < 1:
            minutos = int(round(frac * 24 * 60))
            return f"{minutos // 60:02d}:{minutos % 60:02d}"
    except ValueError:
        pass
    return s


def _adicionar_manual(pendentes):
    """Formulário para cadastrar jogos fora da lista (oculto: MOSTRAR_ADICIONAR_MANUAL)."""
    with st.expander("➕ Adicionar jogo manualmente", expanded=False):
        st.caption("Preencha uma partida por vez e clique em Adicionar. As partidas acumulam até você salvar na planilha.")
        with st.form("form_manual_tab6", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            data_m = c1.date_input("📅 Data", value=None)
            hora_m = c2.time_input("🕐 Horário", value=None)
            pais_m = c3.text_input("🌍 País")
            c4, c5 = st.columns(2)
            mand_m = c4.text_input("🏠 Mandante")
            vis_m = c5.text_input("✈️ Visitante")
            met_m = st.multiselect("🎯 Métodos", options=METODOS_MANUAIS,
                                   help="Selecione um ou mais métodos (os mesmos da tabela Jogos do Dia).")
            b1, b2 = st.columns(2)
            adicionar = b1.form_submit_button("➕ Adicionar à lista", width="stretch")
            salvar = b2.form_submit_button("💾 Salvar na planilha", type="primary", width="stretch")
        if adicionar:
            if not mand_m.strip() or not vis_m.strip():
                st.warning("Preencha ao menos Mandante e Visitante antes de adicionar.")
            else:
                pendentes.append({
                    "data": data_m.strftime("%d/%m/%Y") if data_m else "", "pais": pais_m.strip(),
                    "mandante": mand_m.strip(), "horario": hora_m.strftime("%H:%M") if hora_m else "",
                    "visitante": vis_m.strip(), "metodos": "; ".join(met_m),
                })
                st.success(f"✅ Adicionado: {mand_m.strip()} x {vis_m.strip()}")
        if pendentes:
            st.markdown("**📋 Partidas aguardando salvamento:**")
            for i, p in enumerate(pendentes, 1):
                st.write(f"{i}. {p['data']} {p['horario']} — {p['mandante']} x {p['visitante']} "
                         f"({p['pais']}) — **{p['metodos'] or 'sem métodos'}**")
        if salvar:
            if not pendentes:
                st.info("Nenhuma partida adicionada para salvar.")
            else:
                with st.spinner("Salvando..."):
                    resp = dl.salvar_metodos(pendentes)
                if resp.get("ok"):
                    flash("metodos", f"✅ {len(pendentes)} partida(s) salva(s) na planilha!")
                    st.session_state["manuais_pendentes"] = []
                    st.rerun()
                st.error(f"Erro ao salvar: {resp}")



@st.fragment
def aba_metodos():
    st.subheader("✅ Métodos por Jogo")
    st.caption("Consulta dos métodos salvos por partida. Acessível de qualquer dispositivo.")
    mostrar_flash("metodos")
    pendentes = st.session_state.setdefault("manuais_pendentes", [])

    if MOSTRAR_ADICIONAR_MANUAL:
        _adicionar_manual(pendentes)

    salvos = dl.load_metodos_jogos()
    if not salvos:
        st.info("Nenhum método salvo ainda. Marque os métodos na tabela principal e clique em 💾 Salvar seleções.")
        return

    dfc = pd.DataFrame(salvos).rename(columns={
        "data": "Data", "pais": "País", "mandante": "Time Mandante", "horario": "Horário",
        "visitante": "Time Visitante", "metodos": "Métodos"})
    dfc = dfc[[c for c in ["Data", "Horário", "País", "Time Mandante", "Time Visitante", "Métodos"] if c in dfc.columns]]
    dfc = dfc.fillna("").astype(str)
    if "Data" in dfc.columns:
        dfc["Data"] = dfc["Data"].map(norm_data)
    if "Horário" in dfc.columns:
        dfc["Horário"] = dfc["Horário"].map(_fmt_horario)
    dfc = (dfc.assign(_o=pd.to_datetime(dfc["Data"], format="%Y-%m-%d", errors="coerce"))
           .sort_values(["_o", "Horário"], na_position="last").drop(columns="_o"))

    # Posição na tabela == posição no DataFrame (a exclusão usa essa posição)
    dfc = dfc.reset_index(drop=True)
    dfc["Excluir"] = False

    st.session_state.setdefault("_editor_tab6_n", 0)
    chave_editor = f"editor_metodos_tab6_{st.session_state['_editor_tab6_n']}"
    if st.button("🗑️ Excluir jogos marcados", key="btn_excluir_jogos", width="stretch"):
        estado = st.session_state.get(chave_editor) or {}
        idx = sorted(int(i) for i, mud in estado.get("edited_rows", {}).items() if mud.get("Excluir"))
        linhas = [{"data": r["Data"], "pais": r["País"], "mandante": r["Time Mandante"],
                   "horario": r["Horário"], "visitante": r["Time Visitante"], "metodos": r["Métodos"]}
                  for r in dfc.iloc[[i for i in idx if i < len(dfc)]].to_dict("records")]
        if not linhas:
            st.info("Nenhum jogo marcado para exclusão.")
        else:
            with st.spinner("Excluindo..."):
                resp = dl.deletar_metodos(linhas)
            if resp.get("ok"):
                st.session_state["_editor_tab6_n"] += 1     # editor novo, sem marcações antigas
                flash("metodos", f"🗑️ {len(linhas)} jogo(s) excluído(s) da planilha!")
                st.rerun()
            st.error(f"Erro ao excluir: {resp}")

    st.data_editor(dfc, hide_index=True, width="stretch", height=520,
                   disabled=[c for c in dfc.columns if c != "Excluir"],
                   column_config={"Excluir": st.column_config.CheckboxColumn(
                       "Excluir", help="Marque os jogos a excluir e clique em 🗑️ Excluir jogos marcados", default=False)},
                   key=chave_editor)
    st.caption(f"📋 {len(dfc)} partidas classificadas")


# ============================================================
# MAIN
# ============================================================
with st.spinner("Carregando dados..."):
    df_base = dl.load_data()
    dl.load_paises_elegiveis()   # baixa todas as referências do Sheets em paralelo (1ª vez)

ABAS = [
    ("📊 Dashboard", lambda: aba_dashboard(df_base), True),
    ("🧮 Calculadora", aba_calculadora, MOSTRAR_CALCULADORA),
    ("🎯 Stakes", aba_stakes, True),
    ("📋 Critérios", aba_criterios, MOSTRAR_CRITERIOS),
    ("⚽ Jogos do Dia", aba_jogos, True),
    ("✅ Métodos", aba_metodos, MOSTRAR_ABA_METODOS),
]
ABAS = [(nome, render) for nome, render, visivel in ABAS if visivel]
for aba, (_, render) in zip(st.tabs([nome for nome, _ in ABAS]), ABAS):
    with aba:
        render()
