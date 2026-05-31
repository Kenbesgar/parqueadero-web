from flask import Flask, render_template, request, redirect, session, jsonify, Response, make_response
from parking_manager import ParkingManager

app = Flask(__name__)
app.secret_key = 'parqueadero_super_secret_key'
manager = ParkingManager(db_path="parqueadero.db")

@app.route('/')
def index():
    if 'user' not in session: return redirect('/login')
    return render_template('index.html', user=session['user'], name=session.get('name', session['user']), role=session['role'], activos=manager.get_tickets_activos())

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form['usuario'].lower().strip(), request.form['password']
        info = manager.get_usuario_info(u)
        if info:
            parts = info.split('|')
            if parts[0] == p:
                session['user'] = u
                session['role'] = parts[1]
                session['name'] = parts[2] if len(parts) > 2 else u
                return redirect('/')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear(); return redirect('/login')

@app.route('/api/caja/estado')
def caja_estado():
    u = request.args.get('usuario') or session.get('user')
    res = manager.get_estado_caja(u)

    # Mejora para ADMIN: Si su caja está cerrada, buscar si hay alguna otra abierta para supervisar
    if res['estado'] == 'CERRADA' and session.get('role') == 'ADMIN' and not request.args.get('usuario'):
        todas = manager.get_reporte_cierres()
        abierta = next((c for c in todas if not c['fecha_cierre']), None)
        if abierta:
            res = {
                'estado': 'ABIERTA',
                'id': abierta['id'],
                'usuario': abierta['usuario'],
                'base': abierta['base'],
                'fecha_apertura': abierta['fecha_apertura'],
                'supervisando': True
            }

    res['valores_actuales'] = manager.get_valores_actuales(res['usuario'])
    return jsonify(res)

@app.route('/api/caja/abrir', methods=['POST'])
def caja_abrir():
    if 'user' not in session: return jsonify({"status": "error"}), 401
    data = request.json
    if manager.abrir_caja(data['usuario'], data['base']):
        return jsonify({"status": "ok"})
    return jsonify({"status": "error", "msg": "Este usuario ya tiene una caja abierta."})

@app.route('/api/caja/actualizar_usuario', methods=['POST'])
def caja_actualizar_usuario():
    if 'user' not in session: return jsonify({"status": "error"}), 401
    data = request.json
    manager.actualizar_usuario_actual(data['id'], data['usuario'], session['user'])
    return jsonify({"status": "ok"})

@app.route('/api/caja/cerrar', methods=['POST'])
def caja_cerrar():
    if session.get('role') != 'ADMIN':
        return jsonify({"status": "error", "msg": "Solo el administrador puede cerrar la caja."}), 403
    data = request.json
    manager.cerrar_caja(data['ef_dig'], data['qr_dig'], data['usuario'])
    return jsonify({"status": "ok"})

@app.route('/api/ingreso', methods=['POST'])
def api_ingreso():
    data = request.json
    usuario_operativo = session['user']
    if session['role'] == 'ADMIN':
        res_estado = manager.get_estado_caja(session['user'])
        if res_estado['estado'] == 'CERRADA':
            todas = manager.get_reporte_cierres()
            abierta = next((c for c in todas if not c['fecha_cierre']), None)
            if abierta: usuario_operativo = abierta['usuario']

    res = manager.registrar_ingreso(data['placa'], data['tipo'], usuario_operativo)
    if isinstance(res, dict) and res.get('status') == 'ok':
        return jsonify({"status": "ok", "msg": res['msg'], "datos": res['datos'], "activos": manager.get_tickets_activos()})
    return jsonify({"status": "error", "msg": res if isinstance(res, str) else res.get('msg', 'Error desconocido'), "activos": manager.get_tickets_activos()})

@app.route('/api/salida', methods=['POST'])
def api_salida():
    data = request.json
    usuario_operativo = session['user']
    if session['role'] == 'ADMIN':
        res_estado = manager.get_estado_caja(session['user'])
        if res_estado['estado'] == 'CERRADA':
            todas = manager.get_reporte_cierres()
            abierta = next((c for c in todas if not c['fecha_cierre']), None)
            if abierta: usuario_operativo = abierta['usuario']

    res = manager.registrar_salida(data['placa'], data['medio'], usuario_operativo)
    res['activos'] = manager.get_tickets_activos()
    return jsonify(res)

@app.route('/api/reportes')
def api_reportes():
    return jsonify(manager.get_reporte_cierres(request.args.get('incluir_eliminados') == 'true'))

@app.route('/api/reportes/eliminar', methods=['POST'])
def api_reportes_eliminar():
    if session.get('role') != 'ADMIN': return jsonify({"status": "error"}), 403
    manager.eliminar_cierre(request.json['id'], session['user'])
    return jsonify({"status": "ok"})

