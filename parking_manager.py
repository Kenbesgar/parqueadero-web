import sqlite3
import datetime
import configparser
import os
import re

class ParkingManager:
    def __init__(self, db_path="parqueadero.db"):
        # Usamos rutas absolutas para compatibilidad con servidores como PythonAnywhere
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(base_dir, db_path)
        self.config_file = os.path.join(base_dir, 'config.ini')
        self.session_file = os.path.join(base_dir, 'caja.ini')

        self.config = configparser.ConfigParser()
        self.session = configparser.ConfigParser()
        self.inicializar_base_de_datos()
        self.cargar_config()
        self.cargar_sesion()

    def inicializar_base_de_datos(self):
        conn = sqlite3.connect(self.db_path); cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, placa TEXT, tipo TEXT, ingreso TEXT, salida TEXT, valor REAL, estado TEXT, descuento REAL DEFAULT 0, motivo_descuento TEXT DEFAULT '', medio_pago TEXT DEFAULT 'EFECTIVO', usuario_pago TEXT, usuario_ingreso TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS cierres (usuario TEXT, fecha_apertura TEXT, fecha_cierre TEXT, base REAL, vts_ef_sis REAL DEFAULT 0, vts_qr_sis REAL DEFAULT 0, vts_ef_dig REAL DEFAULT 0, vts_qr_dig REAL DEFAULT 0, cnt_ef_sis INTEGER DEFAULT 0, cnt_qr_sis INTEGER DEFAULT 0, estado TEXT DEFAULT 'ACTIVO')")
        cursor.execute("CREATE TABLE IF NOT EXISTS auditoria (usuario TEXT, accion TEXT, detalle TEXT, fecha TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS mensualidades (placa TEXT PRIMARY KEY, cliente TEXT, fecha_inicio TEXT, fecha_fin TEXT, valor_pagado REAL)")
        try: cursor.execute("ALTER TABLE tickets ADD COLUMN usuario_ingreso TEXT")
        except: pass
        try: cursor.execute("ALTER TABLE tickets ADD COLUMN usuario_pago TEXT")
        except: pass
        try: cursor.execute("ALTER TABLE tickets ADD COLUMN descuento REAL DEFAULT 0")
        except: pass
        try: cursor.execute("ALTER TABLE tickets ADD COLUMN motivo_descuento TEXT DEFAULT ''")
        except: pass
        try: cursor.execute("ALTER TABLE cierres ADD COLUMN estado TEXT DEFAULT 'ACTIVO'")
        except: pass
        conn.commit(); conn.close()

    def get_estado_caja(self, usuario):
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute("SELECT rowid as id, * FROM cierres WHERE usuario = ? AND (fecha_cierre IS NULL OR fecha_cierre = '') AND estado != 'ELIMINADO'", (usuario,))
        row = cursor.fetchone(); conn.close()
        if row: return {'estado': 'ABIERTA', 'id': row['id'], 'usuario': row['usuario'], 'base': float(row['base']), 'fecha_apertura': row['fecha_apertura']}
        return {'estado': 'CERRADA', 'usuario': usuario, 'base': 0, 'fecha_apertura': 'N/A'}

    def abrir_caja(self, usuario, base):
        if self.get_estado_caja(usuario)['estado'] == 'ABIERTA': return False
        conn = sqlite3.connect(self.db_path); cursor = conn.cursor()
        ahora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        cursor.execute("INSERT INTO cierres (usuario, fecha_apertura, base, estado) VALUES (?, ?, ?, 'ACTIVO')", (usuario, ahora, base))
        self.registrar_auditoria(cursor, usuario, "APERTURA_CAJA", f"Base: {base}")
        conn.commit(); conn.close(); return True

    def get_valores_actuales(self, usuario):
        caja = self.get_estado_caja(usuario)
        if caja['estado'] == 'CERRADA': return {'efectivo': 0, 'qr': 0, 'total': 0, 'cnt_ef': 0, 'cnt_qr': 0, 'descuentos': 0}
        conn = sqlite3.connect(self.db_path); cursor = conn.cursor()
        cursor.execute("SELECT valor, medio_pago, descuento FROM tickets WHERE estado = 'PAGADO' AND usuario_pago = ? AND salida >= ?", (usuario, caja['fecha_apertura']))
        ef, qr, cef, cqr, dtot = 0.0, 0.0, 0, 0, 0.0
        for row in cursor.fetchall():
            dtot += row[2]
            if row[1] == 'QR': qr += row[0]; cqr += 1
            else: ef += row[0]; cef += 1
        conn.close(); return {'efectivo': ef, 'qr': qr, 'cnt_ef': cef, 'cnt_qr': cqr, 'total': ef + qr, 'descuentos': dtot}

    def cerrar_caja(self, ef_dig, qr_dig, usuario_caja):
        caja = self.get_estado_caja(usuario_caja)
        if caja['estado'] == 'CERRADA': return False
        sis = self.get_valores_actuales(usuario_caja)
        conn = sqlite3.connect(self.db_path); cursor = conn.cursor()
        ahora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        cursor.execute("UPDATE cierres SET fecha_cierre = ?, vts_ef_sis = ?, vts_qr_sis = ?, vts_ef_dig = ?, vts_qr_dig = ?, cnt_ef_sis = ?, cnt_qr_sis = ? WHERE rowid = ?",
                       (ahora, sis['efectivo'], sis['qr'], ef_dig, qr_dig, sis['cnt_ef'], sis['cnt_qr'], caja['id']))
        self.registrar_auditoria(cursor, usuario_caja, "CIERRE_CAJA", f"Caja ID: {caja['id']}")
        conn.commit(); conn.close(); return True

    def aplicar_descuento_manual(self, id_t, monto, motivo, usuario_admin):
        conn = sqlite3.connect(self.db_path); cursor = conn.cursor()
        cursor.execute("SELECT valor, placa FROM tickets WHERE id = ?", (id_t,))
        row = cursor.fetchone()
        if not row: conn.close(); return {"status": "error", "msg": "No encontrado"}
        if float(monto) > row[0]: conn.close(); return {"status": "error", "msg": "Descuento superior al valor"}
        cursor.execute("UPDATE tickets SET valor = valor - ?, descuento = descuento + ?, motivo_descuento = ? WHERE id = ?", (monto, monto, motivo, id_t))
        self.registrar_auditoria(cursor, usuario_admin, "DESCUENTO", f"Placa: {row[1]} | ${monto}")
        conn.commit(); conn.close(); return {"status": "ok", "msg": "Aplicado"}

    def registrar_ingreso(self, placa, tipo, usuario):
        if self.get_estado_caja(usuario)['estado'] == 'CERRADA': return "ERROR: No tiene caja abierta."
        placa = placa.upper().strip().replace(" ", "")
        import re
        es_carro = re.match(r"^[A-Z]{3}\d{3}$", placa); es_moto = re.match(r"^[A-Z]{3}\d{2}[A-Z]{1,2}X?$", placa)
        if not es_carro and not es_moto: return "ERROR: Formato de placa inválido."
        tipo_final = "CARRO" if es_carro else "MOTO"
        conn = sqlite3.connect(self.db_path); cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE placa = ? AND estado = 'ACTIVO'", (placa,))
        if cursor.fetchone()[0] > 0: conn.close(); return "ERROR: Ya está adentro."
        ahora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        cursor.execute("INSERT INTO tickets (placa, tipo, ingreso, salida, valor, estado, usuario_ingreso) VALUES (?, ?, ?, 'N/A', 0, 'ACTIVO', ?)", (placa, tipo_final, ahora, usuario))
        t_id = cursor.lastrowid
        conn.commit(); conn.close();
        return {"status": "ok", "msg": "Ingreso registrado correctamente.", "datos": {"id": t_id, "placa": placa, "tipo": tipo_final, "ingreso": ahora}}

    def registrar_salida(self, placa, medio, usuario):
        if self.get_estado_caja(usuario)['estado'] == 'CERRADA': return {"status": "error", "msg": "Caja cerrada."}
        placa = placa.upper().strip()
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute("SELECT rowid as id_pk, * FROM tickets WHERE placa = ? AND estado = 'ACTIVO' ORDER BY id DESC", (placa,))
        row = cursor.fetchone()
        if not row: conn.close(); return {"status": "error", "msg": "No encontrado."}

        t_in = self.parse_fecha(row['ingreso']); t_out = datetime.datetime.now(); mins = int((t_out - t_in).total_seconds() / 60)
        tarifa = self.get_tarifa_carro() if row['tipo'] == "CARRO" else self.get_tarifa_moto()

        if mins <= 60: hrs = 1.0
        else:
            h, m = mins // 60, mins % 60
            if m <= 15: hrs = float(h)
            elif m <= 39: hrs = h + 0.5
            else: hrs = float(h + 1)

        total = hrs * tarifa; ahora_str = t_out.strftime("%d/%m/%Y %H:%M:%S")
        cursor.execute("UPDATE tickets SET salida = ?, valor = ?, estado = 'PAGADO', medio_pago = ?, usuario_pago = ? WHERE rowid = ?", (ahora_str, total, medio, usuario, row['id_pk']))
        self.registrar_auditoria(cursor, usuario, "SALIDA", f"Placa: {placa} | Valor: {total}")
        conn.commit(); conn.close()
        return {"status": "ok", "texto": "PAGO", "datos": {"id": row['id'], "placa": placa, "tipo": row['tipo'], "ingreso": row['ingreso'], "salida": ahora_str, "minutos": mins, "medio": medio, "total": total}}

    def get_tickets_activos(self):
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute("SELECT id, placa, tipo, ingreso FROM tickets WHERE estado = 'ACTIVO'"); rows = [dict(r) for r in cursor.fetchall()]; conn.close(); return rows

    def get_tickets_rango(self, inicio, fin, usuario=None):
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        t_i = self.parse_fecha(inicio); t_f = datetime.datetime.now() if fin == 'EN CURSO' else self.parse_fecha(fin)
        query = "SELECT * FROM tickets WHERE (usuario_ingreso = ? OR usuario_pago = ?)"
        cursor.execute(query, (usuario, usuario))
        all_t = [dict(r) for r in cursor.fetchall()]
        res = [t for t in all_t if (t_i <= self.parse_fecha(t['ingreso']) <= t_f) or (t['salida'] != 'N/A' and t_i <= self.parse_fecha(t['salida']) <= t_f)]
        conn.close(); return res

    def parse_fecha(self, f):
        if not f: return datetime.datetime(1900,1,1)
        # Reemplazar T de datetime-local por espacio para compatibilidad
        f = f.replace('T', ' ')
        for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try: return datetime.datetime.strptime(f, fmt)
            except: continue
        return datetime.datetime(1900,1,1)

    def get_reporte_cierres(self, inc=False):
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        sql = "SELECT rowid as id, * FROM cierres" + ("" if inc else " WHERE estado != 'ELIMINADO'") + " ORDER BY rowid DESC"
        cursor.execute(sql); rows = [dict(r) for r in cursor.fetchall()]; conn.close(); return rows

    def registrar_auditoria(self, cursor, u, a, d):
        cursor.execute("INSERT INTO auditoria (usuario, accion, detalle, fecha) VALUES (?, ?, ?, ?)", (u, a, d, datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")))

    def get_auditoria(self, d=None, h=None, a=None):
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        query = "SELECT * FROM auditoria WHERE 1=1"; params = []
        if a and a not in ["TODAS", "null", "undefined", ""]: query += " AND accion = ?"; params.append(a)
        cursor.execute(query + " ORDER BY fecha DESC", params)
        rows = [dict(r) for r in cursor.fetchall()]
        if d and h and d != "" and h != "" and d != "null":
            try:
                d_obj = datetime.datetime.strptime(d, "%Y-%m-%d"); h_obj = datetime.datetime.strptime(h, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                rows = [r for r in rows if d_obj <= self.parse_fecha(r['fecha']) <= h_obj]
            except: pass
        conn.close(); return rows[:500]

    def get_reporte_filtrado(self, desde, hasta, usuario=None, id_caja=None):
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row; cursor = conn.cursor()

        # Limpieza de parámetros nulos provenientes de la web
        if id_caja in ["", "null", "undefined"]: id_caja = None
        if usuario in ["", "null", "undefined"]: usuario = None

        if id_caja:
            cursor.execute("SELECT usuario, fecha_apertura, fecha_cierre FROM cierres WHERE rowid = ?", (id_caja,))
            caja = cursor.fetchone()
            if caja:
                usuario = caja['usuario']
                desde = caja['fecha_apertura']
                hasta = caja['fecha_cierre'] if caja['fecha_cierre'] else 'EN CURSO'

        cursor.execute("SELECT * FROM tickets WHERE estado = 'PAGADO'")
        all_t = [dict(r) for r in cursor.fetchall()]

        d_obj = self.parse_fecha(desde)
        if hasta == 'EN CURSO': h_obj = datetime.datetime.now()
        else:
            h_obj = self.parse_fecha(hasta)
            if h_obj != datetime.datetime(1900,1,1) and len(str(hasta)) <= 10:
                h_obj = h_obj.replace(hour=23, minute=59, second=59)

        filtrados = [t for t in all_t if d_obj <= self.parse_fecha(t['salida']) <= h_obj]

        if usuario:
            filtrados = [t for t in filtrados if str(t['usuario_pago']).strip().lower() == str(usuario).strip().lower()]

        conn.close()
        return filtrados

    def get_datos_excel(self, tipo, desde, hasta, usuario=None, id_caja=None):
        filtrados = self.get_reporte_filtrado(desde, hasta, usuario, id_caja)
        info = f"Periodo: {desde} a {hasta}"

        # Totales para el resumen
        total_recaudo = sum(t['valor'] for t in filtrados)
        total_efectivo = sum(t['valor'] for t in filtrados if t['medio_pago'] == 'EFECTIVO')
        total_qr = sum(t['valor'] for t in filtrados if t['medio_pago'] == 'QR')

        carros = [t for t in filtrados if t['tipo'] == 'CARRO']
        motos = [t for t in filtrados if t['tipo'] == 'MOTO']

        cant_carros = len(carros)
        cant_motos = len(motos)

        dinero_carros = sum(t['valor'] for t in carros)
        dinero_motos = sum(t['valor'] for t in motos)

        # Cálculo de tiempos totales
        tiempo_carros = sum(int((self.parse_fecha(t['salida'])-self.parse_fecha(t['ingreso'])).total_seconds()/60) for t in carros)
        tiempo_motos = sum(int((self.parse_fecha(t['salida'])-self.parse_fecha(t['ingreso'])).total_seconds()/60) for t in motos)

        descuento_total = sum(t['descuento'] for t in filtrados)

        # Construcción Estética del CSV
        csv = f"REPORTE GENERAL DE VENTAS\n"
        csv += f"CONFIGURACION;{info}\n\n"

        csv += "RESUMEN DE OPERACION POR TIPO\n"
        csv += "CATEGORIA;CANTIDAD;TIEMPO TOTAL (MIN);TOTAL RECAUDADO\n"
        csv += f"CARROS;{cant_carros};{tiempo_carros};{int(dinero_carros)}\n"
        csv += f"MOTOS;{cant_motos};{tiempo_motos};{int(dinero_motos)}\n"
        csv += f"TOTALES;{len(filtrados)};{tiempo_carros + tiempo_motos};{int(total_recaudo)}\n\n"

        csv += "RESUMEN POR MEDIO DE PAGO\n"
        csv += f"TOTAL EFECTIVO;;;{int(total_efectivo)}\n"
        csv += f"TOTAL QR;;;{int(total_qr)}\n"
        csv += f"TOTAL DESCUENTOS;;;{int(descuento_total)}\n"
        csv += f"TOTAL NETO;;;{int(total_recaudo)}\n\n"

        # Detalle de Movimientos
        csv += "DETALLE DE MOVIMIENTOS INDIVIDUALES\n"
        csv += "PLACA;TIPO;INGRESO;SALIDA;TIEMPO (MIN);VALOR PAGADO;MEDIO;DESCUENTO;MOTIVO\n"
        for t in filtrados:
            tiempo = int((self.parse_fecha(t['salida'])-self.parse_fecha(t['ingreso'])).total_seconds()/60)
            csv += f"{t['placa']};{t['tipo']};{t['ingreso']};{t['salida']};{tiempo};{int(t['valor'])};{t['medio_pago']};{int(t['descuento'])};{t['motivo_descuento']}\n"

        return csv

    def cargar_config(self):
        if not os.path.exists(self.config_file):
            self.config['TARIFAS'] = {'tarifa_carro': '4000', 'tarifa_moto': '2000'}
            self.config['USUARIOS'] = {'admin': '1234|ADMIN'}
            self.config['METAS'] = {'diaria': '500000'}
            with open(self.config_file, 'w') as f: self.config.write(f)
        else:
            self.config.read(self.config_file)
            if 'METAS' not in self.config:
                self.config['METAS'] = {'diaria': '500000'}
                self.save_config()
    def save_config(self):
        with open(self.config_file, 'w') as f: self.config.write(f)
    def cargar_sesion(self):
        if not os.path.exists(self.session_file):
            if 'ESTADO' not in self.session: self.session.add_section('ESTADO')
            self.session.set('ESTADO', 'estado', 'CERRADA'); self.save_session()
        else: self.session.read(self.session_file)
    def save_session(self):
        with open(self.session_file, 'w') as f: self.session.write(f)
    def get_tarifa_carro(self): return float(self.config.get('TARIFAS', 'tarifa_carro', fallback=4000))
    def get_tarifa_moto(self): return float(self.config.get('TARIFAS', 'tarifa_moto', fallback=2000))
    def set_tarifas(self, c, m, meta=None):
        if 'TARIFAS' not in self.config: self.config.add_section('TARIFAS')
        self.config.set('TARIFAS', 'tarifa_carro', str(c))
        self.config.set('TARIFAS', 'tarifa_moto', str(m))
        if meta:
            if 'METAS' not in self.config: self.config.add_section('METAS')
            self.config.set('METAS', 'diaria', str(meta))
        self.save_config()
    def get_lista_usuarios(self): return list(self.config['USUARIOS'].keys())
    def get_usuario_info(self, u): return self.config.get('USUARIOS', u.lower(), fallback=None)
    def get_ticket_by_id(self, id_t):
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute("SELECT * FROM tickets WHERE id = ?", (id_t,)); row = cursor.fetchone(); conn.close(); return dict(row) if row else None

    def get_caja_by_id(self, id_c):
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute("SELECT rowid as id, * FROM cierres WHERE rowid = ?", (id_c,))
        row = cursor.fetchone(); conn.close()
        if not row: return None
        res = dict(row)
        # Para que sea compatible con el modal, mapeamos los valores guardados
        res['valores_actuales'] = {
            'efectivo': row['vts_ef_sis'],
            'qr': row['vts_qr_sis'],
            'total': row['vts_ef_sis'] + row['vts_qr_sis']
        }
        res['digitado'] = {
            'efectivo': row['vts_ef_dig'],
            'qr': row['vts_qr_dig'],
            'total': row['vts_ef_dig'] + row['vts_qr_dig']
        }
        return res

    def eliminar_cierre(self, id_c, admin):
        conn = sqlite3.connect(self.db_path); cursor = conn.cursor()
        cursor.execute("UPDATE cierres SET estado = 'ELIMINADO' WHERE rowid = ?", (id_c,))
        self.registrar_auditoria(cursor, admin, "ELIMINAR_CAJA", f"ID: {id_c}"); conn.commit(); conn.close(); return True
    def recuperar_cierre(self, id_c, admin):
        conn = sqlite3.connect(self.db_path); cursor = conn.cursor()
        cursor.execute("UPDATE cierres SET estado = 'ACTIVO' WHERE rowid = ?", (id_c,))
        self.registrar_auditoria(cursor, admin, "RECUPERAR_CAJA", f"ID: {id_c}"); conn.commit(); conn.close(); return True
    def actualizar_usuario_actual(self, id_caja, nuevo_u, admin):
        conn = sqlite3.connect(self.db_path); cursor = conn.cursor()
        cursor.execute("UPDATE cierres SET usuario = ? WHERE rowid = ?", (nuevo_u, id_caja))
        self.registrar_auditoria(cursor, admin, "CAMBIO_RESPONSABLE", f"Caja ID: {id_caja} a {nuevo_u}"); conn.commit(); conn.close(); return True

    def set_metas(self, diaria, semanal, mensual, anual):
        if 'METAS' not in self.config: self.config.add_section('METAS')
        self.config.set('METAS', 'diaria', str(diaria))
        self.config.set('METAS', 'semanal', str(semanal))
        self.config.set('METAS', 'mensual', str(mensual))
        self.config.set('METAS', 'anual', str(anual))
        self.save_config()

    def get_mensualidades(self):
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute("SELECT * FROM mensualidades ORDER BY fecha_fin ASC")
        rows = [dict(r) for r in cursor.fetchall()]; conn.close(); return rows

    def guardar_mensualidad(self, p, c, i, f, v):
        conn = sqlite3.connect(self.db_path); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO mensualidades (placa, cliente, fecha_inicio, fecha_fin, valor_pagado) VALUES (?, ?, ?, ?, ?)", (p.upper(), c, i, f, v))
        self.registrar_auditoria(cursor, "SISTEMA", "REGISTRO_MENSUALIDAD", f"Placa: {p} | Cliente: {c}")
        conn.commit(); conn.close(); return True

    def eliminar_mensualidad(self, p):
        conn = sqlite3.connect(self.db_path); cursor = conn.cursor()
        cursor.execute("DELETE FROM mensualidades WHERE placa = ?", (p,))
        self.registrar_auditoria(cursor, "SISTEMA", "ELIMINAR_MENSUALIDAD", f"Placa: {p}")
        conn.commit(); conn.close(); return True

    def get_estadisticas_avanzadas(self, desde, hasta, id_caja=None):
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row; cursor = conn.cursor()

        usuario_filtro = None
        if id_caja and id_caja != "" and id_caja != "undefined":
            cursor.execute("SELECT usuario, fecha_apertura, fecha_cierre FROM cierres WHERE rowid = ?", (id_caja,))
            caja = cursor.fetchone()
            if caja:
                usuario_filtro = caja['usuario']
                desde = caja['fecha_apertura']
                hasta = caja['fecha_cierre'] if caja['fecha_cierre'] else 'EN CURSO'

        cursor.execute("SELECT * FROM tickets WHERE estado = 'PAGADO'")
        all_pagados = [dict(r) for r in cursor.fetchall()]

        d_obj = self.parse_fecha(desde)
        h_obj = datetime.datetime.now() if hasta == 'EN CURSO' else self.parse_fecha(hasta)
        if len(str(hasta)) <= 10 and h_obj != datetime.datetime(1900,1,1):
            h_obj = h_obj.replace(hour=23, minute=59, second=59)

        filtrados = [t for t in all_pagados if d_obj <= self.parse_fecha(t['salida']) <= h_obj]
        if usuario_filtro:
            filtrados = [t for t in filtrados if str(t['usuario_pago']).strip().lower() == str(usuario_filtro).strip().lower()]

        ahora = datetime.datetime.now()

        # Cálculos de periodos para metas
        def get_total_periodo(inicio, fin):
            return sum(t['valor'] for t in all_pagados if inicio <= self.parse_fecha(t['salida']) <= fin)

        # Diario (Hoy)
        inicio_hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
        total_hoy = get_total_periodo(inicio_hoy, ahora)

        # Semanal (Lunes a Domingo actual)
        inicio_semana = (ahora - datetime.timedelta(days=ahora.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        total_semana = get_total_periodo(inicio_semana, ahora)

        # Mensual (Mes actual)
        inicio_mes = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        total_mes = get_total_periodo(inicio_mes, ahora)

        # Anual (Año actual)
        inicio_anio = ahora.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        total_anio = get_total_periodo(inicio_anio, ahora)

        # Historial 7 días para el gráfico de barras
        fin_7 = h_obj
        inicio_7 = (fin_7 - datetime.timedelta(days=6)).replace(hour=0, minute=0, second=0)
        ultimos_7_dias = {}
        for i in range(7):
            fecha_d = (inicio_7 + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            ultimos_7_dias[fecha_d] = 0.0
        for t in all_pagados:
            ts = self.parse_fecha(t['salida'])
            if inicio_7 <= ts <= fin_7:
                dk = ts.strftime("%Y-%m-%d");
                if dk in ultimos_7_dias: ultimos_7_dias[dk] += t['valor']

        res = {
            "conteos": {"CARRO": 0, "MOTO": 0},
            "dinero": {"CARRO": 0.0, "MOTO": 0.0},
            "por_hora": {},
            "max_hora": {"hora": None, "valor": 0},
            "min_hora": {"hora": None, "valor": float('inf')},
            "promedios": {"diario": 0, "ticket": 0},
            "historial_7_dias": ultimos_7_dias,
            "dashboard_metas": {
                "hoy": {"total": total_hoy, "meta": float(self.config.get('METAS', 'diaria', fallback=500000))},
                "semana": {"total": total_semana, "meta": float(self.config.get('METAS', 'semanal', fallback=3000000))},
                "mes": {"total": total_mes, "meta": float(self.config.get('METAS', 'mensual', fallback=12000000))},
                "anio": {"total": total_anio, "meta": float(self.config.get('METAS', 'anual', fallback=140000000))}
            }
        }

        for h in range(24): res["por_hora"][h] = {"CARRO": 0, "MOTO": 0, "cnt_c": 0, "cnt_m": 0}
        for t in filtrados:
            tipo, valor = t['tipo'], t['valor']
            res["conteos"][tipo] += 1
            res["dinero"][tipo] += valor
            h_salida = self.parse_fecha(t['salida']).hour
            res["por_hora"][h_salida][tipo] += valor
            if tipo == "CARRO": res["por_hora"][h_salida]["cnt_c"] += 1
            else: res["por_hora"][h_salida]["cnt_m"] += 1

        suma_total = res["dinero"]["CARRO"] + res["dinero"]["MOTO"]
        for h, data in res["por_hora"].items():
            total_h = data["CARRO"] + data["MOTO"]
            if total_h > 0:
                if total_h > res["max_hora"]["valor"]: res["max_hora"] = {"hora": h, "valor": total_h}
                if total_h < res["min_hora"]["valor"]: res["min_hora"] = {"hora": h, "valor": total_h}

        if res["min_hora"]["valor"] == float('inf'): res["min_hora"]["valor"] = 0
        res["promedios"]["ticket"] = suma_total / len(filtrados) if len(filtrados) > 0 else 0
        diff_days = (h_obj - d_obj).days + 1
        res["promedios"]["diario"] = suma_total / diff_days if diff_days > 0 else suma_total

        conn.close(); return res
