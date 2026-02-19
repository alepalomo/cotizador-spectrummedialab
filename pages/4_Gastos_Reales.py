import streamlit as st
import pandas as pd
import datetime
import os
import zipfile 
from database import get_db
from models import Expense, Mall, OI, Proveedor, Quote
from auth import require_role
from services import get_active_rate
import io
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_RIGHT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph

require_role(["ADMIN", "AUTORIZADO", "VENDEDOR"])
db = next(get_db())

st.title("💸 Registro de Gastos Reales")

tab_odc, tab_caja, tab_host = st.tabs(["📝 ODC", "📦 Caja Chica", "🎤 Host / Talento"])

# --- CARGA INICIAL DE ACTIVIDADES ---
active_quotes = db.query(Quote).filter(Quote.status == "APROBADA").all()

if not active_quotes:
    st.warning("⚠️ No hay actividades activas (Aprobadas) para cargar gastos.")
    st.info("Pide al administrador que apruebe una cotización o reactiva una liquidada.")
    st.stop() # Detiene la app aquí si no hay nada

# --- PESTAÑA 1: ODC ---
with tab_odc:
    st.subheader("Registro por Orden de Compra")
    with st.form("form_odc", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        odc_text = c1.text_input("Número de ODC")
        date_odc = c2.date_input("Fecha de Ingreso")
        
        ois = db.query(OI).filter(OI.is_active==True).all()
        oi_sel = c3.selectbox(
            "OI que registra el gasto", 
            ois, 
            format_func=lambda x: f"{x.oi_code} - {x.oi_name} ({x.mall.name if x.mall else 'Sin Mall'})", 
            key="oi_odc"
        )
        
        c4, c5 = st.columns(2)
        provs = db.query(Proveedor).filter(Proveedor.is_active==True).all()
        prov_sel = c4.selectbox("Proveedor", provs, format_func=lambda x: x.name, key="prov_odc")
        amount_q = c5.number_input("Monto (Q)", min_value=0.0, step=100.0, key="amt_odc")
        desc_odc = st.text_input("Descripción")
        
        # --- CORRECCIÓN AQUÍ: Usamos active_quotes directamente ---
        act_sel = st.selectbox(
            "Actividad", 
            active_quotes, # <--- ANTES DECÍA acts
            format_func=lambda x: f"{x.activity_name} ({x.mall.name if x.mall else 'Global'})", 
            key="act_odc"
        )
        
        if st.form_submit_button("💾 Guardar ODC"):
            if not act_sel or not oi_sel: st.error("Datos faltantes")
            else:
                rate = get_active_rate(db)
                db.add(Expense(date=date_odc, year=date_odc.year, month=date_odc.month, mall_id=act_sel.mall_id, oi_id=oi_sel.id, quote_id=act_sel.id, category="ODC", description=desc_odc, amount_gtq=amount_q, amount_usd=amount_q/rate, odc_number=odc_text, company_id=prov_sel.id if prov_sel else None))
                db.commit(); st.success("Guardado")

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
        else: st.warning("No hay datos.")

# --- PESTAÑA 2: CAJA CHICA ---
with tab_caja:
    st.subheader("Registro de Caja Chica")
    with st.form("form_cc", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        amount_cc = c1.number_input("Monto (Q)", min_value=0.0, step=10.0, key="amt_cc")
        date_cc = c2.date_input("Fecha", key="date_cc")
        fact_cc = c3.text_input("# Factura", key="fact_cc")
        
        c4, c5 = st.columns(2)
        prov_cc = c4.selectbox("Proveedor", provs, format_func=lambda x: f"{x.name} (NIT: {x.nit})", key="prov_cc")
        
        oi_cc = c5.selectbox(
            "OI (Cuenta)", 
            ois, 
            format_func=lambda x: f"{x.oi_code} - {x.oi_name} ({x.mall.name if x.mall else 'Sin Mall'})", 
            key="oi_cc"
        )
        
        # --- NUEVO CAMPO: PAGAR A ---
        col_pay, col_txt = st.columns(2)
        pay_to_txt = col_pay.text_input("Pagar a:", key="pay_to_cc")
        txt_add = col_txt.text_input("Texto Adicional 2")
        
        # --- CORRECCIÓN AQUÍ TAMBIÉN: Usamos active_quotes ---
        act_cc = st.selectbox(
            "Actividad", 
            active_quotes,  # <--- ANTES DECÍA acts
            format_func=lambda x: f"{x.activity_name} ({x.mall.name if x.mall else 'Global'})", 
            key="act_cc"
        )
        
        if st.form_submit_button("💾 Guardar Caja Chica"):
            rate = get_active_rate(db)
            db.add(Expense(
                date=date_cc, year=date_cc.year, month=date_cc.month, 
                mall_id=act_cc.mall_id, oi_id=oi_cc.id, quote_id=act_cc.id, 
                category="CAJA_CHICA", description=f"Factura {fact_cc}", 
                amount_gtq=amount_cc, amount_usd=amount_cc/rate, 
                doc_number=fact_cc, company_id=prov_cc.id, 
                text_additional=txt_add,
                pay_to=pay_to_txt
            ))
            db.commit(); st.success("Guardado")

    st.divider()
    st.markdown("⬇️ **Reporte Contable Caja Chica**")
    
    col_d1, col_d2 = st.columns(2)
    start_d_cc = col_d1.date_input("Desde", datetime.date.today().replace(day=1), key="d1_cc")
    end_d_cc = col_d2.date_input("Hasta", datetime.date.today(), key="d2_cc")
    
    if st.button("Generar CSV Contable"):
        data_cc = db.query(Expense).filter(
            Expense.category=="CAJA_CHICA", 
            Expense.date >= start_d_cc, 
            Expense.date <= end_d_cc
        ).all()
        
        if data_cc:
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
                    "Pagar A": e.pay_to,
                    "Actividad": e.quote.activity_name
                })
            df_cc = pd.DataFrame(export_data)
            st.download_button("Descargar CSV Contable", df_cc.to_csv(index=False).encode('utf-8'), "caja_chica_contable.csv", "text/csv")
        else:
            st.warning("No hay gastos en ese rango de fechas.")

