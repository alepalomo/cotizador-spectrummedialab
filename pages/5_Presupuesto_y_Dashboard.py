import streamlit as st
import pandas as pd
import altair as alt
import datetime
from database import get_db
from models import Expense, OI, Mall, ActivityType, Quote
from auth import require_role
from services import get_active_rate

require_role(["ADMIN", "AUTORIZADO", "VENDEDOR"])
db = next(get_db())

st.title("📊 Dashboard Financiero")

# --- FILTROS GLOBALES ---
with st.container():
    # Fila 1: Año y Mall
    c1, c2 = st.columns(2)
    sel_year = c1.number_input("Año Fiscal", value=2026, step=1)
    
    malls = db.query(Mall).all()
    sel_mall = c2.selectbox("Filtrar por Mall", [None] + malls, format_func=lambda x: x.name if x else "Todos los Malls")

    # Fila 2: Filtros de Actividad
    c3, c4 = st.columns(2)
    
    # Filtro Tipo
    types = db.query(ActivityType).all()
    sel_type = c3.selectbox("Filtrar por Tipo de Actividad", [None] + types, format_func=lambda x: x.name if x else "Todos los Tipos")
    
    # Filtro Actividad Específica (Quote)
    # Cargamos solo las aprobadas/ejecutadas de ese año para el filtro
    start_filter = datetime.datetime(sel_year, 1, 1)
    end_filter = datetime.datetime(sel_year, 12, 31, 23, 59, 59)
    
    quotes_q = db.query(Quote).filter(
        Quote.status.in_(["APROBADA", "EJECUTADA", "LIQUIDADA"]),
        Quote.created_at >= start_filter,
        Quote.created_at <= end_filter
    )
    
    if sel_mall:
        quotes_q = quotes_q.filter(Quote.mall_id == sel_mall.id)
    if sel_type:
        quotes_q = quotes_q.filter(Quote.activity_type_id == sel_type.id)
    
    available_quotes = quotes_q.all()
    sel_quote = c4.selectbox("Filtrar por Actividad Específica", [None] + available_quotes, format_func=lambda x: f"{x.activity_name}" if x else "Todas las Actividades")

st.divider()

# ==============================================================================
# SECCIÓN 1: RENTABILIDAD Y VENTAS (NUEVO)
# ==============================================================================
st.header("💰 Análisis de Rentabilidad (Ventas vs. Costos)")

# 1. Consultar Cotizaciones para Ventas
# Usamos los mismos filtros para ser consistentes
q_sales = db.query(Quote).filter(
    Quote.status.in_(["APROBADA", "EJECUTADA", "LIQUIDADA"]),
    Quote.created_at >= start_filter,
    Quote.created_at <= end_filter
)

if sel_mall: q_sales = q_sales.filter(Quote.mall_id == sel_mall.id)
if sel_type: q_sales = q_sales.filter(Quote.activity_type_id == sel_type.id)
if sel_quote: q_sales = q_sales.filter(Quote.id == sel_quote.id)

sales_data = q_sales.all()

# 2. Calcular Totales
total_venta = sum([q.final_sale_price_usd if q.final_sale_price_usd else 0 for q in sales_data])
total_costo_cotizado = sum([q.total_cost_usd for q in sales_data])
utilidad = total_venta - total_costo_cotizado
margen_pct = (utilidad / total_venta * 100) if total_venta > 0 else 0.0

# 3. Mostrar KPIs
k_v1, k_v2, k_v3, k_v4 = st.columns(4)
k_v1.metric("Venta Total (Aprobada)", f"${total_venta:,.2f}")
k_v2.metric("Costo Total (Base)", f"${total_costo_cotizado:,.2f}")
k_v3.metric("Utilidad $", f"${utilidad:,.2f}", delta_color="normal")
k_v4.metric("Margen %", f"{margen_pct:.1f}%", delta_color="normal")

st.divider()

# ==============================================================================
# SECCIÓN 2: EJECUCIÓN PRESUPUESTARIA (PRESUPUESTO OI vs GASTO REAL)
# ==============================================================================
st.header("📉 Ejecución Presupuestaria (OIs vs Gastos Reales)")

