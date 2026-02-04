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

# ==============================================================================
# 1. FILTROS AVANZADOS (MULTI-SELECT)
# ==============================================================================
with st.container():
    st.subheader("🔍 Filtros de Visualización")
    
    # Fila 1: Año y Malls
    c1, c2 = st.columns(2)
    sel_year = c1.number_input("Año Fiscal", value=2026, step=1)
    
    all_malls = db.query(Mall).all()
    sel_malls = c2.multiselect(
        "Filtrar por Mall (Selecciona uno o varios)", 
        all_malls, 
        format_func=lambda x: x.name,
        placeholder="Todos los Malls"
    )

    # Fila 2: Tipos y Actividades
    c3, c4 = st.columns(2)
    
    all_types = db.query(ActivityType).all()
    sel_types = c3.multiselect(
        "Filtrar por Tipo de Actividad", 
        all_types, 
        format_func=lambda x: x.name,
        placeholder="Todos los Tipos"
    )
    
    # Lógica para filtrar las actividades disponibles en el selector
    # Solo mostramos actividades que coincidan con los Malls y Tipos elegidos arriba
    start_filter = datetime.datetime(sel_year, 1, 1)
    end_filter = datetime.datetime(sel_year, 12, 31, 23, 59, 59)
    
    quotes_q = db.query(Quote).filter(
        Quote.status.in_(["APROBADA", "EJECUTADA", "LIQUIDADA"]),
        Quote.created_at >= start_filter,
        Quote.created_at <= end_filter
    )
    
    # Aplicar filtros previos a la query de opciones
    if sel_malls:
        mall_ids = [m.id for m in sel_malls]
        quotes_q = quotes_q.filter(Quote.mall_id.in_(mall_ids))
        
    if sel_types:
        type_ids = [t.id for t in sel_types]
        quotes_q = quotes_q.filter(Quote.activity_type_id.in_(type_ids))
    
    available_quotes = quotes_q.all()
    
    sel_quotes = c4.multiselect(
        "Filtrar por Actividad Específica", 
        available_quotes, 
        format_func=lambda x: f"{x.activity_name} ({x.mall.name if x.mall else 'Global'})",
        placeholder="Todas las Actividades"
    )

st.divider()

# ==============================================================================
# SECCIÓN 1: RENTABILIDAD Y VENTAS
# ==============================================================================
st.header("💰 Análisis de Rentabilidad (Ventas vs. Costos)")

# Construcción de query de ventas basada en MULTI-SELECT
q_sales = db.query(Quote).filter(
    Quote.status.in_(["APROBADA", "EJECUTADA", "LIQUIDADA"]),
    Quote.created_at >= start_filter,
    Quote.created_at <= end_filter
)

# Filtro Malls
if sel_malls:
    q_sales = q_sales.filter(Quote.mall_id.in_([m.id for m in sel_malls]))

# Filtro Tipos
if sel_types:
    q_sales = q_sales.filter(Quote.activity_type_id.in_([t.id for t in sel_types]))

# Filtro Actividades Específicas
if sel_quotes:
    q_sales = q_sales.filter(Quote.id.in_([q.id for q in sel_quotes]))

sales_data = q_sales.all()

# Cálculos Totales
total_venta = sum([q.final_sale_price_usd if q.final_sale_price_usd else 0 for q in sales_data])
total_costo_cotizado = sum([q.total_cost_usd for q in sales_data])
utilidad = total_venta - total_costo_cotizado
margen_pct = (utilidad / total_venta * 100) if total_venta > 0 else 0.0

# KPIs
k_v1, k_v2, k_v3, k_v4 = st.columns(4)
k_v1.metric("Venta Total (Selección)", f"${total_venta:,.2f}")
k_v2.metric("Costo Total (Base)", f"${total_costo_cotizado:,.2f}")
k_v3.metric("Utilidad $", f"${utilidad:,.2f}", delta_color="normal")
k_v4.metric("Margen %", f"{margen_pct:.1f}%", delta_color="normal")

st.divider()

# ==============================================================================
# SECCIÓN 2: EJECUCIÓN PRESUPUESTARIA
# ==============================================================================
st.header("📉 Ejecución Presupuestaria (OIs vs Gastos Reales)")

