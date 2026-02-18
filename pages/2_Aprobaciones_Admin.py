import streamlit as st
import pandas as pd
from database import get_db
from models import Quote, User
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
    st.info("Aquí llegan las cotizaciones nuevas para ser revisadas.")
    
    pending_quotes = db.query(Quote).filter(Quote.status == "ENVIADA").all()
    
    if not pending_quotes:
        st.success("✅ Todo al día. No hay aprobaciones pendientes.")
    else:
        for q in pending_quotes:
            with st.expander(f"📌 {q.activity_name} (Solicita: {q.created_by}) - ${q.total_cost_usd:,.2f}"):
                # Mostrar detalles básicos
                st.write(f"**Cliente/Actividad:** {q.activity_name}")
                st.write(f"**Notas:** {q.notes}")
                
                # Botones de Acción
                c1, c2 = st.columns(2)
                if c1.button("✅ APROBAR", key=f"ap_{q.id}"):
                    q.status = "APROBADA" # <--- CAMBIA A ESTADO ACTIVO
                    db.commit()
                    st.toast(f"Actividad {q.activity_name} APROBADA y ACTIVA.")
                    st.rerun()
                
                if c2.button("❌ RECHAZAR (Volver a Borrador)", key=f"rej_{q.id}"):
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