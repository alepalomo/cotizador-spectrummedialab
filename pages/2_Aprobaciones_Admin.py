import streamlit as st
import pandas as pd
from database import get_db
from models import Quote
from auth import require_role

require_role(["ADMIN"])
db = next(get_db())

st.title("🛡️ Panel de Aprobaciones")

# Buscar cotizaciones que están esperando aprobación
pending = db.query(Quote).filter(Quote.status == "ENVIADA").all()

if not pending:
    st.success("✅ Todo limpio. No hay cotizaciones pendientes.")
else:
    for q in pending:
        # Usamos un expander para agrupar cada solicitud visualmente
        label = f"📌 #{q.id} - {q.activity_name} (Solicitado por: {q.creator.username if q.creator else '?'})"
        with st.expander(label, expanded=True):
            
            # --- 1. DESGLOSE DETALLADO (LO QUE PEDISTE) ---
            st.markdown("#### 🛒 Desglose de Costos")
            if q.lines:
                # Convertimos las líneas a una tabla bonita con Pandas
                data_items = []
                for line in q.lines:
                    data_items.append({
                        "Insumo": line.insumo.name,
                        "Personas": int(line.qty_personas),
                        "Unidades": int(line.units_value),
                        "Costo Total USD": f"${line.line_cost_usd:,.2f}"
                    })
                df = pd.DataFrame(data_items)
                st.dataframe(df, use_container_width=True)
            else:
                st.warning("⚠️ Esta cotización está vacía (sin líneas).")

            # --- 2. RESUMEN FINANCIERO ---
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("Costo Total (Base)", f"${q.total_cost_usd:,.2f}")
            c2.metric("Precio Sugerido (60%)", f"${q.suggested_price_usd_m60:,.2f}")
            c3.write(f"**Notas del Vendedor:**\n_{q.notes if q.notes else 'Sin notas'}_")

            # --- 3. ZONA DE DECISIÓN (APROBAR O RECHAZAR) ---
            st.markdown("### ⚖️ Decisión del Administrador")
            
            col_input, col_buttons = st.columns([1, 1])
            
            with col_input:
                # El admin tiene la última palabra sobre el precio de venta
                final_sale_price = st.number_input(
                    "Precio Final de Venta (USD) a autorizar:", 
                    min_value=0.0, 
                    value=q.suggested_price_usd_m60, 
                    step=100.0,
                    key=f"price_{q.id}"
                )
            
            with col_buttons:
                st.write("") # Espaciador para alinear botones abajo
                st.write("")
                b_ok, b_cancel = st.columns(2)
                
                # BOTÓN APROBAR
                if b_ok.button("✅ APROBAR", key=f"app_{q.id}", type="primary", use_container_width=True):
                    q.status = "APROBADA"
                    q.final_sale_price_usd = final_sale_price
                    db.commit()
                    st.balloons()
                    st.success(f"Solicitud #{q.id} Aprobada por ${final_sale_price:,.2f}")
                    st.rerun()
                
                # BOTÓN RECHAZAR (NUEVO)
                if b_cancel.button("❌ RECHAZAR", key=f"rej_{q.id}", type="secondary", use_container_width=True):
                    q.status = "RECHAZADA"
                    db.commit()
                    st.error(f"Solicitud #{q.id} Rechazada.")
                    st.rerun()