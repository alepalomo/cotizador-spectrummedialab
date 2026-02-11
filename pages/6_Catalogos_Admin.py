import streamlit as st
import pandas as pd
from database import get_db
from models import Insumo, Mall, ActivityType, Company, OI, User
from auth import require_role, hash_password

require_role(["ADMIN", "AUTORIZADO"])
db = next(get_db())

st.title("Administración de Catálogos (Editable)")
st.info("💡 Tip: Edita los datos directamente en las tablas y presiona 'Guardar Cambios'.")

# AHORA SON 5 PESTAÑAS
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Insumos", "Malls & OIs", "Tipos Actividad", "Usuarios", "🏢 Proveedores"])

# --- FUNCIÓN AUXILIAR ---
def save_changes_generic(model, df_edited, id_col='id'):
    try:
        records = df_edited.to_dict('records')
        for row in records:
            obj_id = row.get(id_col)
            obj = db.query(model).get(obj_id)
            if obj:
                for key, value in row.items():
                    if hasattr(obj, key):
                        setattr(obj, key, value)
        db.commit()
        st.success("¡Cambios guardados correctamente!")
        st.rerun()
    except Exception as e:
        st.error(f"Error al guardar: {e}")

# --- TAB 1: INSUMOS ---
with tab1:
    st.markdown("### 📤 Carga Masiva de Insumos")
    uploaded_insumos = st.file_uploader("Subir CSV de Insumos", type=["csv"], key="csv_insumos")

    if uploaded_insumos:
        df_insumos = pd.read_csv(uploaded_insumos)
        # Estandarizamos nombres de columnas para evitar errores
        df_insumos.columns = [c.lower().strip() for c in df_insumos.columns]

        st.write("Vista previa de datos a cargar:", df_insumos.head())
    
        if st.button("🚀 Procesar Carga Insumos"):
            # 1. Obtener nombres existentes para no duplicar
            existing_names = {i.name for i in db.query(Insumo).all()}
            new_objects = []
            skipped_count = 0

            for index, row in df_insumos.iterrows():
                name_val = str(row['name']).strip()

                # 2. Verificar si ya existe
                if name_val in existing_names:
                    skipped_count += 1
                    continue # Salta al siguiente

                # 3. Crear objeto si es nuevo
                new_obj = Insumo(
                    name=name_val,
                    unit_type=row.get('unit_type', 'UNIDAD'), # Valor por defecto si falta
                    cost_gtq=float(row.get('cost_gtq', 0.0)),
                    billing_mode=row.get('billing_mode', 'MULTIPLICABLE')
                )
                new_objects.append(new_obj)
                # Agregamos al set temporal para evitar duplicados dentro del mismo CSV
                existing_names.add(name_val)

            if new_objects:
                db.add_all(new_objects)
                db.commit()
                st.success(f"✅ Se agregaron {len(new_objects)} nuevos insumos.")

            if skipped_count > 0:
                st.warning(f"⚠️ Se omitieron {skipped_count} insumos porque ya existían.")

    with st.expander("➕ Crear Nuevo Insumo"):
        with st.form("add_ins"):
            c1, c2, c3, c4 = st.columns(4)
            name = c1.text_input("Nombre")
            cost = c2.number_input("Costo GTQ", min_value=0.0)
            mode = c3.selectbox("Modo", ["MULTIPLICABLE", "POR_ACTIVIDAD"])
            unit = c4.selectbox("Unidad", ["HORA", "DIA", "UNIDAD"])
            if st.form_submit_button("Agregar"):
                try: db.add(Insumo(name=name, unit_type=unit, cost_gtq=cost, billing_mode=mode)); db.commit(); st.rerun()
                except: st.error("Error: Duplicado")
    
    insumos = db.query(Insumo).all()
    if insumos:
        df = pd.DataFrame([{"id": i.id, "name": i.name, "cost_gtq": i.cost_gtq, "unit_type": i.unit_type, "billing_mode": i.billing_mode} for i in insumos])
        edited_df = st.data_editor(df, column_config={"id": st.column_config.NumberColumn(disabled=True), "billing_mode": st.column_config.SelectboxColumn(options=["MULTIPLICABLE", "POR_ACTIVIDAD"]), "unit_type": st.column_config.SelectboxColumn(options=["HORA", "DIA", "UNIDAD"])}, hide_index=True, key="ed_ins")
        if st.button("Guardar Insumos"): save_changes_generic(Insumo, edited_df)

