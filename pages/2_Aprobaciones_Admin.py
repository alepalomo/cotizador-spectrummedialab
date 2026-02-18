import streamlit as st
import pandas as pd
from database import get_db
from models import Quote, User, QuoteLine, Insumo
from auth import require_role
from services import calculate_quote_totals

require_role(["ADMIN", "AUTORIZADO"])
db = next(get_db())

st.title("Panel de Control de Actividades")

# 3 Fases del Flujo
tab_pend, tab_act, tab_liq = st.tabs([
    "⏳ 1. Pendientes de Aprobación", 
    "🚀 2. Activas (En Ejecución)", 
    "🏁 3. Ejecutadas & Liquidadas"
])

# --- TAB 1: APROBACIONES (FLUJO ACTUAL) ---
with tab_pend:
    st.info("Aquí administras las cotizaciones nuevas y defines el PRECIO FINAL DE VENTA.")
    
    # Traemos las pendientes
    pending_quotes = db.query(Quote).filter(Quote.status == "ENVIADA").all()
    
    if not pending_quotes:
        st.success("✅ Todo al día. No hay aprobaciones pendientes.")
    else:
        for q in pending_quotes:
            # 1. Obtener nombre del usuario creador
            user_creator = db.query(User).filter(User.id == q.created_by).first()
            creator_name = user_creator.username if user_creator else "Usuario Desconocido"
            
            # Encabezado visual
            with st.expander(f"📌 {q.activity_name} | Por: {creator_name} | Total: ${q.total_cost_usd:,.2f}"):
                
                # --- A. DETALLES GENERALES ---
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**Actividad:**\n{q.activity_name}")
                c2.markdown(f"**Solicita:**\n{creator_name}")
                c3.markdown(f"**Fecha:**\n{q.created_at.strftime('%d/%m/%Y')}")
                st.write(f"**Notas:** {q.notes}")
                st.divider()

                # --- B. LISTA DE ELEMENTOS ---
                st.subheader("📦 Elementos Contemplados")
                lines = db.query(QuoteLine).filter(QuoteLine.quote_id == q.id).all()
                
                if lines:
                    items_data = []
                    for line in lines:
                        insumo_nombre = line.insumo.name if line.insumo else "Insumo Borrado"
                        items_data.append({
                            "Insumo": insumo_nombre,
                            "Personas/Cant": line.qty_personas,
                            "Unidades/Días": line.units_value,
                            "Costo Línea (Q)": f"Q{line.line_cost_gtq:,.2f}",
                            "Costo Línea ($)": f"${line.line_cost_usd:,.2f}"
                        })
                    st.dataframe(pd.DataFrame(items_data), use_container_width=True)
                else:
                    st.warning("⚠️ Cotización sin líneas.")

                # --- C. AÑADIR ELEMENTOS EXTRA ---
                with st.expander("➕ Añadir Elemento Extra (Sin editar)", expanded=False):
                    col_add1, col_add2, col_add3, col_add4 = st.columns([3, 1, 1, 1])
                    all_insumos = db.query(Insumo).filter(Insumo.is_active == True).all()
                    insumo_add = col_add1.selectbox("Buscar Insumo", all_insumos, format_func=lambda x: f"{x.name} (Q{x.cost_gtq})", key=f"ins_sel_{q.id}")
                    qty_add = col_add2.number_input("Cant/Pax", min_value=1.0, value=1.0, key=f"qty_{q.id}")
                    units_add = col_add3.number_input("Días/Unid", min_value=1.0, value=1.0, key=f"unit_{q.id}")
                    
                    if col_add4.button("Agregar", key=f"btn_add_{q.id}"):
                        costo_linea_gtq = insumo_add.cost_gtq * qty_add * units_add
                        costo_linea_usd = costo_linea_gtq / 7.8 
                        new_line = QuoteLine(
                            quote_id=q.id, insumo_id=insumo_add.id,
                            qty_personas=qty_add, units_value=units_add,
                            line_cost_gtq=costo_linea_gtq, line_cost_usd=costo_linea_usd
                        )
                        db.add(new_line)
                        q.total_cost_gtq += costo_linea_gtq
                        q.total_cost_usd += costo_linea_usd
                        db.commit()
                        st.rerun()

                st.divider()

                # --- D. ANÁLISIS FINANCIERO Y PRECIO FINAL ---
                costo_usd = q.total_cost_usd
                
                # 1. Calculamos Sugerido (70%)
                precio_sugerido = costo_usd / 0.30 if costo_usd > 0 else 0
                
                # Layout de decisión
                st.markdown("### 🎯 Definición de Precio de Venta")
                st.caption("El sistema sugiere un precio basado en margen del 70%, pero tú defines el final.")

                col_metrics, col_input = st.columns([2, 2])
                
                with col_metrics:
                    # Mostramos métricas de referencia
                    st.metric("Costo Total (Base)", f"${costo_usd:,.2f}")
                    st.metric("Sugerido (70% Margen)", f"${precio_sugerido:,.2f}", delta="Target Ideal")

                with col_input:
                    # --- INPUT CLAVE: PRECIO REAL ---
                    # Por defecto ponemos el sugerido, pero es editable
                    final_price_input = st.number_input(
                        "💰 Precio Final de Venta (USD)",
                        min_value=0.0,
                        value=float(precio_sugerido), # Valor inicial sugerido
                        step=10.0,
                        help="Este es el valor que se verá en el Dashboard de Ventas.",
                        key=f"final_price_{q.id}"
                    )
                    
                    # Calculamos utilidad real en vivo basada en el input
                    utilidad_real = final_price_input - costo_usd
                    margen_real = (utilidad_real / final_price_input * 100) if final_price_input > 0 else 0
                    
                    if margen_real < 30:
                        st.error(f"⚠️ Margen bajo: {margen_real:.1f}%")
                    else:
                        st.success(f"✅ Margen saludable: {margen_real:.1f}%")

                st.divider()

                # --- E. BOTONES DE ACCIÓN ---
                btn_col1, btn_col2 = st.columns(2)
                
                if btn_col1.button("✅ APROBAR CON ESTE PRECIO", key=f"ap_{q.id}", type="primary"):
                    q.status = "APROBADA"
                    
                    # --- AQUÍ GUARDAMOS EL DATO PARA EL DASHBOARD ---
                    q.final_sale_price_usd = final_price_input # <--- ESTO ES LO IMPORTANTE
                    q.suggested_price_usd_m70 = precio_sugerido # Guardamos el sugerido como referencia histórica
                    
                    db.commit()
                    st.balloons()
                    st.success(f"Actividad aprobada. Venta registrada: ${final_price_input:,.2f}")
                    st.rerun()
                
                if btn_col2.button("❌ RECHAZAR", key=f"rej_{q.id}"):
                    q.status = "BORRADOR"
                    db.commit()
                    st.toast("Devuelta a borrador.")
                    st.rerun()

