import streamlit as st
import pandas as pd
from database import get_db
from models import Quote, QuoteLine, ActivityType, Insumo, Mall
from auth import require_role
from services import calculate_quote_totals, get_active_rate

require_role(["VENDEDOR", "AUTORIZADO", "ADMIN"])
db = next(get_db())

st.title("Generador de Cotizaciones")

# --- SECCIÓN 1: CREAR NUEVA (DESDE CERO O PLANTILLA) ---
# Solo mostramos esto si no estamos editando una actualmente
if 'current_quote_id' not in st.session_state:
    
    # Pestañas para elegir método de creación
    tab1, tab2 = st.tabs(["✨ Crear desde Cero", "📂 Cargar Plantilla"])
    
    # --- OPCIÓN A: CREAR DESDE CERO ---
    with tab1:
        with st.expander("Detalles de la Nueva Actividad", expanded=True):
            activity_types = db.query(ActivityType).filter(ActivityType.is_active==True).all()
            malls = db.query(Mall).filter(Mall.is_active==True).all()
            
            c_name, c_type = st.columns(2)
            act_name = c_name.text_input("Nombre de la Actividad")
            
            if not activity_types:
                st.error("⚠️ No hay Tipos de Actividad. Contacta al Admin.")
                act_type = None
            else:
                act_type = c_type.selectbox("Tipo", options=activity_types, format_func=lambda x: x.name)
                if act_type and act_type.description:
                    st.info(f"ℹ️ **{act_type.name}:** {act_type.description}")

            c_mall, c_note = st.columns(2)
            mall = c_mall.selectbox("Mall (Opcional)", options=[None] + malls, format_func=lambda x: x.name if x else "Sin asignar")
            notes = c_note.text_area("Notas")
            
            if st.button("🚀 Crear Nuevo Borrador"):
                if act_type:
                    new_quote = Quote(created_by=st.session_state["user_id"], activity_name=act_name, activity_type_id=act_type.id, mall_id=mall.id if mall else None, notes=notes)
                    db.add(new_quote)
                    db.commit()
                    st.session_state['current_quote_id'] = new_quote.id
                    st.success("Creado. Ahora agrega los insumos.")
                    st.rerun()

    # --- OPCIÓN B: USAR PLANTILLA ---
    with tab2:
        st.markdown("##### Selecciona una plantilla para iniciar")
        templates = db.query(Quote).filter(Quote.status == "PLANTILLA").all()
        
        if not templates:
            st.info("No hay plantillas guardadas aún. Crea una cotización y guárdala como plantilla.")
        else:
            c_temp, c_new_name = st.columns(2)
            sel_template_preview = c_temp.selectbox("Elegir Plantilla", templates, format_func=lambda x: f"{x.activity_name} (Total: ${x.total_cost_usd:,.2f})")
            new_name_from_temp = c_new_name.text_input("Nombre para esta nueva cotización", value=f"Copia de {sel_template_preview.activity_name}")
            
            if st.button("⚡ Crear usando esta Plantilla"):
                # TRUCO: Volvemos a cargar la plantilla con la sesión ACTUAL para evitar el error "DetachedInstance"
                sel_template = db.query(Quote).get(sel_template_preview.id)
                
                # 1. Duplicar Cabecera
                cloned_quote = Quote(
                    created_by=st.session_state["user_id"],
                    activity_name=new_name_from_temp,
                    activity_type_id=sel_template.activity_type_id,
                    mall_id=sel_template.mall_id,
                    notes=sel_template.notes,
                    status="BORRADOR", # Nace como borrador editable
                    total_cost_gtq=sel_template.total_cost_gtq,
                    total_cost_usd=sel_template.total_cost_usd,
                    suggested_price_usd_m70=sel_template.suggested_price_usd_m70,
                    suggested_price_usd_m60=sel_template.suggested_price_usd_m60,
                    suggested_price_usd_m50=sel_template.suggested_price_usd_m50
                )
                db.add(cloned_quote)
                db.commit()
                
                # 2. Duplicar Líneas (Ahora sí funcionará porque sel_template está fresco)
                if sel_template.lines:
                    for l in sel_template.lines:
                        new_line = QuoteLine(
                            quote_id=cloned_quote.id,
                            insumo_id=l.insumo_id,
                            qty_personas=l.qty_personas,
                            units_value=l.units_value,
                            line_cost_gtq=l.line_cost_gtq,
                            line_cost_usd=l.line_cost_usd
                        )
                        db.add(new_line)
                    db.commit()
                
                # 3. Entrar a editar
                st.session_state['current_quote_id'] = cloned_quote.id
                st.success("¡Plantilla cargada exitosamente!")
                st.rerun()

