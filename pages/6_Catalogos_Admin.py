import streamlit as st
import pandas as pd
from database import get_db
from models import Insumo, Mall, ActivityType, Company, OI, User
from auth import require_role, hash_password
import bcrypt
import streamlit as st
from database import engine
from models import Base

require_role(["ADMIN", "AUTORIZADO"])
db = next(get_db())

with st.sidebar:
    st.divider()
    st.error("⚠️ ZONA DE PELIGRO")
    if st.button("☢️ HARD RESET DB (Borrar Todo)", type="primary"):
        try:
            # 1. Borra las tablas viejas en la nube
            Base.metadata.drop_all(bind=engine)
            
            # 2. Crea las tablas nuevas (con category y description)
            Base.metadata.create_all(bind=engine)
            
            st.success("✅ ¡Base de datos en la nube reseteada!")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

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
    # DEFINIMOS LAS CATEGORÍAS FIJAS (Puedes editar esta lista a tu gusto)
    CATEGORIAS_OPCIONES = ["Bebidas", "Comida", "Decoración", "Entretenimiento", "Extras", "Logos", "Mantenimiento", "Mobiliario", "Pantallas", "Personal", "Servicio", "Sticker"]

    st.markdown("### 📤 Carga Masiva de Insumos")
    uploaded_insumos = st.file_uploader("Subir CSV de Insumos", type=["csv"], key="csv_insumos")

    if uploaded_insumos:
        # --- LÓGICA DE LECTURA ROBUSTA (UTF-8 y LATIN-1) ---
        try:
            # Intento 1: Leer normal (UTF-8 y coma)
            df_insumos = pd.read_csv(uploaded_insumos)
            
            # Chequeo de Separador: Si solo detectó 1 columna, seguro era punto y coma
            if df_insumos.shape[1] < 2:
                uploaded_insumos.seek(0)
                df_insumos = pd.read_csv(uploaded_insumos, sep=';')

        except UnicodeDecodeError:
            # Intento 2: Si falla por tildes/ñ, probamos codificación 'latin-1' (Excel Español)
            uploaded_insumos.seek(0)
            try:
                df_insumos = pd.read_csv(uploaded_insumos, encoding='latin-1')
                if df_insumos.shape[1] < 2:
                    uploaded_insumos.seek(0)
                    df_insumos = pd.read_csv(uploaded_insumos, sep=';', encoding='latin-1')
            except Exception as e:
                st.error(f"❌ Error leyendo formato 'Latin-1': {e}")
                st.stop()
                
        except Exception as e:
            # Si es otro error, lo mostramos explícitamente para saber qué es
            st.error(f"❌ Error técnico: {e}")
            st.stop()

        # --- A PARTIR DE AQUÍ SIGUE TU CÓDIGO NORMAL DE NORMALIZACIÓN ---
        # Normalizar columnas (minúsculas y sin espacios)
        df_insumos.columns = [c.lower().strip() for c in df_insumos.columns]        
        # --- MAPEO INTELIGENTE (ESPAÑOL -> INGLÉS) ---
        rename_map = {
            'nombre': 'name', 'insumo': 'name', 'item': 'name',
            'costo': 'cost_gtq', 'precio': 'cost_gtq', 'cost': 'cost_gtq',
            'unidad': 'unit_type', 'medida': 'unit_type', 'tipo': 'unit_type',
            'cobro': 'billing_mode', 'modo': 'billing_mode',
            # NUEVOS CAMPOS
            'categoria': 'category', 'cat': 'category',
            'descripcion': 'description', 'detalle': 'description', 'desc': 'description'
        }
        df_insumos.rename(columns=rename_map, inplace=True)
        
        st.write("Columnas detectadas:", df_insumos.columns.tolist()) # Para depuración
        st.dataframe(df_insumos.head())
        
        # Verificación de columna obligatoria
        if 'name' not in df_insumos.columns:
            st.error("❌ Error: No se encuentra la columna 'Nombre' o 'Name'. Revisa tu archivo.")
        else:
            if st.button("🚀 Procesar Carga Insumos"):
                existing_names = {i.name for i in db.query(Insumo).all()}
                new_objects = []
                skipped_count = 0
                
                for index, row in df_insumos.iterrows():
                    name_val = str(row['name']).strip()
                    
                    if name_val in existing_names or name_val == "nan":
                        skipped_count += 1
                        continue 
                    
                    # Manejo seguro de valores numéricos
                    try:
                        cost_val = float(str(row.get('cost_gtq', 0)).replace(',', '').replace('Q', ''))
                    except:
                        cost_val = 0.0

                    # Limpieza de textos nuevos
                    cat_val = row.get('category', None)
                    if pd.isna(cat_val): cat_val = "Varios" # Default si no trae
                    
                    desc_val = row.get('description', "")
                    if pd.isna(desc_val): desc_val = ""

                    new_obj = Insumo(
                        name=name_val,
                        unit_type=row.get('unit_type', 'UNIDAD'), 
                        cost_gtq=cost_val,
                        billing_mode=row.get('billing_mode', 'MULTIPLICABLE'),
                        category=str(cat_val),        # <--- NUEVO
                        description=str(desc_val)     # <--- NUEVO
                    )
                    new_objects.append(new_obj)
                    existing_names.add(name_val) 

                if new_objects:
                    db.add_all(new_objects)
                    db.commit()
                    st.success(f"✅ Se agregaron {len(new_objects)} nuevos insumos.")
                
                if skipped_count > 0:
                    st.warning(f"⚠️ Se omitieron {skipped_count} insumos (ya existían o vacíos).")


    with st.expander("➕ Crear Nuevo Insumo"):
        with st.form("add_ins"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Nombre")
            cat = c2.selectbox("Categoría", CATEGORIAS_OPCIONES) # <--- NUEVO
            
            c3, c4, c5 = st.columns(3)
            cost = c3.number_input("Costo GTQ", min_value=0.0)
            mode = c4.selectbox("Modo", ["MULTIPLICABLE", "POR_ACTIVIDAD"])
            unit = c5.selectbox("Unidad", ["HORA", "DIA", "UNIDAD"])
            
            desc = st.text_area("Descripción (Opcional)") # <--- NUEVO

            if st.form_submit_button("Agregar"):
                try: 
                    # AGREGAMOS LOS CAMPOS NUEVOS AL OBJETO
                    db.add(Insumo(
                        name=name, 
                        unit_type=unit, 
                        cost_gtq=cost, 
                        billing_mode=mode,
                        category=cat,
                        description=desc
                    )) 
                    db.commit()
                    st.success("Agregado exitosamente")
                    st.rerun()
                except Exception as e: 
                    st.error(f"Error: {e}")
    
    st.markdown("### ✏️ Editor de Insumos")
    st.caption("Puedes agregar filas nuevas al final o borrar seleccionando la fila y presionando la tecla 'Supr' o el ícono de basurero.")

    # 1. Cargar datos actuales
    insumos_list = db.query(Insumo).order_by(Insumo.id).all()
    # Guardamos los IDs originales para saber cuáles se borraron después
    ids_originales = {i.id for i in insumos_list}
    
    df_insumos = pd.DataFrame([
        {
            "id": i.id,
            "name": i.name,
            "category": i.category,       # <--- NUEVO
            "description": i.description, # <--- NUEVO
            "cost_gtq": float(i.cost_gtq),
            "unit_type": i.unit_type,
            "billing_mode": i.billing_mode
        }
        for i in insumos_list
    ])

    # 2. Configurar el Editor
    column_cfg_ins = {
        "id": st.column_config.NumberColumn(disabled=True, width="small"), 
        "name": st.column_config.TextColumn("Insumo/Servicio", required=True, width="medium"),
        "cost_gtq": st.column_config.NumberColumn("Costo Q", min_value=0, format="Q%.2f", width="small"),
        "unit_type": st.column_config.SelectboxColumn("Unidad", options=["UNIDAD", "DIA", "GLOBAL", "HORA"], required=True, width="small"),
        "billing_mode": st.column_config.SelectboxColumn("Modo Cobro", options=["MULTIPLICABLE", "FIJO"], required=True, width="small"),
        # CONFIGURACIÓN DE LAS NUEVAS COLUMNAS
        "category": st.column_config.SelectboxColumn(
            "Categoría", 
            options=CATEGORIAS_OPCIONES, 
            required=False, 
            width="medium"
        ),
        "description": st.column_config.TextColumn(
            "Descripción", 
            width="large",
            help="Texto que aparecerá abajo del insumo al cotizar"
        )
    }

    edited_insumos = st.data_editor(
        df_insumos, 
        column_config=column_cfg_ins, 
        num_rows="dynamic", 
        hide_index=True, 
        use_container_width=True,
        key="editor_insumos_main"
    )

    # 3. Lógica Inteligente de Guardado
    if st.button("💾 Guardar Cambios (Insumos)"):
        # A. DETECTAR BORRADOS
        ids_remanentes = set(edited_insumos["id"].dropna().astype(int).tolist())
        ids_a_borrar = ids_originales - ids_remanentes
        
        deleted_count = 0
        if ids_a_borrar:
            db.query(Insumo).filter(Insumo.id.in_(ids_a_borrar)).delete(synchronize_session=False)
            deleted_count = len(ids_a_borrar)

        # B. DETECTAR NUEVOS Y EDICIONES
        updated_count = 0
        new_count = 0
        
        for index, row in edited_insumos.iterrows():
            # Si tiene ID (y no es NaN), es una edición
            if pd.notna(row["id"]):
                item = db.query(Insumo).get(int(row["id"]))
                if item:
                    item.name = row["name"]
                    item.cost_gtq = row["cost_gtq"]
                    item.unit_type = row["unit_type"]
                    item.billing_mode = row["billing_mode"]
                    # ACTUALIZAR NUEVOS CAMPOS
                    item.category = row.get("category")
                    item.description = row.get("description")
                    updated_count += 1
            # Si NO tiene ID (es NaN), es un registro NUEVO
            else:
                new_item = Insumo(
                    name=row["name"],
                    cost_gtq=row["cost_gtq"],
                    unit_type=row["unit_type"],
                    billing_mode=row["billing_mode"],
                    # INSERTAR NUEVOS CAMPOS
                    category=row.get("category"),
                    description=row.get("description")
                )
                db.add(new_item)
                new_count += 1
        
        db.commit()
        
        msg = "✅ Procesado: "
        if deleted_count: msg += f"🗑️ {deleted_count} borrados. "
        if new_count: msg += f"✨ {new_count} nuevos. "
        if updated_count: msg += f"✏️ {updated_count} actualizados."
        
        st.success(msg)
        st.rerun()

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
    st.markdown("### 📤 Carga Masiva de Tipos de Actividad")
    uploaded_types = st.file_uploader("Subir CSV de Tipos", type=["csv"], key="csv_types")

    if uploaded_types:
        try:
            df_types = pd.read_csv(uploaded_types)
            if df_types.shape[1] < 2:
                uploaded_types.seek(0)
                df_types = pd.read_csv(uploaded_types, sep=';')
        except:
            st.error("Error leyendo el archivo. Asegúrate que sea un CSV válido.")
            st.stop()

        # Normalizar encabezados
        df_types.columns = [c.lower().strip() for c in df_types.columns]
        
        # MAPEO INTELIGENTE (Español -> Inglés)
        rename_map = {
            'nombre': 'name', 'tipo': 'name', 'actividad': 'name',
            'descripcion': 'description', 'descripción': 'description', 'detalle': 'description'
        }
        df_types.rename(columns=rename_map, inplace=True)
        
        st.write("Columnas detectadas:", df_types.columns.tolist())
        
        if 'name' not in df_types.columns:
            st.error("❌ Error: Falta la columna 'Nombre' o 'Tipo'.")
        else:
            if st.button("🚀 Procesar Carga Tipos"):
                existing_types = {t.name for t in db.query(ActivityType).all()}
                new_types = []
                skipped = 0
                
                for index, row in df_types.iterrows():
                    name_val = str(row['name']).strip()
                    
                    if name_val in existing_types or name_val == "nan" or name_val == "":
                        skipped += 1
                        continue
                    
                    desc_val = str(row.get('description', ''))
                    if desc_val == "nan": desc_val = ""

                    new_obj = ActivityType(
                        name=name_val,
                        description=desc_val
                    )
                    new_types.append(new_obj)
                    existing_types.add(name_val)

                if new_types:
                    db.add_all(new_types)
                    db.commit()
                    st.success(f"✅ Se agregaron {len(new_types)} nuevos tipos.")
                
                if skipped > 0:
                    st.warning(f"⚠️ Se omitieron {skipped} tipos duplicados.")

    with st.expander("➕ Nueva Actividad", expanded=True):
        with st.form("na"):
            n = st.text_input("Nombre"); d = st.text_area("Descripción")
            if st.form_submit_button("Crear"): db.add(ActivityType(name=n, description=d)); db.commit(); st.rerun()
    acts = db.query(ActivityType).all()
    
    st.markdown("### ✏️ Editor de Tipos de Actividad")
    # 1. Cargar datos y guardar IDs originales para detectar borrados
    types_list = db.query(ActivityType).order_by(ActivityType.id).all()
    ids_originales_t = {t.id for t in types_list}
    
    df_types = pd.DataFrame([
        {
            "id": t.id,
            "name": t.name,
            "description": t.description
        } 
        for t in types_list
    ])

    # 2. Configurar Editor con num_rows="dynamic" (Activa Agregar/Borrar)
    col_cfg_types = {
        "id": st.column_config.NumberColumn(disabled=True, width="small"),
        "name": st.column_config.TextColumn("Tipo Actividad", required=True, width="medium"),
        "description": st.column_config.TextColumn("Descripción / Detalles", width="large")
    }

    edited_types = st.data_editor(
        df_types,
        column_config=col_cfg_types,
        num_rows="dynamic", # <--- ESTO ES LA CLAVE
        hide_index=True,
        use_container_width=True,
        key="editor_types_main"
    )

    # 3. Guardar Cambios (Lógica inteligente: Crear, Borrar, Actualizar)
    if st.button("💾 Guardar Cambios (Tipos)"):
        # A. DETECTAR BORRADOS (Los IDs que ya no están en la tabla)
        ids_remanentes_t = set(edited_types["id"].dropna().astype(int).tolist())
        ids_borrar_t = ids_originales_t - ids_remanentes_t
        
        d_count = 0
        if ids_borrar_t:
            db.query(ActivityType).filter(ActivityType.id.in_(ids_borrar_t)).delete(synchronize_session=False)
            d_count = len(ids_borrar_t)
            
        # B. ACTUALIZAR EXISTENTES Y CREAR NUEVOS
        u_count = 0
        n_count = 0
        
        for index, row in edited_types.iterrows():
            # Si tiene ID, actualizamos
            if pd.notna(row["id"]):
                t_item = db.query(ActivityType).get(int(row["id"]))
                if t_item:
                    t_item.name = row["name"]
                    t_item.description = row["description"]
                    u_count += 1
            # Si NO tiene ID, creamos uno nuevo
            else:
                new_t = ActivityType(
                    name=row["name"],
                    description=row["description"]
                )
                db.add(new_t)
                n_count += 1
        
        db.commit()
        
        msg_t = "✅ Procesado: "
        if d_count: msg_t += f"🗑️ {d_count} borrados. "
        if n_count: msg_t += f"✨ {n_count} nuevos. "
        if u_count: msg_t += f"✏️ {u_count} actualizados."
        st.success(msg_t)
        st.rerun()

# --- TAB 4: USUARIOS ---
with tab4:

    st.markdown("### Gestion de Usuarios")
    st.info("Escribe en 'Password' para cambiar la clave. Si queda vacio, no hay cambios.")

    # 1. Cargar Usuarios
    u_list = db.query(User).order_by(User.id).all()
    u_orig_ids = {u.id for u in u_list}

    # 2. DataFrame simple
    df_u = pd.DataFrame([{"id": u.id, "username": u.username, "role": u.role, "password": ""} for u in u_list])

    # 3. Configuracion en una sola linea por columna para evitar el TypeError
    c_config = {
        "id": st.column_config.NumberColumn("ID", disabled=True),
        "username": st.column_config.TextColumn("Usuario", required=True),
        "role": st.column_config.SelectboxColumn("Rol", options=["ADMIN", "AUTORIZADO", "VENDEDOR"], required=True),
        "password": st.column_config.TextColumn("Password")
    }

    # 4. Editor Dinamico
    ed_u = st.data_editor(df_u, column_config=c_config, num_rows="dynamic", hide_index=True, use_container_width=True, key="users_editor_final")

    if st.button("Guardar Usuarios"):
        # Procesar Borrados
        curr_ids = set(ed_u["id"].dropna().astype(int).tolist())
        for d_id in (u_orig_ids - curr_ids):
            if d_id != 1: # Proteccion Admin
                db.query(User).filter(User.id == d_id).delete()
        
        # Procesar Cambios y Nuevos
        for _, row in ed_u.iterrows():
            u_name = str(row["username"]).strip()
            pw = str(row["password"]).strip()
            
            if pd.notna(row["id"]):
                user = db.query(User).get(int(row["id"]))
                if user:
                    user.username = u_name
                    user.role = row["role"]
                    if pw and pw not in ["", "nan"]:
                        user.password_hash = bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            else:
                if pw and pw not in ["", "nan"]:
                    hash_pw = bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    db.add(User(username=u_name, role=row["role"], password_hash=hash_pw))
        
        db.commit()
        st.success("Cambios guardados con exito")
        st.rerun()

# --- TAB 5: PROVEEDORES ---
with tab5:
    st.subheader("🏢 Catálogo de Proveedores Detallado")

    st.markdown("### 📤 Carga Masiva de Proveedores")
    uploaded_provs = st.file_uploader("Subir CSV de Proveedores", type=["csv"], key="csv_provs")

    if uploaded_provs:
        try:
            df_prov = pd.read_csv(uploaded_provs)
            if df_prov.shape[1] < 2:
                uploaded_provs.seek(0)
                df_prov = pd.read_csv(uploaded_provs, sep=';')
        except:
            st.error("Error leyendo CSV.")
            st.stop()

        df_prov.columns = [c.lower().strip() for c in df_prov.columns]
        
        # MAPEO INTELIGENTE (Español -> Inglés)
        rename_map = {
            'nombre': 'name', 'nombre comercial': 'name', 'empresa': 'name', 'proveedor': 'name',
            'razon social': 'legal_name', 'razón social': 'legal_name',
            'tipo': 'provider_type', 'categoria': 'provider_type',
            'nit': 'nit',
            'cui': 'cui', 'dpi': 'cui',
            'banco': 'bank_name',
            'cuenta': 'account_number', 'numero de cuenta': 'account_number'
        }
        df_prov.rename(columns=rename_map, inplace=True)
        
        st.write("Columnas detectadas:", df_prov.columns.tolist())
        
        if 'name' not in df_prov.columns:
            st.error("❌ Falta la columna 'Nombre Comercial' o 'Empresa'.")
        else:
            if st.button("🚀 Procesar Carga Proveedores"):
                existing_provs = db.query(Company).all()
                existing_names = {p.name for p in existing_provs}
                existing_nits = {p.nit for p in existing_provs if p.nit}
                
                new_provs = []
                skipped = 0
                
                for index, row in df_prov.iterrows():
                    name_val = str(row['name']).strip()
                    
                    # Limpieza de NIT (quitar guiones si quieres)
                    nit_val = str(row.get('nit', '')).strip().upper()
                    if nit_val == "NAN": nit_val = ""
                    
                    # Chequeo de duplicados (Nombre O Nit)
                    if name_val in existing_names or (nit_val and nit_val in existing_nits):
                        skipped += 1
                        continue
                    
                    # Limpieza de otros campos para que no diga "nan"
                    def clean(val):
                        s = str(val).strip()
                        return "" if s.lower() == "nan" else s

                    new_obj = Company(
                        name=name_val,
                        legal_name=clean(row.get('legal_name', '')),
                        provider_type=clean(row.get('provider_type', 'Directo')),
                        nit=nit_val,
                        cui=clean(row.get('cui', '')),
                        bank_name=clean(row.get('bank_name', '')),
                        account_number=clean(row.get('account_number', ''))
                    )
                    new_provs.append(new_obj)
                    existing_names.add(name_val)
                    if nit_val: existing_nits.add(nit_val)

                if new_provs:
                    db.add_all(new_provs)
                    db.commit()
                    st.success(f"✅ Se agregaron {len(new_provs)} nuevos proveedores.")
                
                if skipped > 0:
                    st.warning(f"⚠️ Se omitieron {skipped} proveedores (ya existían por Nombre o NIT).")
    
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