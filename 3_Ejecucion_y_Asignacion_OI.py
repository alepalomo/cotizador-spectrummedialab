import streamlit as st
from database import get_db
from models import Quote, OI, Mall
from auth import require_role

require_role(["ADMIN", "AUTORIZADO"])
db = next(get_db())

st.title("🚀 Asignación de OI y Ejecución")
st.markdown("Aquí conviertes una **Cotización Aprobada** en una actividad **Ejecutada**, asignándole la cuenta (OI) que pagará.")

# 1. Buscar Cotizaciones Aprobadas (Pendientes de Ejecución)
pending_execution = db.query(Quote).filter(Quote.status == "APROBADA").all()

if not pending_execution:
    st.info("🎉 No hay cotizaciones pendientes de ejecución.")
else:
    for q in pending_execution:
        with st.expander(f"📌 #{q.id}: {q.activity_name} | Total: ${q.total_cost_usd:,.2f}", expanded=True):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**Creado por:** {q.creator.username}")
                st.write(f"**Mall sugerido:** {q.mall.name if q.mall_id else 'No definido'}")
                st.info(f"Notas: {q.notes}")
            
            with col2:
                # Lógica para asignar OI
                st.write("### Asignar Cuenta (OI)")
                
                # Filtramos las OIs. Si la cotización ya tenía Mall, mostramos OIs de ese Mall.
                if q.mall_id:
                    ois_available = db.query(OI).filter(OI.mall_id == q.mall_id, OI.is_active==True).all()
                else:
                    ois_available = db.query(OI).filter(OI.is_active==True).all()
                
                if not ois_available:
                    st.error("No hay OIs disponibles para este Mall.")
                else:
                    # Selectbox para elegir la OI
                    selected_oi = st.selectbox(
                        f"Selecciona OI para #{q.id}", 
                        ois_available, 
                        format_func=lambda x: f"{x.oi_code} - {x.oi_name}",
                        key=f"sel_oi_{q.id}"
                    )
                    
                    if st.button(f"✅ CONFIRMAR EJECUCIÓN #{q.id}", type="primary"):
                        # Actualizamos la cotización
                        q.oi_id = selected_oi.id
                        q.status = "EJECUTADA"
                        # Si no tenía Mall, le asignamos el de la OI
                        if not q.mall_id:
                            q.mall_id = selected_oi.mall_id
                            
                        db.commit()
                        st.success(f"Actividad #{q.id} ejecutada y asignada a OI {selected_oi.oi_code}")
                        st.rerun()