# --- TAB 2: MALLS Y OIS ---
with tab2:
    col_m, col_o = st.columns(2)
    with col_m:
        st.subheader("Malls")
        with st.expander("➕ Nuevo Mall"):
            nm = st.text_input("Nombre Mall")
            if st.button("Crear Mall"): db.add(Mall(name=nm)); db.commit(); st.rerun()
        ms = db.query(Mall).all()
        if ms:
            ed_m = st.data_editor(pd.DataFrame([{"id": m.id, "name": m.name} for m in ms]), hide_index=True, key="ed_m")
            if st.button("Guardar Malls"): save_changes_generic(Mall, ed_m)

    with col_o:
        st.subheader("OIs")
        with st.expander("➕ Nueva OI"):
            malls_objs = db.query(Mall).all()
            if malls_objs:
                sm = st.selectbox("Mall", malls_objs, format_func=lambda x: x.name)
                oc = st.text_input("Código")
                on = st.text_input("Nombre")
                ob = st.number_input("Presupuesto Anual", min_value=0.0)
                if st.button("Crear OI"): db.add(OI(mall_id=sm.id, oi_code=oc, oi_name=on, annual_budget_usd=ob)); db.commit(); st.rerun()
        
        # Carga CSV OIs
        with st.expander("📂 Carga Masiva OIs (CSV)"):
            uploaded_oi = st.file_uploader("Sube CSV (Mall, Codigo, Nombre, Presupuesto)", type=["csv", "xlsx"])
            if uploaded_oi and st.button("Procesar Archivo"):
                try:
                    df_load = pd.read_csv(uploaded_oi) if uploaded_oi.name.endswith('.csv') else pd.read_excel(uploaded_oi)
                    existing_malls = {m.name: m.id for m in db.query(Mall).all()}
                    count = 0
                    for _, row in df_load.iterrows():
                        if str(row['Mall']).strip() in existing_malls:
                            db.add(OI(mall_id=existing_malls[str(row['Mall']).strip()], oi_code=str(row['Codigo']), oi_name=str(row['Nombre']), annual_budget_usd=float(row['Presupuesto'])))
                            count += 1
                    db.commit(); st.success(f"{count} OIs cargadas."); st.rerun()
                except Exception as e: st.error(f"Error: {e}")

        # Tabla OIs
        ois = db.query(OI).all()
        malls_map = {m.name: m.id for m in db.query(Mall).all()}
        if ois:
            data_ois = [{"id": o.id, "mall_name": next((name for name, id_ in malls_map.items() if id_ == o.mall_id), "Sin Asignar"), "oi_code": o.oi_code, "oi_name": o.oi_name, "annual_budget_usd": o.annual_budget_usd} for o in ois]
            ed_o = st.data_editor(pd.DataFrame(data_ois), column_config={"id": st.column_config.NumberColumn(disabled=True, width="small"), "mall_name": st.column_config.SelectboxColumn("Mall", options=list(malls_map.keys()), required=True)}, hide_index=True, key="ed_ois")
            if st.button("Guardar OIs"):
                try:
                    for row in ed_o.to_dict('records'):
                        obj = db.query(OI).get(row['id'])
                        if obj:
                            obj.oi_code = row['oi_code']; obj.oi_name = row['oi_name']; obj.annual_budget_usd = row['annual_budget_usd']
                            if row['mall_name'] in malls_map: obj.mall_id = malls_map[row['mall_name']]
                    db.commit(); st.rerun()
                except Exception as e: st.error(str(e))

# --- TAB 3: ACTIVIDADES ---
with tab3:
    with st.expander("➕ Nueva Actividad", expanded=True):
        with st.form("na"):
            n = st.text_input("Nombre"); d = st.text_area("Descripción")
            if st.form_submit_button("Crear"): db.add(ActivityType(name=n, description=d)); db.commit(); st.rerun()
    acts = db.query(ActivityType).all()
    if acts:
        ed_a = st.data_editor(pd.DataFrame([{"id": a.id, "name": a.name, "description": a.description} for a in acts]), column_config={"id": st.column_config.NumberColumn(disabled=True, width="small")}, hide_index=True, key="ed_a")
        if st.button("Guardar Diccionario"): save_changes_generic(ActivityType, ed_a)

# --- TAB 4: USUARIOS ---
with tab4:
    with st.form("nu"):
        u = st.text_input("Usuario"); p = st.text_input("Password", type="password"); r = st.selectbox("Rol", ["VENDEDOR", "AUTORIZADO", "ADMIN"])
        if st.form_submit_button("Crear"): 
            try: db.add(User(username=u, password_hash=hash_password(p), role=r)); db.commit(); st.success("Ok")
            except: st.error("Error")

# --- TAB 5: PROVEEDORES ---
with tab5:
    st.subheader("🏢 Catálogo de Proveedores Detallado")
    
    with st.expander("➕ Agregar Nuevo Proveedor", expanded=True):
        with st.form("new_prov_form"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Nombre Comercial")
            legal = c2.text_input("Razón Social")
            
            c3, c4 = st.columns(2)
            p_type = c3.selectbox("Tipo", ["Certificado", "Directo"])
            nit = c4.text_input("NIT")
            
            # NUEVO CAMPO CUI EN EL FORMULARIO
            c_cui, c_vacio = st.columns(2)
            cui_val = c_cui.text_input("CUI (DPI)")
            
            c5, c6 = st.columns(2)
            bank = c5.text_input("Banco")
            acc = c6.text_input("No. de Cuenta")
            
            if st.form_submit_button("Guardar Proveedor"):
                if name:
                    try:
                        db.add(Company(
                            name=name, legal_name=legal, provider_type=p_type,
                            nit=nit, bank_name=bank, account_number=acc, cui=cui_val
                        ))
                        db.commit()
                        st.success("Proveedor agregado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("El nombre es obligatorio.")

    st.divider()
    
    # Tabla editable completa
    companies = db.query(Company).all()
    if companies:
        data_c = []
        for c in companies:
            data_c.append({
                "id": c.id,
                "name": c.name,
                "legal_name": c.legal_name,
                "provider_type": c.provider_type,
                "nit": c.nit,
                "cui": c.cui, # Mostrar CUI
                "bank_name": c.bank_name,
                "account_number": c.account_number
            })
        
        df_comp = pd.DataFrame(data_c)
        edited_comps = st.data_editor(
            df_comp,
            column_config={
                "id": st.column_config.NumberColumn(disabled=True, width="small"),
                "name": "Nombre Comercial",
                "legal_name": "Razón Social",
                "provider_type": st.column_config.SelectboxColumn("Tipo", options=["Certificado", "Directo"]),
                "nit": "NIT",
                "cui": "CUI (DPI)",
                "bank_name": "Banco",
                "account_number": "Cuenta"
            },
            hide_index=True,
            key="editor_companies",
            num_rows="dynamic"
        )
        
        if st.button("Guardar Cambios Proveedores"):
            save_changes_generic(Company, edited_comps)