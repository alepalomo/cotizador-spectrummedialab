import streamlit as st
import pandas as pd
import datetime
from database import get_db
from models import Expense, Mall, OI, ExpenseType, Company, Quote
from auth import require_role
from services import get_active_rate

require_role(["ADMIN", "AUTORIZADO"])
db = next(get_db())

st.title("💸 Registro de Gastos Reales")

# --- SECCIÓN 1: FORMULARIO DE REGISTRO ---
with st.container():
    st.markdown("### Registrar Nueva Factura / Gasto")
    
    rate = get_active_rate(db)
    st.caption(f"Tipo de Cambio Activo: Q{rate} / USD")

    with st.form("expense_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        date_exp = c1.date_input("Fecha Gasto", datetime.date.today())
        
        malls = db.query(Mall).filter(Mall.is_active==True).all()
        sel_mall = c2.selectbox("Mall", malls, format_func=lambda x: x.name)
        
        ois = []
        if sel_mall:
            ois = db.query(OI).filter(OI.mall_id == sel_mall.id, OI.is_active==True).all()
        sel_oi = c3.selectbox("OI (Cuenta)", ois, format_func=lambda x: f"{x.oi_code} - {x.oi_name}")

        c4, c5 = st.columns([2, 1])
        quotes = db.query(Quote).filter(Quote.status.in_([ "EJECUTADA", "APROBADA"])).all()
        quote_opts = [None] + quotes
        sel_quote = c4.selectbox("Vincular a Actividad", quote_opts, format_func=lambda x: f"#{x.id} - {x.activity_name}" if x else "⚠️ GASTO NO PRESUPUESTADO")

        if sel_quote: c4.info(f"Presupuesto: Q{sel_quote.total_cost_gtq:,.2f}")

        amount_gtq = c5.number_input("Monto Factura (GTQ)", min_value=0.0, step=100.0)

        # --- FILA DE DOCUMENTOS (AQUÍ ESTÁ LO NUEVO) ---
        c6, c7, c8 = st.columns(3)
        
        # 1. Número de Factura
        doc_num = c6.text_input("Número de Factura")
        
        # 2. Número de ODC (NUEVO)
        odc_num = c7.text_input("Número de ODC")
        
        # 3. Tipo Documento
        ex_types = db.query(ExpenseType).all()
        sel_type = c8.selectbox("Tipo Doc", ex_types, format_func=lambda x: x.name) if ex_types else None

        # --- FILA DE PROVEEDOR Y DESCRIPCIÓN ---
        c9, c10 = st.columns([1, 2])
        
        # 4. Proveedor Desplegable (NUEVO)
        companies = db.query(Company).filter(Company.is_active==True).all()
        if not companies:
            c9.warning("¡No hay proveedores! Ve a Catálogos Admin.")
            sel_comp = None
        else:
            sel_comp = c9.selectbox("Proveedor", companies, format_func=lambda x: x.name)
        
        desc = c10.text_input("Descripción (Opcional si hay actividad)")
        
        notes = st.text_area("Notas Adicionales")

        if st.form_submit_button("💾 Registrar Gasto"):
            if not sel_oi:
                st.error("Falta OI.")
            else:
                final_desc = desc if desc else (sel_quote.activity_name if sel_quote else "Gasto General")
                
                new_exp = Expense(
                    date=date_exp,
                    year=date_exp.year,
                    month=date_exp.month,
                    mall_id=sel_mall.id,
                    oi_id=sel_oi.id,
                    quote_id=sel_quote.id if sel_quote else None,
                    description=final_desc,
                    amount_gtq=amount_gtq,
                    amount_usd=amount_gtq / rate,
                    
                    doc_type=sel_type.name if sel_type else "Otro",
                    doc_number=doc_num,
                    odc_number=odc_num, # Guardamos la ODC
                    
                    expense_type_id=sel_type.id if sel_type else None,
                    company_id=sel_comp.id if sel_comp else None, # Guardamos el Proveedor
                    notes=notes,
                    created_at=datetime.datetime.utcnow()
                )
                db.add(new_exp)
                db.commit()
                st.success("Gasto registrado exitosamente.")
                st.rerun()

# --- VISOR ---
st.divider()
st.subheader("📋 Historial Reciente")
expenses = db.query(Expense).order_by(Expense.date.desc()).limit(10).all()
if expenses:
    data = []
    for e in expenses:
        data.append({
            "Fecha": e.date,
            "Mall": e.mall.name,
            "Factura #": e.doc_number,
            "ODC #": e.odc_number, # Mostramos ODC en la tabla
            "Proveedor": e.company.name if e.company else "-",
            "Monto GTQ": f"Q{e.amount_gtq:,.2f}"
        })
    st.dataframe(pd.DataFrame(data), use_container_width=True)