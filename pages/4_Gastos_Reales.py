import streamlit as st
import pandas as pd
import datetime
from database import get_db
from models import Expense, Mall, OI, Company, Quote
from auth import require_role
from services import get_active_rate

# Librerías para PDF
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import io

require_role(["ADMIN", "AUTORIZADO"])
db = next(get_db())

st.title("💸 Registro de Gastos Reales")

# --- SELECTOR DE PESTAÑAS PRINCIPALES ---
tab_odc, tab_caja, tab_host = st.tabs(["📝 ODC", "📦 Caja Chica", "🎤 Host / Talento"])

# Función auxiliar para filtrar actividades VIVAS (No liquidadas)
def get_active_activities():
    return db.query(Quote).filter(Quote.status.in_(["EJECUTADA", "APROBADA"])).all()

# --- PESTAÑA 1: ODC (Orden de Compra) ---
with tab_odc:
    st.subheader("Registro por Orden de Compra")
    with st.form("form_odc", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        odc_text = c1.text_input("Número de ODC")
        date_odc = c2.date_input("Fecha de Ingreso")
        
        # OIs
        ois = db.query(OI).filter(OI.is_active==True).all()
        oi_sel = c3.selectbox("OI que registra el gasto", ois, format_func=lambda x: f"{x.oi_code} - {x.oi_name}", key="oi_odc")
        
        c4, c5 = st.columns(2)
        provs = db.query(Company).filter(Company.is_active==True).all()
        prov_sel = c4.selectbox("Proveedor", provs, format_func=lambda x: x.name, key="prov_odc")
        amount_q = c5.number_input("Monto (Quetzales)", min_value=0.0, step=100.0, key="amt_odc")
        
        desc_odc = st.text_input("Descripción del Gasto")
        
        # Actividad Vinculada (Obligatoria)
        acts = get_active_activities()
        act_sel = st.selectbox("Vincular a Actividad", acts, format_func=lambda x: f"#{x.id} {x.activity_name}", key="act_odc")
        
        if st.form_submit_button("💾 Guardar ODC"):
            if not act_sel or not oi_sel:
                st.error("OI y Actividad son obligatorias")
            else:
                rate = get_active_rate(db)
                new_exp = Expense(
                    date=date_odc, year=date_odc.year, month=date_odc.month,
                    mall_id=act_sel.mall_id, oi_id=oi_sel.id, quote_id=act_sel.id,
                    category="ODC", description=desc_odc,
                    amount_gtq=amount_q, amount_usd=amount_q/rate,
                    odc_number=odc_text, company_id=prov_sel.id if prov_sel else None
                )
                db.add(new_exp)
                db.commit()
                st.success("Gasto ODC Guardado")

    st.divider()
    st.markdown("⬇️ **Descargar Reporte ODC**")
    d1, d2 = st.columns(2)
    start_d = d1.date_input("Desde", datetime.date.today().replace(day=1), key="d1_odc")
    end_d = d2.date_input("Hasta", datetime.date.today(), key="d2_odc")
    
    if st.button("Generar CSV ODC"):
        data = db.query(Expense).filter(Expense.category=="ODC", Expense.date >= start_d, Expense.date <= end_d).all()
        if data:
            df = pd.DataFrame([{
                "Fecha": e.date, "ODC": e.odc_number, "OI": e.oi.oi_code, 
                "Proveedor": e.company.name if e.company else "", 
                "Monto Q": e.amount_gtq, "Descripcion": e.description,
                "Actividad": e.quote.activity_name
            } for e in data])
            st.download_button("Descargar CSV", df.to_csv(index=False).encode('utf-8'), "reporte_odc.csv", "text/csv")
        else:
            st.warning("No hay datos en ese rango.")

# --- PESTAÑA 2: CAJA CHICA ---
with tab_caja:
    st.subheader("Registro de Caja Chica (Contable)")
    with st.form("form_cc", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        amount_cc = c1.number_input("Monto (Q)", min_value=0.0, step=10.0, key="amt_cc")
        date_cc = c2.date_input("Fecha Documento", key="date_cc")
        fact_cc = c3.text_input("# Factura", key="fact_cc")
        
        c4, c5 = st.columns(2)
        # Proveedor (Autocompletar NIT y Razón Social internamente)
        prov_cc = c4.selectbox("Proveedor", provs, format_func=lambda x: f"{x.name} (NIT: {x.nit})", key="prov_cc")
        if prov_cc:
            st.caption(f"📌 NIT: {prov_cc.nit} | Razón Social: {prov_cc.legal_name}")
            
        oi_cc = c5.selectbox("Orden Interna", ois, format_func=lambda x: x.oi_code, key="oi_cc")
        
        txt_add = st.text_input("Texto Adicional 2")
        act_cc = st.selectbox("Vincular a Actividad", acts, format_func=lambda x: f"#{x.id} {x.activity_name}", key="act_cc")
        
        if st.form_submit_button("💾 Guardar Caja Chica"):
            rate = get_active_rate(db)
            new_exp = Expense(
                date=date_cc, year=date_cc.year, month=date_cc.month,
                mall_id=act_cc.mall_id, oi_id=oi_cc.id, quote_id=act_cc.id,
                category="CAJA_CHICA", description=f"Factura {fact_cc}",
                amount_gtq=amount_cc, amount_usd=amount_cc/rate,
                doc_number=fact_cc, company_id=prov_cc.id,
                text_additional=txt_add
            )
            db.add(new_exp)
            db.commit()
            st.success("Gasto Caja Chica Guardado")

    st.divider()
    st.markdown("⬇️ **Reporte Contable Caja Chica**")
    if st.button("Generar CSV Contable"):
        data_cc = db.query(Expense).filter(Expense.category=="CAJA_CHICA").all()
        if data_cc:
            # Estructura fija solicitada
            export_data = []
            for e in data_cc:
                export_data.append({
                    "Operación Contable": "COSTO O GASTO GRAVADO",
                    "Monto": e.amount_gtq,
                    "ST.doc": "",
                    "Ind.Impuesto": "V1",
                    "Libro Mayor": "7006080000",
                    "NIT": e.company.nit if e.company else "",
                    "RAZÓN SOCIAL": e.company.legal_name if e.company else "",
                    "Fecha Documento": e.date,
                    "# FACT": e.doc_number,
                    "Orden Interna": e.oi.oi_code,
                    "Texto": "B",
                    "Texto Adicional 2": e.text_additional,
                    "Actividad": e.quote.activity_name
                })
            df_cc = pd.DataFrame(export_data)
            st.download_button("Descargar CSV Contable", df_cc.to_csv(index=False).encode('utf-8'), "caja_chica.csv", "text/csv")

# --- PESTAÑA 3: HOST (CON GENERACIÓN DE PDF) ---
with tab_host:
    st.subheader("Generación de Recibos Host")
    
    # Variables de estado para las filas
    if "host_rows" not in st.session_state:
        st.session_state["host_rows"] = [{"desc": "", "rate": 0.0, "days": 0}]

    # 1. Cabecera
    h1, h2 = st.columns(2)
    prov_host = h1.selectbox("Proveedor (Host)", provs, format_func=lambda x: x.name, key="prov_host")
    if prov_host:
        h1.info(f"🏦 {prov_host.bank_name} | No. {prov_host.account_number}")
    
    act_host = h2.selectbox("Actividad", acts, format_func=lambda x: x.activity_name, key="act_host")
    
    # 2. Filas Dinámicas (Hasta 10)
    st.markdown("#### Detalle de Servicios")
    
    # Editor de filas
    for idx, row in enumerate(st.session_state["host_rows"]):
        c_desc, c_rate, c_days, c_del = st.columns([3, 1, 1, 0.5])
        row["desc"] = c_desc.text_input(f"Descripción {idx+1}", value=row["desc"], key=f"hd_{idx}")
        row["rate"] = c_rate.number_input(f"Tarifa {idx+1}", value=row["rate"], key=f"hr_{idx}")
        row["days"] = c_days.number_input(f"Días {idx+1}", value=row["days"], key=f"hdy_{idx}")
        
        if c_del.button("❌", key=f"del_{idx}") and len(st.session_state["host_rows"]) > 1:
            st.session_state["host_rows"].pop(idx)
            st.rerun()
            
    if len(st.session_state["host_rows"]) < 10:
        if st.button("➕ Agregar Fila"):
            st.session_state["host_rows"].append({"desc": "", "rate": 0.0, "days": 0})
            st.rerun()

    # Cálculo Total
    total_host = sum([r["rate"] * r["days"] for r in st.session_state["host_rows"]])
    st.metric("Total a Pagar", f"Q{total_host:,.2f}")

    # 3. Guardar y Generar PDF
    if st.button("💾 Guardar y Generar PDF"):
        if not act_host or not prov_host:
            st.error("Faltan datos principales")
        else:
            # Guardar en BD
            rate = get_active_rate(db)
            # Buscamos la OI de la actividad automáticamente
            oi_linked = act_host.oi if act_host.oi else (act_host.quote.oi if act_host.quote else None)
            # Fallback simple: toma la primera OI si no está linkeada (debería estarlo)
            oi_id = act_host.oi_id if act_host.oi_id else db.query(OI).first().id 

            new_exp = Expense(
                date=datetime.date.today(), year=datetime.date.today().year, month=datetime.date.today().month,
                mall_id=act_host.mall_id, oi_id=oi_id, quote_id=act_host.id,
                category="HOST", description=f"Recibo Host {prov_host.name}",
                amount_gtq=total_host, amount_usd=total_host/rate,
                company_id=prov_host.id,
                host_details=st.session_state["host_rows"]
            )
            db.add(new_exp)
            db.commit()
            
            # --- GENERACIÓN PDF (ReportLab) ---
            buffer = io.BytesIO()
            p = canvas.Canvas(buffer, pagesize=LETTER)
            width, height = LETTER
            
            # Header (Estilo Spectrum Media Negro/Azul)
            p.setFillColor(colors.black)
            p.rect(0, height-80, width, 80, fill=1) # Fondo negro header
            
            p.setFillColor(colors.white)
            p.setFont("Helvetica-Bold", 24)
            p.drawString(50, height-50, "spectrum media")
            p.drawString(400, height-50, f"RECIBO #{new_exp.id}")
            
            # Info Proveedor
            p.setFillColor(colors.black)
            p.setFont("Helvetica-Bold", 12)
            y = height - 120
            p.drawString(50, y, "RECIBO DE: SPECTRUM MEDIA LAB")
            p.drawString(50, y-20, f"RECIBO PARA: {prov_host.name.upper()}")
            
            p.setFont("Helvetica", 10)
            p.drawString(50, y-60, f"Banco: {prov_host.bank_name}")
            p.drawString(50, y-75, f"Nombre de cuenta: {prov_host.name}")
            p.drawString(50, y-90, f"Numero de cuenta: {prov_host.account_number}")
            
            # Tabla
            y_table = y - 140
            p.setFont("Helvetica-Bold", 10)
            p.drawString(50, y_table, "DESCRIPTION")
            p.drawString(350, y_table, "RATE")
            p.drawString(420, y_table, "DIA")
            p.drawString(500, y_table, "AMOUNT")
            p.line(50, y_table-5, 550, y_table-5)
            
            y_row = y_table - 25
            p.setFont("Helvetica", 10)
            
            for row in st.session_state["host_rows"]:
                subt = row["rate"] * row["days"]
                p.drawString(50, y_row, row["desc"])
                p.drawString(350, y_row, f"Q{row['rate']}")
                p.drawString(430, y_row, str(row['days']))
                p.drawString(500, y_row, f"Q{subt}")
                p.line(50, y_row-5, 550, y_row-5)
                y_row -= 25
            
            # Total
            y_final = y_row - 20
            p.setFont("Helvetica-Bold", 14)
            p.drawString(50, y_final, "TOTAL")
            p.drawString(500, y_final, f"Q{total_host:,.2f}")
            
            # Firma
            p.line(200, 100, 400, 100)
            p.setFont("Helvetica", 8)
            p.drawCentredString(300, 85, "FIRMA DE PAGO RECIBIDO")
            
            p.save()
            buffer.seek(0)
            
            st.success("Gasto Guardado")
            st.download_button(
                label="🖨️ Descargar Recibo PDF",
                data=buffer,
                file_name=f"Recibo_{prov_host.name}_{act_host.activity_name}.pdf",
                mime="application/pdf"
            )