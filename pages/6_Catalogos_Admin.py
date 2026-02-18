import streamlit as st
import pandas as pd
from database import get_db
from models import Insumo, Mall, ActivityType, Proveedor, OI, User
from auth import require_role, hash_password
import bcrypt
import streamlit as st
from database import engine
from models import Base
from sqlalchemy import func

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
            'categoria': 'category', 'cat': 'category', 'categoría': 'category',
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
                if st.button("Crear OI"):
                    try:
                        # Forzamos que el código sea un string sin decimales antes de guardar
                        clean_manual_code = str(int(float(oc))) if oc.replace('.','').isdigit() else oc
                        db.add(OI(mall_id=sm.id, oi_code=clean_manual_code, oi_name=on, annual_budget_usd=ob))
                        db.commit()
                        st.success("OI creada con éxito")
                        st.rerun()
                    except Exception as e:
                        db.rollback() # <--- ESTO ES LO QUE DESBLOQUEA TU APP
                        st.error(f"Error al crear: {e}")        
        try:
            ois_data = db.query(OI).all()
        except Exception:
            db.rollback() # Limpia cualquier error previo para permitir la lectura
            ois_data = db.query(OI).all()
        
        # Carga CSV OIs
        with st.expander("📂 Carga Masiva OIs (CSV o Excel)"):
            st.info("💡 RECOMENDACIÓN: Sube el archivo en formato EXCEL (.xlsx) para evitar problemas con los números largos.")
            uploaded_oi = st.file_uploader("Sube archivo", type=["xlsx", "csv"])
            
            if uploaded_oi and st.button("Procesar Archivo"):
                try:
                    # 1. LECTURA BLINDADA (Forzamos a que el Código sea Texto para no perder dígitos)
                    if uploaded_oi.name.endswith('.csv'):
                        # Para CSV: Detectamos separador automático y forzamos string
                        df_load = pd.read_csv(
                            uploaded_oi, 
                            encoding='utf-8-sig', 
                            sep=None, 
                            engine='python', 
                            dtype={'Codigo': str} # <--- ¡ESTO ES VITAL!
                        )
                    else:
                        # Para EXCEL: Esta es la mejor opción
                        df_load = pd.read_excel(
                            uploaded_oi, 
                            dtype={'Codigo': str} # <--- Lee "300000002352" tal cual, sin redondear
                        )
                    
                    # Limpieza de nombres de columnas (quita espacios extra)
                    df_load.columns = df_load.columns.str.strip()
                    
                    # Validación de columnas
                    if 'Mall' not in df_load.columns or 'Codigo' not in df_load.columns:
                        st.error(f"Error: No encuentro las columnas 'Mall' o 'Codigo'. Detectadas: {list(df_load.columns)}")
                        st.stop()

                    # Mapeo de Malls
                    malls_map = {m.name.strip().lower(): m.id for m in db.query(Mall).all()}
                    
                    created_count = 0
                    updated_count = 0
                    errors = []

                    for index, row in df_load.iterrows():
                        try:
                            # Datos básicos
                            mall_input = str(row['Mall']).strip()
                            mall_key = mall_input.lower()
                            
                            # --- RECUPERACIÓN DEL CÓDIGO EXACTO ---
                            # Al leer como string, debería venir como "300000002352"
                            raw_code = str(row['Codigo']).strip()
                            
                            # Solo si por desgracia viene como notación científica (ej: "3.00E+11"), intentamos convertirlo
                            # Pero si subes el Excel, esto NO debería pasar.
                            if 'E+' in raw_code:
                                st.warning(f"Fila {index+1}: El código venía en notación científica ({raw_code}). Se perderá precisión. Usa .xlsx mejor.")
                                clean_code = str(int(float(raw_code)))
                            elif raw_code.endswith('.0'):
                                clean_code = raw_code[:-2]
                            else:
                                clean_code = raw_code # Aquí tomamos el "300000002352" original
                            # --------------------------------------

                            if mall_key not in malls_map:
                                errors.append(f"Fila {index+1}: Mall '{mall_input}' no existe.")
                                continue
                            
                            mall_id_found = malls_map[mall_key]
                            
                            # Upsert (Actualizar o Crear)
                            existing_oi = db.query(OI).filter(OI.oi_code == clean_code).first()
                            
                            if existing_oi:
                                existing_oi.mall_id = mall_id_found
                                existing_oi.oi_name = str(row['Nombre']).strip()
                                existing_oi.annual_budget_usd = float(row['Presupuesto'])
                                updated_count += 1
                            else:
                                new_oi = OI(
                                    mall_id=mall_id_found,
                                    oi_code=clean_code, # Guardamos el código exacto
                                    oi_name=str(row['Nombre']).strip(),
                                    annual_budget_usd=float(row['Presupuesto']),
                                    is_active=True
                                )
                                db.add(new_oi)
                                created_count += 1
                                
                        except Exception as row_e:
                            errors.append(f"Error fila {index+1}: {row_e}")

                    db.commit()
                    
                    if created_count > 0 or updated_count > 0:
                        st.success(f"✅ Procesado: {created_count} nuevos y {updated_count} actualizados.")
                        st.balloons()
                        st.rerun()
                    elif not errors:
                        st.warning("⚠️ No hubo cambios en la base de datos.")
                        
                    if errors:
                        st.error("Errores encontrados:")
                        for e in errors:
                            st.write(f"- {e}")

                except Exception as e:
                    db.rollback()
                    st.error(f"Error crítico: {e}")

        st.write("---")
        st.subheader("📋 Listado y Edición de OIs")

        # 1. Cargar datos frescos de la Base de Datos
        try:
            malls_db = db.query(Mall).all()
            # Mapeos para traducir ID <-> Nombre
            mall_id_to_name = {m.id: m.name for m in malls_db}
            mall_name_to_id = {m.name: m.id for m in malls_db}
            mall_names_list = list(mall_name_to_id.keys())

            ois_db = db.query(OI).order_by(OI.id).all()
            # Guardamos los IDs originales para saber cuáles se borraron después
            original_ids = {o.id for o in ois_db}

        except Exception:
            db.rollback()
            st.error("Error cargando datos. Refresca la página.")
            st.stop()

        if ois_db:
            # 2. Preparar el DataFrame
            df_ois = pd.DataFrame([
                {
                    "id": o.id,
                    "Mall": mall_id_to_name.get(o.mall_id, "Desconocido"),
                    "Codigo": o.oi_code,
                    "Nombre": o.oi_name,
                    "Presupuesto": o.annual_budget_usd
                } for o in ois_db
            ])

            # 3. Configurar el Editor con num_rows="dynamic"
            # ESTO ES LO QUE ACTIVA EL BASURERO Y EL BOTÓN DE AÑADIR (+)
            edited_df = st.data_editor(
                df_ois,
                key="editor_ois_dynamic",
                num_rows="dynamic", # <--- ¡LA CLAVE!
                use_container_width=True,
                hide_index=True,
                column_config={
                    "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                    "Mall": st.column_config.SelectboxColumn(
                        "Mall",
                        options=mall_names_list,
                        required=True,
                        width="medium"
                    ),
                    "Codigo": st.column_config.TextColumn("Código OI", width="medium"),
                    "Nombre": st.column_config.TextColumn("Nombre OI", width="large"),
                    "Presupuesto": st.column_config.NumberColumn(
                        "Presupuesto ($)", format="$%.2f", min_value=0
                    )
                }
            )

            # 4. Lógica de Sincronización (Detectar Borrados, Ediciones y Nuevos)
            if st.button("💾 Guardar Cambios en OIs", type="primary"):
                try:
                    # A) DETECTAR BORRADOS
                    # IDs que están en la tabla editada
                    current_ids = set(edited_df["id"].dropna().astype(int).tolist())
                    # IDs que estaban en la DB pero ya no están en la tabla (fueron borrados)
                    ids_to_delete = original_ids - current_ids
                    
                    if ids_to_delete:
                        db.query(OI).filter(OI.id.in_(ids_to_delete)).delete(synchronize_session=False)

                    # B) DETECTAR NUEVOS Y EDICIONES
                    for index, row in edited_df.iterrows():
                        # Obtenemos el ID del Mall seleccionado
                        mall_id_sel = mall_name_to_id.get(row["Mall"])

                        # Caso 1: Fila Nueva (No tiene ID o es NaN)
                        if pd.isna(row["id"]):
                            new_oi = OI(
                                mall_id=mall_id_sel,
                                oi_code=str(row["Codigo"]), # Forzamos string
                                oi_name=str(row["Nombre"]),
                                annual_budget_usd=float(row["Presupuesto"] or 0)
                            )
                            db.add(new_oi)
                        
                        # Caso 2: Fila Existente (Tiene ID) - Actualizamos
                        else:
                            oi_id = int(row["id"])
                            if oi_id in original_ids:
                                existing_oi = db.query(OI).get(oi_id)
                                if existing_oi:
                                    # Solo actualizamos si cambiaron los datos
                                    if (existing_oi.mall_id != mall_id_sel or 
                                        existing_oi.oi_code != str(row["Codigo"]) or
                                        existing_oi.oi_name != str(row["Nombre"]) or
                                        existing_oi.annual_budget_usd != float(row["Presupuesto"])):
                                        
                                        existing_oi.mall_id = mall_id_sel
                                        existing_oi.oi_code = str(row["Codigo"])
                                        existing_oi.oi_name = str(row["Nombre"])
                                        existing_oi.annual_budget_usd = float(row["Presupuesto"])

                    db.commit()
                    st.toast("✅ Cambios guardados exitosamente.", icon="🚀")
                    st.rerun()

                except Exception as e:
                    db.rollback()
                    st.error(f"Error al guardar: {e}")

        else:
            st.info("No hay OIs cargadas. Usa el panel de arriba para agregar.")            
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

    st.subheader("📥 Carga Masiva de Proveedores (Datos Completos)")
    st.info("Columnas sugeridas en Excel: 'Nombre Comercial', 'Razon Social', 'Tipo', 'NIT', 'DPI', 'Banco', 'Cuenta'")

    uploaded_prov = st.file_uploader("Sube CSV o Excel", type=["csv", "xlsx"], key="upload_prov_full")

    if uploaded_prov and st.button("Procesar Proveedores"):
        try:
            # --- 1. LECTURA INTELIGENTE ---
            if uploaded_prov.name.endswith('.csv'):
                try:
                    # Intento A: UTF-8 + Auto-separador
                    df_prov = pd.read_csv(uploaded_prov, sep=None, engine='python', encoding='utf-8-sig', dtype=str)
                except:
                    # Intento B: Latin-1 (Excel español)
                    uploaded_prov.seek(0)
                    df_prov = pd.read_csv(uploaded_prov, sep=';', encoding='latin-1', dtype=str)
            else:
                # Excel (dtype=str para que el NIT o Cuenta no pierdan ceros o se vuelvan notación científica)
                df_prov = pd.read_excel(uploaded_prov, dtype=str)
            
            # Limpiar encabezados (quitar espacios y poner todo bonito)
            df_prov.columns = df_prov.columns.str.strip()
            
            # --- 2. MAPEO DE COLUMNAS (BUSCADOR INTELIGENTE) ---
            # Función para buscar columna ignorando mayúsculas/tildes
            def find_col(options):
                for col in df_prov.columns:
                    if col.lower().strip() in [o.lower() for o in options]:
                        return col
                return None

            # Buscamos las columnas basándonos en tu formulario
            c_nombre = find_col(['Nombre Comercial', 'Nombre', 'Empresa', 'Proveedor'])
            c_razon  = find_col(['Razón Social', 'Razon Social', 'Legal'])
            c_tipo   = find_col(['Tipo', 'Categoria', 'Servicio'])
            c_nit    = find_col(['NIT', 'Nit'])
            c_cui    = find_col(['CUI', 'DPI', 'Identificacion'])
            c_banco  = find_col(['Banco', 'Bank'])
            c_cuenta = find_col(['No. de Cuenta', 'No Cuenta', 'Cuenta', 'Numero Cuenta'])

            # Validación mínima: El nombre comercial es obligatorio
            if not c_nombre:
                st.error(f"⚠️ Error: No encuentro la columna 'Nombre Comercial'. Columnas leídas: {list(df_prov.columns)}")
                st.stop()

            count_new = 0
            count_skipped = 0
            progress_bar = st.progress(0)
            total_rows = len(df_prov)

            for i, (index, row) in enumerate(df_prov.iterrows()):
                # Obtener y limpiar datos
                nombre_input = str(row[c_nombre]).strip()
                
                if not nombre_input or nombre_input.lower() == 'nan': 
                    continue

                # --- 3. PROTECCIÓN CONTRA DUPLICADOS ---
                # Buscamos por Nombre Comercial (insensible a mayúsculas)
                existing = db.query(Proveedor).filter(func.lower(Proveedor.name) == nombre_input.lower()).first()
                # Opcional: Podrías buscar también por NIT si quisieras ser más estricto
                # existing = db.query(Proveedor).filter(Proveedor.nit == str(row[c_nit]).strip()).first()
                
                if not existing:
                    # Crear nuevo objeto con TODOS los campos
                    new_p = Proveedor(
                        name = nombre_input,  # Nombre Comercial
                        
                        # Asignamos los campos extra si existen en el Excel, si no, quedan vacíos
                        legal_name = str(row[c_razon]).strip() if c_razon and pd.notna(row[c_razon]) else "",
                        provider_type = str(row[c_tipo]).strip() if c_tipo and pd.notna(row[c_tipo]) else "Certificado", # Valor por defecto
                        nit = str(row[c_nit]).strip() if c_nit and pd.notna(row[c_nit]) else "",
                        cui = str(row[c_cui]).strip() if c_cui and pd.notna(row[c_cui]) else "",
                        bank_name = str(row[c_banco]).strip() if c_banco and pd.notna(row[c_banco]) else "",
                        account_number = str(row[c_cuenta]).strip() if c_cuenta and pd.notna(row[c_cuenta]) else ""
                    )
                    db.add(new_p)
                    count_new += 1
                else:
                    count_skipped += 1
                
                progress_bar.progress((i + 1) / total_rows)
            
            db.commit()
            st.success(f"✅ Procesado: {count_new} proveedores nuevos. {count_skipped} ya existían.")
            st.balloons()
            
            import time
            time.sleep(1.5)
            st.rerun()

        except Exception as e:
            db.rollback()
            st.error(f"❌ Error técnico: {e}. (Verifica que tu base de datos tenga las columnas 'nit', 'cui', 'bank', etc.)")
        
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
    companies = db.query(Proveedor).all()
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
            save_changes_generic(Proveedor, edited_comps)