@app.route('/api/reportes/recuperar', methods=['POST'])
def api_reportes_recuperar():
    if session.get('role') != 'ADMIN': return jsonify({"status": "error"}), 403
    manager.recuperar_cierre(request.json['id'], session['user'])
    return jsonify({"status": "ok"})

@app.route('/api/usuarios', methods=['GET', 'POST', 'DELETE'])
def api_usuarios():
    if session.get('role') != 'ADMIN': return jsonify({"status": "error", "msg": "No autorizado"}), 403

    if request.method == 'POST':
        data = request.json
        u, p, r, n = data['username'].lower().strip(), data['password'], data['role'], data.get('name', '')
        if manager.get_usuario_info(u): return jsonify({"status": "error", "msg": "Existe"}), 400
        manager.config['USUARIOS'][u] = f"{p}|{r}|{n}"
        manager.save_config()
        return jsonify({"status": "ok"})

    if request.method == 'DELETE':
        u = request.args.get('username').lower().strip()
        if u == 'admin' or u == session.get('user').lower(): return jsonify({"status": "error"}), 400
        if u in manager.config['USUARIOS']:
            del manager.config['USUARIOS'][u]
            manager.save_config()
        return jsonify({"status": "ok"})

    res = []
    for u in manager.config['USUARIOS']:
        info = manager.config['USUARIOS'][u].split('|')
        res.append({
            'username': u,
            'role': info[1] if len(info) > 1 else 'OPERARIO',
            'name': info[2] if len(info) > 2 else u
        })
    return jsonify(res)

@app.route('/api/tickets/rango')
def api_tickets_rango():
    u = request.args.get('usuario') or session.get('user')
    return jsonify(manager.get_tickets_rango(request.args.get('inicio'), request.args.get('fin'), u))

@app.route('/api/ticket/<int:id_t>')
def api_get_ticket(id_t):
    return jsonify(manager.get_ticket_by_id(id_t))

@app.route('/api/auditoria')
def api_auditoria():
    return jsonify(manager.get_auditoria())

@app.route('/api/reportes/excel')
def api_reportes_excel():
    if session.get('role') != 'ADMIN': return jsonify({"status": "error", "msg": "No autorizado"}), 403
    t, d, h, u, idc = request.args.get('tipo'), request.args.get('desde'), request.args.get('hasta'), request.args.get('usuario'), request.args.get('id_caja')

    if t == 'json':
        return jsonify(manager.get_reporte_filtrado(d, h, u, idc))

    return jsonify({"csv": manager.get_datos_excel(t, d, h, u, idc)})

@app.route('/api/tarifas', methods=['GET', 'POST'])
def api_tarifas():
    if request.method == 'POST':
        manager.set_tarifas(request.json['carro'], request.json['moto'], request.json.get('meta'))
        return jsonify({"status": "ok"})
    return jsonify({
        "carro": manager.get_tarifa_carro(),
        "moto": manager.get_tarifa_moto(),
        "meta": float(manager.config.get('METAS', 'diaria', fallback=500000))
    })

@app.route('/api/estadisticas/avanzadas')
def api_est_avanzadas():
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')
    idc = request.args.get('id_caja')
    return jsonify(manager.get_estadisticas_avanzadas(desde, hasta, idc))

@app.route('/api/metas', methods=['GET', 'POST'])
def api_metas():
    if session.get('role') != 'ADMIN': return jsonify({"status": "error"}), 403
    if request.method == 'POST':
        data = request.json
        manager.set_metas(data['diaria'], data['semanal'], data['mensual'], data['anual'])
        return jsonify({"status": "ok"})
    return jsonify({
        "diaria": float(manager.config.get('METAS', 'diaria', fallback=500000)),
        "semanal": float(manager.config.get('METAS', 'semanal', fallback=3000000)),
        "mensual": float(manager.config.get('METAS', 'mensual', fallback=12000000)),
        "anual": float(manager.config.get('METAS', 'anual', fallback=140000000))
    })

@app.route('/api/mensualidades', methods=['GET', 'POST', 'DELETE'])
def api_mensualidades():
    if session.get('role') != 'ADMIN': return jsonify({"status": "error"}), 403
    if request.method == 'POST':
        d = request.json
        manager.guardar_mensualidad(d['placa'], d['cliente'], d['inicio'], d['fin'], d['valor'])
        return jsonify({"status": "ok"})
    if request.method == 'DELETE':
        manager.eliminar_mensualidad(request.args.get('placa'))
        return jsonify({"status": "ok"})
    return jsonify(manager.get_mensualidades())

@app.route('/api/caja/<int:id_c>')
def api_get_caja(id_c):
    return jsonify(manager.get_caja_by_id(id_c))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