# --- SECCIÓN 2: EDICIÓN DE COTIZACIÓN ACTIVA ---
if 'current_quote_id' in st.session_state:
    q_id = st.session_state['current_quote_id']
    quote = db.query(Quote).get(q_id)
    
    # Validación por si se borró
    if not quote:
        del st.session_state['current_quote_id']
        st.rerun()

    st.divider()
    
    # Encabezado Editable
    col_tit, col_back = st.columns([4, 1])
    col_tit.subheader(f"🛠️ Editando: {quote.activity_name} (#{quote.id})")
    if col_back.button("🔙 Salir / Volver"):
        del st.session_state['current_quote_id']
        st.rerun()
    
    # SOLO SI ESTÁ EN BORRADOR PERMITIMOS AGREGAR/EDITAR
    if quote.status == "BORRADOR":
        
        # 2.1 AGREGAR NUEVO INSUMO
        with st.container():
            c_i, c_q, c_u, c_b = st.columns([3, 1, 1, 1])
            insumos = db.query(Insumo).filter(Insumo.is_active==True).all()
            
            if insumos:
                sel_ins = c_i.selectbox("Seleccionar Insumo", insumos, format_func=lambda x: f"{x.name} (Q{x.cost_gtq})")
                qty = c_q.number_input("Personas", min_value=1, value=1, step=1, format="%d")
                
                u_val = 1
                if sel_ins.billing_mode == "MULTIPLICABLE":
                    u_val = c_u.number_input(f"Cant. {sel_ins.unit_type}", min_value=1, value=1, step=1, format="%d")
                else:
                    c_u.info("Cobro fijo")
                    
                if c_b.button("➕ Agregar"):
                    cost = (sel_ins.cost_gtq * qty * u_val) if sel_ins.billing_mode == "MULTIPLICABLE" else (sel_ins.cost_gtq * qty)
                    rate = get_active_rate(db)
                    line = QuoteLine(quote_id=quote.id, insumo_id=sel_ins.id, qty_personas=qty, units_value=u_val, line_cost_gtq=cost, line_cost_usd=cost/rate)
                    db.add(line)
                    db.commit()
                    calculate_quote_totals(db, quote.id)
                    st.rerun()

        # 2.2 TABLA EDITABLE (MODIFICAR / BORRAR)
        st.markdown("##### 📝 Listado de Elementos")
        
        lines = quote.lines
        if lines:
            data_lines = []
            for i, l in enumerate(lines, start=1):
                data_lines.append({
                    "id": l.id,
                    "No.": i,
                    "Insumo": l.insumo.name,
                    "Personas": int(l.qty_personas),
                    "Unidades": int(l.units_value),
                    "Costo USD": l.line_cost_usd,
                    "Borrar": False
                })
            
            df_lines = pd.DataFrame(data_lines)
            
            edited_df = st.data_editor(
                df_lines,
                column_config={
                    "id": None, 
                    "No.": st.column_config.NumberColumn("Item", width="small", disabled=True),
                    "Insumo": st.column_config.TextColumn(disabled=True),
                    "Personas": st.column_config.NumberColumn("Personas", min_value=1, step=1, required=True),
                    "Unidades": st.column_config.NumberColumn("Cant. Unidades", min_value=1, step=1, required=True),
                    "Costo USD": st.column_config.NumberColumn(disabled=True, format="$%.2f"),
                    "Borrar": st.column_config.CheckboxColumn("¿Eliminar?", help="Marca para borrar esta línea")
                },
                hide_index=True,
                use_container_width=True,
                key="editor_lines"
            )
            
            if st.button("🔄 Aplicar Cambios (Editar/Borrar)"):
                rate = get_active_rate(db)
                records = edited_df.to_dict('records')
                changes_made = False
                for row in records:
                    line_obj = db.query(QuoteLine).get(row['id'])
                    if line_obj:
                        if row['Borrar']:
                            db.delete(line_obj)
                            changes_made = True
                        else:
                            new_qty = float(row['Personas'])
                            new_units = float(row['Unidades'])
                            if line_obj.qty_personas != new_qty or line_obj.units_value != new_units:
                                line_obj.qty_personas = new_qty
                                line_obj.units_value = new_units
                                insumo = line_obj.insumo
                                cost_gtq = (insumo.cost_gtq * new_qty * new_units) if insumo.billing_mode == "MULTIPLICABLE" else (insumo.cost_gtq * new_qty)
                                line_obj.line_cost_gtq = cost_gtq
                                line_obj.line_cost_usd = cost_gtq / rate
                                changes_made = True
                
                if changes_made:
                    db.commit()
                    calculate_quote_totals(db, quote.id)
                    st.success("Cambios aplicados.")
                    st.rerun()

        # 2.3 TOTALES Y ACCIONES
        st.divider()
        st.markdown(f"### Total Costo: ${quote.total_cost_usd:,.2f}")
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Sugerido (70%)", f"${quote.suggested_price_usd_m70:,.2f}")
        k2.metric("Sugerido (60%)", f"${quote.suggested_price_usd_m60:,.2f}")
        k3.metric("Sugerido (50%)", f"${quote.suggested_price_usd_m50:,.2f}")
        
        st.divider()
        
        # --- ZONA DE ACCIONES (ENVIAR O GUARDAR PLANTILLA) ---
        col_template, col_send = st.columns([1, 1])
        
        # BOTÓN 1: GUARDAR COMO PLANTILLA
        with col_template:
            with st.expander("💾 Guardar como Plantilla"):
                temp_name = st.text_input("Nombre de la Plantilla", value=quote.activity_name)
                if st.button("Confirmar Guardado de Plantilla"):
                    # Clonamos como Status = PLANTILLA
                    template_quote = Quote(
                        created_by=st.session_state["user_id"],
                        activity_name=temp_name,
                        activity_type_id=quote.activity_type_id,
                        mall_id=quote.mall_id,
                        notes=quote.notes,
                        status="PLANTILLA", # <--- ESTE ES EL TRUCO
                        total_cost_gtq=quote.total_cost_gtq,
                        total_cost_usd=quote.total_cost_usd,
                        suggested_price_usd_m70=quote.suggested_price_usd_m70,
                        suggested_price_usd_m60=quote.suggested_price_usd_m60,
                        suggested_price_usd_m50=quote.suggested_price_usd_m50
                    )
                    db.add(template_quote)
                    db.commit()
                    
                    # Clonamos líneas
                    for l in quote.lines:
                        db.add(QuoteLine(
                            quote_id=template_quote.id,
                            insumo_id=l.insumo_id,
                            qty_personas=l.qty_personas,
                            units_value=l.units_value,
                            line_cost_gtq=l.line_cost_gtq,
                            line_cost_usd=l.line_cost_usd
                        ))
                    db.commit()
                    st.success(f"¡Plantilla '{temp_name}' guardada! La encontrarás en la pestaña 'Cargar Plantilla' al inicio.")

        # BOTÓN 2: ENVIAR A APROBACIÓN
        with col_send:
            st.write("") # Espacio
            st.write("") 
            if st.button("📤 ENVIAR A APROBACIÓN", type="primary", use_container_width=True):
                if not quote.lines:
                    st.error("Cotización vacía.")
                else:
                    quote.status = "ENVIADA"
                    db.commit()
                    del st.session_state['current_quote_id']
                    st.balloons()
                    st.success("¡Enviada al administrador!")
                    st.rerun()

    else:
        # VISTA DE LECTURA
        st.info(f"Estado: **{quote.status}**. No editable.")
        lines = quote.lines
        if lines:
            data = [{"Insumo": l.insumo.name, "Cant": l.qty_personas, "Unidades": l.units_value, "Costo USD": f"${l.line_cost_usd:.2f}"} for l in lines]
            st.dataframe(pd.DataFrame(data), use_container_width=True)
            st.markdown(f"**Total USD: ${quote.total_cost_usd:,.2f}**")