# --- PESTAÑA 3: HOST ---
def format_date_es(d):
    meses = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    return f"{d.day} de {meses[d.month]} de {d.year}"

with tab_host:
    st.header("🎤 Gestión de Talentos (Host)")

    # --- PASO 1: DATOS DEL TALENTO ---
    st.markdown("### 1️⃣ Ingresar Datos del Servicio")
    col_h1, col_h2 = st.columns(2)
    
    # Selección de Proveedor (Solo necesitamos cargarlos una vez, ya están en provs)
    prov_host = col_h1.selectbox("Seleccionar Talento (Proveedor)", provs, format_func=lambda x: x.name, key="prov_host")
    
    if prov_host:
        cui_actual = getattr(prov_host, 'cui', None)
        if cui_actual:
            col_h1.success(f"✅ CUI Verificado: {cui_actual}")
        else:
            col_h1.error("⚠️ Este talento NO tiene CUI registrado. Ve a Catálogos.")

    date_host = col_h2.date_input("Fecha de los Documentos", datetime.date.today(), key="date_host")
    contract_desc_form = st.text_input("Descripción Legal para el Contrato", placeholder="Ej: promoción de marca, conducción de evento, creación de contenido...")

    st.markdown("**Detalle de Cobros (Filas del Recibo)**")
    if "host_rows" not in st.session_state:
        st.session_state["host_rows"] = [{"desc": "", "rate": 0.0, "days": 0}]

    for idx, row in enumerate(st.session_state["host_rows"]):
        c_desc, c_rate, c_days, c_del = st.columns([3, 1, 1, 0.5])
        row["desc"] = c_desc.text_input(f"Servicio {idx+1}", value=row["desc"], placeholder="Descripción corta", key=f"hd_{idx}")
        row["rate"] = c_rate.number_input(f"Tarifa Q {idx+1}", value=row["rate"], step=50.0, key=f"hr_{idx}")
        row["days"] = c_days.number_input(f"Días/Cant {idx+1}", value=row["days"], step=1, key=f"hdy_{idx}")
        
        if c_del.button("🗑️", key=f"del_{idx}"):
            if len(st.session_state["host_rows"]) > 1:
                st.session_state["host_rows"].pop(idx)
                st.rerun()

    if len(st.session_state["host_rows"]) < 10:
        if st.button("➕ Agregar otra fila de cobro"):
            st.session_state["host_rows"].append({"desc": "", "rate": 0.0, "days": 0})
            st.rerun()

    total_host = sum([r["rate"] * r["days"] for r in st.session_state["host_rows"]])
    st.info(f"💰 **Total a Pagar: Q{total_host:,.2f}**")

    st.divider()

    # --- PASO 2: VINCULAR A ACTIVIDAD ---
    st.markdown("### 2️⃣ Registrar en Actividad")
    st.caption("Selecciona de dónde saldrá el dinero para pagar esto.")
    
    # --- CORRECCIÓN AQUÍ TAMBIÉN: Usamos active_quotes ---
    act_host_selection = st.selectbox(
        "Seleccionar Actividad (Presupuesto)", 
        active_quotes, 
        format_func=lambda x: f"{x.activity_name} | {x.mall.name if x.mall else 'Global'}", 
        key="act_host"
    )

    st.divider()

    # --- PASO 3: GENERAR DOCUMENTOS ---
    st.markdown("### 3️⃣ Generar y Descargar")
    
    form_valid = True
    if not prov_host or not getattr(prov_host, 'cui', None):
        st.warning("⚠️ Falta CUI del proveedor.")
        form_valid = False
    if not contract_desc_form:
        st.warning("⚠️ Falta la descripción legal.")
        form_valid = False
    if total_host <= 0:
        st.warning("⚠️ El monto total es 0.")
        form_valid = False

    if form_valid:
        if st.button("💾 REGISTRAR GASTO Y GENERAR ZIP", type="primary", use_container_width=True):
            # 1. Guardar en Base de Datos
            act_fresh = db.query(Quote).get(act_host_selection.id)
            rate = get_active_rate(db)
            oi_id_final = act_fresh.oi_id if act_fresh.oi_id else db.query(OI).first().id 
            
            new_exp = Expense(
                date=date_host, year=date_host.year, month=date_host.month, 
                mall_id=act_fresh.mall_id, oi_id=oi_id_final, quote_id=act_fresh.id,
                category="HOST", description=f"Host {prov_host.name} - {contract_desc_form}", 
                amount_gtq=total_host, amount_usd=total_host/rate,
                company_id=prov_host.id, host_details=st.session_state["host_rows"]
            )
            db.add(new_exp)
            db.commit()
            

            # 2. Generar PDF Recibo
            recibo_id_str = f"{new_exp.id:05d}"
            header_img_path = "header_spectrummedia.png"
            width, height = LETTER
            
            buff_recibo = io.BytesIO()
            p = canvas.Canvas(buff_recibo, pagesize=LETTER)
            if os.path.exists(header_img_path): p.drawImage(header_img_path, 0, height-100, width=width, height=100, preserveAspectRatio=False, mask='auto')
            else: p.setFillColor(colors.black); p.rect(0, height-80, width, 80, fill=1); p.setFillColor(colors.white); p.setFont("Helvetica-Bold", 24); p.drawString(50, height-50, "spectrum media")
            
            p.setFillColor(colors.white); p.setFont("Helvetica-Bold", 18); p.drawRightString(width - 50, height - 50, f"RECIBO #{recibo_id_str}")
            p.setFillColor(colors.black); p.setFont("Helvetica-Bold", 12); y = height - 130
            p.drawString(400, y, f"FECHA: {date_host.strftime('%d/%m/%Y')}")
            p.drawString(50, y, "RECIBO DE: SPECTRUM MEDIA LAB"); p.drawString(50, y-20, f"RECIBO PARA: {prov_host.name.upper()}")
            p.setFont("Helvetica", 10); p.drawString(50, y-60, f"Banco: {prov_host.bank_name}"); p.drawString(50, y-75, f"Nombre: {prov_host.name}"); p.drawString(50, y-90, f"Cuenta: {prov_host.account_number}")
            
            y_table = y - 140; p.setFont("Helvetica-Bold", 10)
            p.drawString(50, y_table, "DESCRIPCION"); p.drawString(350, y_table, "TARIFA"); p.drawString(420, y_table, "DIAS"); p.drawString(500, y_table, "TOTAL")
            p.line(50, y_table-5, 550, y_table-5)
            
            y_row = y_table - 25; p.setFont("Helvetica", 10)
            for row in st.session_state["host_rows"]:
                p.drawString(50, y_row, row["desc"])
                p.drawString(350, y_row, f"Q{row['rate']:,.2f}")
                p.drawString(430, y_row, str(row['days']))
                p.drawString(500, y_row, f"Q{row['rate']*row['days']:,.2f}")
                p.line(50, y_row-5, 550, y_row-5); y_row -= 25
            
            p.setFont("Helvetica-Bold", 14); p.drawString(50, y_row-20, "TOTAL PAGADO"); p.drawString(500, y_row-20, f"Q{total_host:,.2f}")
            p.line(200, 100, 400, 100); p.setFont("Helvetica", 8); p.drawCentredString(300, 85, "FIRMA DE CONFORMIDAD"); p.save(); buff_recibo.seek(0)

            # 3. Generar PDF Contrato (MODELO EXACTO SEGÚN REFERENCIA)
            buff_contrato = io.BytesIO()
            c = canvas.Canvas(buff_contrato, pagesize=LETTER)
            
            # --- Encabezado (Imagen superior) ---
            if os.path.exists(header_img_path):
                c.drawImage(header_img_path, 0, height-100, width=width, height=100, preserveAspectRatio=False, mask='auto')
            
            styles = getSampleStyleSheet()
            
            # --- Asunto y Fecha (Alineado a la derecha) ---
            style_right = ParagraphStyle(name='Right', parent=styles['Normal'], alignment=TA_RIGHT, fontSize=10, leading=14)
            fecha_str = format_date_es(date_host)
            p_asunto = Paragraph(f"<b>Asunto: Brand Activation Ambassador</b><br/><br/>En la fecha: <b>{fecha_str}</b>.", style_right)
            w, h = p_asunto.wrap(width - 100, 100)
            p_asunto.drawOn(c, 50, height - 160)
            
            # --- Cuerpo del Contrato (Justificado) ---
            style_justify = ParagraphStyle(name='Justify', parent=styles['Normal'], alignment=TA_JUSTIFY, fontSize=10, leading=14, spaceAfter=14)
            cui_val = getattr(prov_host, 'cui', 'N/A')
            
            txt_1 = f"Yo, <b>{prov_host.name}</b> me identifico con el Documento Personal de Identificación (DPI) con Código Único de Identificación (CUI) No. <b>{cui_val}</b>, por medio de la presente acuerdo prestar servicios como <b>BRAND ACTIVATION AMBASSADOR - {contract_desc_form.upper()}</b> para SPECTRUM MEDIA prestando un servicio y realizando actividades relacionadas con promoción de producto, eventos o generación de contenido, según lo asignado."
            
            txt_2 = f"Como compensación por estos servicios, se entregará un pago único de <b>Q.{total_host:,.2f}</b>, el día y lugar que me ha sido notificado previamente."
            
            txt_3 = "En consecuencia, ambas partes reconocen expresamente que:<br/>• No existe entre ellas relación laboral de ningún tipo, conforme a la legislación laboral vigente.<br/>• No se genera ninguna obligación de carácter laboral, tales como pago de salarios, prestaciones laborales, indemnizaciones, o cualquier otro derecho laboral que derive de una relación de trabajo subordinado.<br/>• Cada parte actúa de forma autónoma, sin que exista dependencia, ni vínculo permanente más allá del objeto del contrato de servicios."
            
            txt_4 = f"La presente notificación tiene como finalidad reiterar la naturaleza de la prestación de servicios, y dejar claro que no se establece, ni se presumirá, ningún tipo de vínculo laboral entre Spectrum Media y {prov_host.name}."
            
            # Dibujar los párrafos en orden calculando el alto dinámicamente
            y_curr = height - 210 
            for txt in [txt_1, txt_2, txt_3, txt_4]:
                p = Paragraph(txt, style_justify)
                w, h = p.wrap(width - 100, height)
                p.drawOn(c, 50, y_curr - h)
                y_curr -= (h + 16) # Espacio entre párrafos
            
            # --- ZONA DE FIRMAS (Centradas) ---
            center_x = width / 2
            style_center = ParagraphStyle(name='Center', parent=styles['Normal'], alignment=TA_CENTER, fontSize=9, leading=11)
            
            # 1. Línea y texto del Talento (Brand Ambassador)
            y_sig1_line = y_curr - 40
            c.setLineWidth(1)
            c.setStrokeColor(colors.black)
            c.line(center_x - 120, y_sig1_line, center_x + 120, y_sig1_line)
            
            p_sig1 = Paragraph(f"<b>Firma del Brand Ambassador</b><br/>{prov_host.name}", style_center)
            w, h = p_sig1.wrap(240, 50)
            p_sig1.drawOn(c, center_x - 120, y_sig1_line - h - 5)
            
            # 2. Insertar Imagen de la Firma (en medio)
            firma_img_path = "firma.png"
            y_sig2_line = y_sig1_line - 100 # Espacio hacia la segunda línea
            
            if os.path.exists(firma_img_path):
                img_w, img_h = 130, 60 # Tamaño aproximado de la firma
                img_x = center_x - (img_w / 2)
                img_y = y_sig2_line + 15 # Posicionada un poco por encima de la segunda línea
                c.drawImage(firma_img_path, img_x, img_y, width=img_w, height=img_h, mask='auto', preserveAspectRatio=True)
            
            # 3. Línea y texto de la Empresa
            c.line(center_x - 120, y_sig2_line, center_x + 120, y_sig2_line)
            
            p_sig2 = Paragraph("<b>Firma del responsable de la empresa:</b><br/>Maria Jose Aguilar, Product Executive", style_center)
            w, h = p_sig2.wrap(240, 50)
            p_sig2.drawOn(c, center_x - 120, y_sig2_line - h - 5)
            
            c.save()
            buff_contrato.seek(0)
            # 4. Crear ZIP y GUARDAR EN MEMORIA (st.session_state)
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.writestr(f"Recibo_{recibo_id_str}.pdf", buff_recibo.getvalue())
                zip_file.writestr(f"Contrato_{recibo_id_str}.pdf", buff_contrato.getvalue())
            
            # Guardamos los bytes del ZIP en la memoria de Streamlit
            st.session_state["zip_data_host"] = zip_buffer.getvalue()
            st.session_state["zip_name_host"] = f"Pack_Legal_{prov_host.name}_{recibo_id_str}.zip"
            
            st.success("✅ Gasto Registrado en Base de Datos y Documentos Listos")
            st.balloons()

    # --- BOTÓN DE DESCARGA: AFUERA del 'if st.button' ---
    # Solo se muestra si el ZIP ya está en memoria
    if "zip_data_host" in st.session_state:
        st.info("Tus documentos están listos para descargar:")
        st.download_button(
            label="⬇️ DESCARGAR DOCUMENTOS (CLICK AQUÍ)", 
            data=st.session_state["zip_data_host"], 
            file_name=st.session_state["zip_name_host"], 
            mime="application/zip",
            key="dl_btn_final"
        )