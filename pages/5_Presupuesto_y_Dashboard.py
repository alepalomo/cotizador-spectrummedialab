import streamlit as st
import pandas as pd
import altair as alt
from database import get_db
from models import Expense, OI, Mall, ActivityType, Quote
from auth import require_role
from services import get_active_rate
from sqlalchemy import func

require_role(["ADMIN", "AUTORIZADO", "VENDEDOR"])
db = next(get_db())

st.title("📊 Dashboard de Ejecución Anual")

# --- FILTROS GLOBALES ---
with st.container():
    # Fila 1: Año y Mall
    c1, c2 = st.columns(2)
    sel_year = c1.number_input("Año Fiscal", value=2025, step=1)
    
    malls = db.query(Mall).all()
    sel_mall = c2.selectbox("Filtrar por Mall", [None] + malls, format_func=lambda x: x.name if x else "Todos los Malls")

    # Fila 2: Filtros de Actividad (NUEVOS)
    c3, c4 = st.columns(2)
    
    # Filtro Tipo
    types = db.query(ActivityType).all()
    sel_type = c3.selectbox("Filtrar por Tipo de Actividad", [None] + types, format_func=lambda x: x.name if x else "Todos los Tipos")
    
    # Filtro Actividad Específica (Quote)
    # Cargamos solo las que tengan gastos o estén aprobadas para no saturar la lista
    quotes_q = db.query(Quote).filter(Quote.status.in_(["APROBADA", "EJECUTADA"]))
    if sel_mall:
        quotes_q = quotes_q.filter(Quote.mall_id == sel_mall.id)
    if sel_type:
        quotes_q = quotes_q.filter(Quote.activity_type_id == sel_type.id)
    
    available_quotes = quotes_q.all()
    sel_quote = c4.selectbox("Filtrar por Actividad Específica", [None] + available_quotes, format_func=lambda x: f"{x.activity_name}" if x else "Todas las Actividades")

# --- LÓGICA DE DATOS ---
rate = get_active_rate(db)

# 1. OBTENER PRESUPUESTOS (TARGETS)
# Usamos el Presupuesto Anual de la OI
query_ois = db.query(OI).filter(OI.is_active == True)
if sel_mall:
    query_ois = query_ois.filter(OI.mall_id == sel_mall.id)
ois = query_ois.all()

# Mapa de presupuestos por OI {oi_code: annual_budget}
budget_map = {oi.oi_code: oi.annual_budget_usd for oi in ois}
oi_names = {oi.oi_code: oi.oi_name for oi in ois}

# 2. OBTENER GASTOS (REALES) DEL AÑO COMPLETO
query_exp = db.query(Expense).filter(Expense.year == sel_year)

# Aplicar filtros a los gastos
if sel_mall:
    query_exp = query_exp.filter(Expense.mall_id == sel_mall.id)

if sel_type:
    # Join con Quote y ActivityType para filtrar por tipo
    query_exp = query_exp.join(Quote).filter(Quote.activity_type_id == sel_type.id)

if sel_quote:
    # Filtrar por una cotización específica
    query_exp = query_exp.filter(Expense.quote_id == sel_quote.id)

expenses = query_exp.all()

# --- PROCESAMIENTO ---
oi_data = {}

# Inicializar con todas las OIs (para que aparezcan aunque no tengan gastos)
# Si seleccionamos una actividad específica, tal vez solo queremos ver la OI de esa actividad, 
# pero mantener el contexto del Mall es útil.
if not sel_quote:
    for code, budget in budget_map.items():
        oi_data[code] = {
            'OI': code,
            'Nombre': oi_names.get(code, ""),
            'budget_usd': budget, # Presupuesto ANUAL completo de la cuenta
            'real_usd': 0.0,
            'real_gtq': 0.0
        }

# Sumar Gastos
for e in expenses:
    code = e.oi.oi_code
    if code not in oi_data:
        # Caso: Gasto en una OI que no estaba en el mapa inicial (raro, pero posible si cambiaron filtro)
        oi_data[code] = {
            'OI': code, 
            'Nombre': e.oi.oi_name, 
            'budget_usd': e.oi.annual_budget_usd, 
            'real_usd': 0.0, 
            'real_gtq': 0.0
        }
    
    oi_data[code]['real_usd'] += e.amount_usd
    oi_data[code]['real_gtq'] += e.amount_gtq

# Convertir a DataFrame
if not oi_data:
    st.warning("No hay datos para los filtros seleccionados.")
else:
    df = pd.DataFrame(list(oi_data.values()))
    
    # Cálculos
    df['% Ejecución'] = (df['real_usd'] / df['budget_usd']).fillna(0) * 100
    df['Disponible USD'] = df['budget_usd'] - df['real_usd']

    # --- KPI SECTION ---
    total_budget = df['budget_usd'].sum()
    total_real = df['real_usd'].sum()
    pct_total = (total_real / total_budget * 100) if total_budget > 0 else 0
    
    st.divider()
    
    # Título dinámico según filtros
    if sel_quote:
        st.info(f"🔎 Analizando Actividad: **{sel_quote.activity_name}**")
        # Si es una actividad específica, comparamos contra SU cotización, no contra toda la OI
        k1, k2, k3 = st.columns(3)
        k1.metric("Cotizado (Presupuesto)", f"${sel_quote.total_cost_usd:,.2f}")
        k2.metric("Gasto Real", f"${total_real:,.2f}")
        diff = sel_quote.total_cost_usd - total_real
        k3.metric("Diferencia", f"${diff:,.2f}", delta_color="normal" if diff >= 0 else "inverse")
        
    else:
        # Vista General (OI Annual)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Presupuesto Anual (OI)", f"${total_budget:,.0f}")
        k2.metric("Gasto Real (Filtrado)", f"${total_real:,.0f}")
        k3.metric("% Ejecución Anual", f"{pct_total:.1f}%")
        k4.metric("Disponible Anual", f"${(total_budget - total_real):,.0f}")
        
        st.progress(min(pct_total / 100, 1.0))

    # --- GRÁFICAS ---
    st.subheader("Comparativa por Cuenta (OI)")
    
    # Preparamos datos para Altair (Formato Largo)
    df_chart = df[['OI', 'budget_usd', 'real_usd']].melt('OI', var_name='Tipo', value_name='Monto USD')
    
    # Diccionario de colores para la gráfica
    domain = ['budget_usd', 'real_usd']
    range_ = ['#e0e0e0', '#ff4b4b'] # Gris para presupuesto, Rojo para real

    chart = alt.Chart(df_chart).mark_bar().encode(
        x=alt.X('OI', sort=None),
        y='Monto USD',
        color=alt.Color('Tipo', scale=alt.Scale(domain=domain, range=range_), legend=alt.Legend(title="Indicador")),
        tooltip=['OI', 'Tipo', alt.Tooltip('Monto USD', format="$,.2f")]
    ).properties(height=350)
    
    st.altair_chart(chart, use_container_width=True)

    # --- TABLA DETALLADA ---
    st.subheader("Detalle Financiero")
    
    st.dataframe(
        df[['OI', 'Nombre', 'budget_usd', 'real_usd', '% Ejecución', 'Disponible USD']].style.format({
            'budget_usd': '${:,.2f}',
            'real_usd': '${:,.2f}',
            '% Ejecución': '{:.1f}%',
            'Disponible USD': '${:,.2f}'
        }),
        use_container_width=True
    )