rate = get_active_rate(db)

# 1. OBTENER PRESUPUESTOS (TARGETS)
query_ois = db.query(OI).filter(OI.is_active == True)
if sel_mall:
    query_ois = query_ois.filter(OI.mall_id == sel_mall.id)
ois = query_ois.all()

budget_map = {oi.oi_code: oi.annual_budget_usd for oi in ois}
oi_names = {oi.oi_code: oi.oi_name for oi in ois}

# 2. OBTENER GASTOS (REALES) DEL AÑO
query_exp = db.query(Expense).filter(Expense.year == sel_year)

if sel_mall:
    query_exp = query_exp.filter(Expense.mall_id == sel_mall.id)
if sel_type:
    query_exp = query_exp.join(Quote).filter(Quote.activity_type_id == sel_type.id)
if sel_quote:
    query_exp = query_exp.filter(Expense.quote_id == sel_quote.id)

expenses = query_exp.all()

# --- PROCESAMIENTO ---
oi_data = {}

# Si no filtramos por actividad específica, cargamos todas las OIs del Mall para ver el panorama completo
if not sel_quote:
    for code, budget in budget_map.items():
        oi_data[code] = {
            'OI': code,
            'Nombre': oi_names.get(code, ""),
            'budget_usd': budget,
            'real_usd': 0.0,
            'real_gtq': 0.0
        }

# Sumar Gastos Reales
for e in expenses:
    code = e.oi.oi_code
    if code not in oi_data:
        oi_data[code] = {
            'OI': code, 
            'Nombre': e.oi.oi_name, 
            'budget_usd': e.oi.annual_budget_usd, 
            'real_usd': 0.0, 
            'real_gtq': 0.0
        }
    oi_data[code]['real_usd'] += e.amount_usd
    oi_data[code]['real_gtq'] += e.amount_gtq

if not oi_data:
    st.info("No hay datos presupuestarios o gastos para mostrar en esta sección.")
else:
    df = pd.DataFrame(list(oi_data.values()))
    
    # Cálculos
    df['% Ejecución'] = (df['real_usd'] / df['budget_usd']).fillna(0) * 100
    df['Disponible USD'] = df['budget_usd'] - df['real_usd']

    total_budget = df['budget_usd'].sum()
    total_real = df['real_usd'].sum()
    pct_total = (total_real / total_budget * 100) if total_budget > 0 else 0
    
    # KPIs Ejecución
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Presupuesto Anual (OI)", f"${total_budget:,.0f}")
    k2.metric("Gasto Real (Ejecutado)", f"${total_real:,.0f}")
    k3.metric("% Ejecución Anual", f"{pct_total:.1f}%")
    k4.metric("Disponible Anual", f"${(total_budget - total_real):,.0f}")
    
    st.progress(min(pct_total / 100, 1.0))

    # GRÁFICA COMPARATIVA
    st.subheader("Comparativa por Cuenta (OI)")
    df_chart = df[['OI', 'budget_usd', 'real_usd']].melt('OI', var_name='Tipo', value_name='Monto USD')
    
    domain = ['budget_usd', 'real_usd']
    range_ = ['#e0e0e0', '#ff4b4b'] 

    chart = alt.Chart(df_chart).mark_bar().encode(
        x=alt.X('OI', sort=None),
        y='Monto USD',
        color=alt.Color('Tipo', scale=alt.Scale(domain=domain, range=range_), legend=alt.Legend(title="Indicador")),
        tooltip=['OI', 'Tipo', alt.Tooltip('Monto USD', format="$,.2f")]
    ).properties(height=350)
    
    st.altair_chart(chart, use_container_width=True)

    # TABLA DETALLE
    with st.expander("Ver Detalle Financiero por OI"):
        st.dataframe(
            df[['OI', 'Nombre', 'budget_usd', 'real_usd', '% Ejecución', 'Disponible USD']].style.format({
                'budget_usd': '${:,.2f}',
                'real_usd': '${:,.2f}',
                '% Ejecución': '{:.1f}%',
                'Disponible USD': '${:,.2f}'
            }),
            use_container_width=True
        )