# --- TAB 2: ACTIVAS (DONDE SE GASTA) ---
with tab_act:
    st.info("Estas actividades están visibles para que los usuarios carguen gastos.")
    
    active_quotes = db.query(Quote).filter(Quote.status == "APROBADA").all()
    
    if not active_quotes:
        st.warning("No hay actividades activas actualmente.")
    else:
        # Tabla resumen
        data_active = [{
            "ID": q.id,
            "Actividad": q.activity_name, 
            "Presupuesto": f"${q.total_cost_usd:,.2f}",
            "Creada": q.created_at.strftime("%d/%m/%Y")
        } for q in active_quotes]
        st.dataframe(pd.DataFrame(data_active), use_container_width=True)
        
        st.divider()
        st.subheader("🔒 Liquidar / Cerrar Actividad")
        st.caption("Al liquidar, la actividad desaparece del menú de gastos pero se mantiene en el Dashboard.")
        
        # Selector para liquidar
        q_to_close = st.selectbox("Seleccionar Actividad para Liquidar", active_quotes, format_func=lambda x: f"{x.activity_name} (#{x.id})")
        
        if st.button("🏁 LIQUIDAR ACTIVIDAD", type="primary"):
            if q_to_close:
                q_to_close.status = "LIQUIDADA" # <--- CAMBIA A ESTADO FINAL
                db.commit()
                st.balloons()
                st.success(f"{q_to_close.activity_name} ha sido liquidada correctamente.")
                st.rerun()

# --- TAB 3: LIQUIDADAS (HISTÓRICO) ---
with tab_liq:
    st.info("Historial de actividades finalizadas. Ya no reciben gastos.")
    
    closed_quotes = db.query(Quote).filter(Quote.status == "LIQUIDADA").order_by(Quote.id.desc()).all()
    
    if closed_quotes:
        df_closed = pd.DataFrame([{
            "ID": q.id,
            "Actividad": q.activity_name,
            "Total Final": f"${q.total_cost_usd:,.2f}"
        } for q in closed_quotes])
        st.dataframe(df_closed, use_container_width=True)
        
        # Opción de Emergencia: Reactivar
        with st.expander("🛠️ Zona de Peligro: Reactivar Actividad"):
            q_reactivate = st.selectbox("Elegir actividad para reactivar", closed_quotes, format_func=lambda x: x.activity_name)
            if st.button("🔄 Reactivar (Volver a Aprobada)"):
                q_reactivate.status = "APROBADA"
                db.commit()
                st.success("Actividad reactivada.")
                st.rerun()
    else:
        st.write("No hay actividades liquidadas aún.")