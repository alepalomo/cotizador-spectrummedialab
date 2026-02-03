import streamlit as st
import pandas as pd
import datetime
import os
import zipfile 
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

tab_odc, tab_caja, tab_host = st.tabs(["📝 ODC", "📦 Caja Chica", "🎤 Host / Talento"])

def get_active_activities():
    return db.query(Quote).filter(Quote.status.in_(["EJECUTADA", "APROBADA"])).all()

# --- PESTAÑA 1 y 2 (Sin cambios mayores, solo mantenemos estructura) ---
with tab_odc:
    st.subheader("Registro por Orden de Compra")
    with st.form("form_odc", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        odc_text = c1.text_input("Número de ODC")
        date_odc = c2.date_input("Fecha de Ingreso")
        ois = db.query(OI).filter(OI.is_active==True).all()
        oi_sel = c3.selectbox("OI", ois, format_func=lambda x: f"{x.oi_code} - {x.oi_name} ({x.mall.name if x.mall else 'Sin Mall'})", key="oi_odc")
        c4, c5 = st.columns(2)
        provs = db.query(Company).filter(Company.is_active==True).all()
        prov_sel = c4.selectbox("Proveedor", provs, format_func=lambda x: x.name, key="prov_odc")
        amount_q = c5.number_input("Monto (Q)", min_value=0.0, step=100.0, key="amt_odc")
        desc_odc = st.text_input("Descripción")
        acts = get_active_activities()
        act_sel = st.selectbox("Actividad", acts, format_func=lambda x: f"#{x.id} {x.activity_name}", key="act_odc")
        
        if st.form_submit_button("💾 Guardar ODC"):
            if not act_sel or not oi_sel: st.error("Datos faltantes")
            else:
                rate = get_active_rate(db)
                db.add(Expense(date=date_odc, year=date_odc.year, month=date_odc.month, mall_id=act_sel.mall_id, oi_id=oi_sel.id, quote_id=act_sel.id, category="ODC", description=desc_odc, amount_gtq=amount_q, amount_usd=amount_q/rate, odc_number=odc_text, company_id=prov_sel.id if prov_sel else None))
                db.commit(); st.success("Guardado")

with tab_caja:
    st.subheader("Registro de Caja Chica")
    with st.form("form_cc", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        amount_cc = c1.number_input("Monto (Q)", min_value=0.0, step=10.0, key="amt_cc")
        date_cc = c2.date_input("Fecha", key="date_cc")
        fact_cc = c3.text_input("# Factura", key="fact_cc")
        c4, c5 = st.columns(2)
        prov_cc = c4.selectbox("Proveedor", provs, format_func=lambda x: f"{x.name} (NIT: {x.nit})", key="prov_cc")
        oi_cc = c5.selectbox("OI", ois, format_func=lambda x: f"{x.oi_code} - {x.oi_name}", key="oi_cc")
        txt_add = st.text_input("Texto Adicional 2")
        act_cc = st.selectbox("Actividad", acts, format_func=lambda x: f"#{x.id} {x.activity_name}", key="act_cc")
        if st.form_submit_button("💾 Guardar Caja Chica"):
            rate = get_active_rate(db)
            db.add(Expense(date=date_cc, year=date_cc.year, month=date_cc.month, mall_id=act_cc.mall_id, oi_id=oi_cc.id, quote_id=act_cc.id, category="CAJA_CHICA", description=f"Factura {fact_cc}", amount_gtq=amount_cc, amount_usd=amount_cc/rate, doc_number=fact_cc, company_id=prov_cc.id, text_additional=txt_add))
            db.commit(); st.success("Guardado")

# --- PESTAÑA 3: HOST (CON GENERACIÓN DE CONTRATO Y RECIBO) ---
def format_date_es(d):
    meses = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    return f"{d.day} de {meses[d.month]} de {d.year}"

with tab_host:
    st.subheader("Generación de Recibos y Contratos")
    
    if "host_rows" not in st.session_state:
        st.session_state["host_rows"] = [{"desc": "", "rate": 0.0, "days": 0}]

    h1, h2, h3 = st.columns(3)
    prov_host = h1.selectbox("Proveedor (Host)", provs, format_func=lambda x: x.name, key="prov_host")
    if prov_host:
        h1.caption(f"CUI: {prov_host.cui if prov_host.cui else '⚠️ Falta CUI'}")
    
    act_host_selection = h2.selectbox("Actividad", acts, format_func=lambda x: x.activity_name, key="act_host")
    date_host = h3.date_input("Fecha Documentos", datetime.date.today(), key="date_host")
    
    # NUEVO CAMPO PARA EL CONTRATO
    contract_desc_form = st.text_input("Descripción para el Contrato (ej: promoción de producto, eventos...)", placeholder="Ingresa la descripción del servicio para el contrato legal")

    st.markdown("#### Detalle de Servicios")
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

    total_host = sum([r["rate"] * r["days"] for r in st.session_state["host_rows"]])
    st.metric("Total a Pagar", f"Q{total_host:,.2f}")

    if st.button("💾 Guardar y Generar Documentos"):
        if not act_host_selection or not prov_host:
            st.error("Faltan datos")
        elif not prov_host.cui:
            st.error(f"El proveedor {prov_host.name} no tiene CUI registrado. Agrégalo en Catálogos Admin.")
        elif not contract_desc_form:
            st.error("Debes llenar la Descripción para el Contrato.")
        else:
            act_fresh = db.query(Quote).get(act_host_selection.id)
            rate = get_active_rate(db)
            oi_id_final = act_fresh.oi_id if act_fresh.oi_id else db.query(OI).first().id 
            
            # Guardar Gasto
            new_exp = Expense(
                date=date_host, year=date_host.year, month=date_host.month,
                mall_id=act_fresh.mall_id, oi_id=oi_id_final, quote_id=act_fresh.id,
                category="HOST", description=f"Host {prov_host.name}",
                amount_gtq=total_host, amount_usd=total_host/rate,
                company_id=prov_host.id, host_details=st.session_state["host_rows"]
            )
            db.add(new_exp)
            db.commit()
            
            recibo_id_str = f"{new_exp.id:05d}"
            header_img_path = "header_spectrummedia.png"
            width, height = LETTER
            
            # --- 1. GENERAR RECIBO (PDF) ---
            buff_recibo = io.BytesIO()
            p = canvas.Canvas(buff_recibo, pagesize=LETTER)
            
            # Header
            if os.path.exists(header_img_path):
                p.drawImage(header_img_path, 0, height-100, width=width, height=100, preserveAspectRatio=False, mask='auto')
            else:
                p.setFillColor(colors.black); p.rect(0, height-80, width, 80, fill=1)
                p.setFillColor(colors.white); p.setFont("Helvetica-Bold", 24); p.drawString(50, height-50, "spectrum media")
            
            p.setFillColor(colors.white); p.setFont("Helvetica-Bold", 18)
            p.drawRightString(width - 50, height - 50, f"RECIBO #{recibo_id_str}")
            
            # Info Recibo
            p.setFillColor(colors.black); p.setFont("Helvetica-Bold", 12)
            y = height - 130
            p.drawString(400, y, f"FECHA: {date_host.strftime('%d/%m/%Y')}")
            p.drawString(50, y, "RECIBO DE: SPECTRUM MEDIA LAB")
            p.drawString(50, y-20, f"RECIBO PARA: {prov_host.name.upper()}")
            p.setFont("Helvetica", 10)
            p.drawString(50, y-60, f"Banco: {prov_host.bank_name}"); p.drawString(50, y-75, f"Nombre: {prov_host.name}"); p.drawString(50, y-90, f"Cuenta: {prov_host.account_number}")
            
            # Tabla Recibo
            y_table = y - 140
            p.setFont("Helvetica-Bold", 10)
            p.drawString(50, y_table, "DESCRIPTION"); p.drawString(350, y_table, "RATE"); p.drawString(420, y_table, "DIA"); p.drawString(500, y_table, "AMOUNT"); p.line(50, y_table-5, 550, y_table-5)
            y_row = y_table - 25; p.setFont("Helvetica", 10)
            for row in st.session_state["host_rows"]:
                p.drawString(50, y_row, row["desc"]); p.drawString(350, y_row, f"Q{row['rate']}"); p.drawString(430, y_row, str(row['days'])); p.drawString(500, y_row, f"Q{row['rate']*row['days']}"); p.line(50, y_row-5, 550, y_row-5); y_row -= 25
            p.setFont("Helvetica-Bold", 14); p.drawString(50, y_row-20, "TOTAL"); p.drawString(500, y_row-20, f"Q{total_host:,.2f}")
            p.line(200, 100, 400, 100); p.setFont("Helvetica", 8); p.drawCentredString(300, 85, "FIRMA DE PAGO RECIBIDO")
            p.save()
            buff_recibo.seek(0)
            
            # --- 2. GENERAR CONTRATO (PDF) ---
            buff_contrato = io.BytesIO()
            c = canvas.Canvas(buff_contrato, pagesize=LETTER)
            
            # Header Contrato
            if os.path.exists(header_img_path):
                c.drawImage(header_img_path, 0, height-100, width=width, height=100, preserveAspectRatio=False, mask='auto')
            
            c.setFillColor(colors.black)
            
            # Título y Fecha
            c.setFont("Helvetica-Bold", 11)
            c.drawRightString(width-50, height-130, "Asunto: Brand Activation Ambassador")
            c.setFont("Helvetica", 11)
            c.drawRightString(width-50, height-150, f"En la fecha: {format_date_es(date_host)}.")
            
            # Cuerpo del Contrato
            y_text = height - 200
            line_height = 16
            left_margin = 50
            
            # Párrafo 1
            c.drawString(left_margin, y_text, f"Yo, {prov_host.name} (del forms) me identifico con el Documento Personal de")
            y_text -= line_height
            c.drawString(left_margin, y_text, f"Identificación (DPI) con Código Único de Identificación (CUI) No. {prov_host.cui} (de BDD),")
            y_text -= line_height
            c.drawString(left_margin, y_text, "por medio de la presente acuerdo prestar servicios como BRAND ACTIVATION AMBASSADOR")
            y_text -= line_height
            c.drawString(left_margin, y_text, f"- {contract_desc_form.upper()} para SPECTRUM")
            y_text -= line_height
            c.drawString(left_margin, y_text, "MEDIA prestando un servicio y realizando actividades relacionadas con promoción de")
            y_text -= line_height
            c.drawString(left_margin, y_text, "producto, eventos o generación de contenido, según lo asignado.")
            y_text -= (line_height * 2)
            
            # Párrafo 2
            c.drawString(left_margin, y_text, f"Como compensación por estos servicios, se entregará un pago único de Q.{total_host:,.2f} (del")
            y_text -= line_height
            c.drawString(left_margin, y_text, "form), el día y lugar que me ha sido notificado previamente.")
            y_text -= (line_height * 2)
            
            # Cláusulas
            c.drawString(left_margin, y_text, "En consecuencia, ambas partes reconocen expresamente que:")
            y_text -= (line_height * 1.5)
            
            clauses = [
                "No existe entre ellas relación laboral de ningún tipo, conforme a la legislación laboral vigente.",
                "No se genera ninguna obligación de carácter laboral, tales como pago de salarios,", 
                "prestaciones laborales, indemnizaciones, o cualquier otro derecho laboral.",
                "Cada parte actúa de forma autónoma, sin que exista dependencia, ni vínculo",
                "permanente más allá del objeto del contrato de servicios."
            ]
            
            for clause in clauses:
                c.drawString(left_margin + 20, y_text, f"•   {clause}")
                y_text -= line_height
            
            y_text -= line_height
            c.drawString(left_margin, y_text, "La presente notificación tiene como finalidad reiterar la naturaleza de la prestación de")
            y_text -= line_height
            c.drawString(left_margin, y_text, "servicios, y dejar claro que no se establece, ni se presumirá, ningún tipo de vínculo laboral")
            y_text -= line_height
            c.drawString(left_margin, y_text, f"entre Spectrum Media y {prov_host.name}")
            
            # Firmas
            y_sig = 150
            c.setFont("Helvetica-Bold", 10)
            c.drawString(left_margin, y_sig, "Firma del Brand Ambassador: __________________________")
            c.drawString(left_margin, y_sig-15, f"Nombre completo: {prov_host.name}")
            
            # Firma Spectrum (Imagen o Espacio)
            c.drawString(left_margin, 80, "Firma del responsable de la empresa:")
            c.drawString(left_margin, 65, "Nombre y cargo: Maria Jose Aguilar, Product Executive")
            
            c.save()
            buff_contrato.seek(0)
            
            # --- 3. CREAR ZIP ---
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                zip_file.writestr(f"Recibo_{recibo_id_str}.pdf", buff_recibo.getvalue())
                zip_file.writestr(f"Contrato_{recibo_id_str}.pdf", buff_contrato.getvalue())
            
            st.success("¡Documentos Generados!")
            st.download_button(
                label="🗂️ Descargar ZIP (Contrato + Recibo)",
                data=zip_buffer.getvalue(),
                file_name=f"Docs_Host_{recibo_id_str}.zip",
                mime="application/zip"
            )