rate = get_active_rate(db)

# 1. Obtener Presupuestos (Targets) de OIs Activas
query_ois = db.query(OI).filter(OI.is_active == True)

# Filtrar OIs por Malls seleccionados
if sel_malls:
    query_ois = query_ois.filter(OI.mall_id.in_([m.id for m in sel_malls]))

ois = query_ois.all()
budget_map = {oi.oi_code: oi.annual_budget_usd for oi in ois}
oi_names = {oi.oi_code: oi.oi_name for oi in ois}
oi_malls = {oi.oi_code: oi.mall.name if oi.mall else "N/A" for oi in ois} # Mapa para saber el mall

# 2. Obtener Gastos Reales con Filtros Multi-Select
query_exp = db.query(Expense).filter(Expense.year == sel_year)

if sel_malls:
    query_exp = query_exp.filter(Expense.mall_id.in_([m.id for m in sel_malls]))

if sel_types:
    query_exp = query_exp.join(Quote).filter(Quote.activity_type_id.in_([t.id for t in sel_types]))

if sel_quotes:
    query_exp = query_exp.filter(Expense.quote_id.in_([q.id for q in sel_quotes]))

expenses = query_exp.all()

# --- PROCESAMIENTO DE DATOS ---
oi_data = {}

# Si NO hay filtro de actividad específica, cargamos todas las OIs del Mall para ver lo disponible vs gastado
if not sel_quotes:
    for code, budget in budget_map.items():
        oi_data[code] = {
            'OI': code,
            'Nombre': oi_names.get(code, ""),
            'Mall': oi_malls.get(code, ""), # Agregamos el Mall
            'budget_usd': budget,
            'real_usd': 0.0,
            'real_gtq': 0.0
        }

# Sumar Gastos Reales
for e in expenses:
    code = e.oi.oi_code
    
    # Si la OI no estaba (porque filtramos por actividad específica y solo esa debe salir)
    if code not in oi_data:
        oi_data[code] = {
            'OI': code, 
            'Nombre': e.oi.oi_name, 
            'Mall': e.mall.name if e.mall else "N/A", # Agregamos el Mall
            'budget_usd': e.oi.annual_budget_usd, 
            'real_usd': 0.0, 
            'real_gtq': 0.0
        }
    
    oi_data[code]['real_usd'] += e.amount_usd
    oi_data[code]['real_gtq'] += e.amount_gtq

if not oi_data:
    st.info("No hay datos para mostrar con los filtros actuales.")
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
    
    # Preparamos datos: OI + Mall para la etiqueta del eje X si se quiere
    df['Etiqueta'] = df['OI'] + " (" + df['Mall'] + ")"
    
    df_chart = df[['Etiqueta', 'budget_usd', 'real_usd', 'Mall']].melt(['Etiqueta', 'Mall'], var_name='Tipo', value_name='Monto USD')
    
    domain = ['budget_usd', 'real_usd']
    range_ = ['#e0e0e0', '#ff4b4b'] 

    chart = alt.Chart(df_chart).mark_bar().encode(
        x=alt.X('Etiqueta', sort=None, title="OI (Mall)"),
        y='Monto USD',
        color=alt.Color('Tipo', scale=alt.Scale(domain=domain, range=range_), legend=alt.Legend(title="Indicador")),
        tooltip=['Etiqueta', 'Mall', 'Tipo', alt.Tooltip('Monto USD', format="$,.2f")]
    ).properties(height=400)
    
    st.altair_chart(chart, use_container_width=True)

    # TABLA DETALLE (CON COLUMNA MALL)
    with st.expander("Ver Detalle Financiero por OI", expanded=True):
        st.dataframe(
            df[['Mall', 'OI', 'Nombre', 'budget_usd', 'real_usd', '% Ejecución', 'Disponible USD']].style.format({
                'budget_usd': '${:,.2f}',
                'real_usd': '${:,.2f}',
                '% Ejecución': '{:.1f}%',
                'Disponible USD': '${:,.2f}'
            }),
            use_container_width=True
        )