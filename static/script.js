document.addEventListener('DOMContentLoaded', () => {
    const txtPlaca = document.getElementById('txtPlaca');
    const tipoVehiculo = document.getElementById('tipoVehiculo');
    const btnIngresar = document.getElementById('btnIngresar');
    const btnSalida = document.getElementById('btnSalida');
    const tablaCuerpo = document.getElementById('tablaCuerpo');
    const labelEstadoCaja = document.getElementById('labelEstadoCaja');
    const roleElem = document.getElementById('hiddenUserRole');
    const userRole = roleElem ? roleElem.value.trim().toUpperCase() : 'OPERARIO';
    const currentUser = document.getElementById('hiddenUserEmail')?.value.trim();
    const currentUserName = document.getElementById('txtUserNameTop')?.textContent.trim();

    let usersMap = {};
    const fetchUsersMap = async () => {
        const res = await fetch('/api/usuarios');
        const data = await res.json();
        data.forEach(u => usersMap[u.username.toLowerCase()] = u.name);
    };
    fetchUsersMap();

    // Notificación de Bienvenida
    const showWelcome = () => {
        const toast = document.getElementById('welcomeToast');
        // Para pruebas o si se desea ver siempre al recargar, se puede comentar la línea de sessionStorage
        if (toast) {
            setTimeout(() => {
                toast.classList.add('show');
                setTimeout(() => {
                    toast.classList.remove('show');
                }, 4000); // Aumentado a 4 segundos para que se aprecie mejor
            }, 800);
        }
    };
    showWelcome();

    const checkEstadoCaja = async () => {
        try {
            const res = await fetch('/api/caja/estado');
            const data = await res.json();
            const estaAbierta = data.estado === 'ABIERTA';

            if (estaAbierta) {
                if (data.supervisando) {
                    labelEstadoCaja.textContent = `SUPERVISANDO - ${data.usuario}`;
                    labelEstadoCaja.className = 'badge-caja badge-abierta';
                } else {
                    labelEstadoCaja.textContent = `ABIERTA - ${data.usuario}`;
                    labelEstadoCaja.className = 'badge-caja badge-abierta';
                }
                btnIngresar.disabled = false;
                btnSalida.disabled = false;
            } else {
                labelEstadoCaja.textContent = 'CERRADA';
                labelEstadoCaja.className = 'badge-caja badge-cerrada';
                btnIngresar.disabled = true;
                btnSalida.disabled = true;
            }

            const canManage = (userRole === 'ADMIN');
            labelEstadoCaja.onclick = canManage ? () => gestionarCaja() : null;
            labelEstadoCaja.style.cursor = canManage ? "pointer" : "default";

            return data;
        } catch (e) { labelEstadoCaja.textContent = 'ERROR CONEXIÓN'; }
    };

    function imprimirTicketPro(html) {
        const ventimp = window.open(' ', 'popimpr');
        ventimp.document.write(`<html><head><title>Imprimir</title><style>body { font-family: 'Arial', sans-serif; padding: 10px; width: 280px; font-size: 13px; line-height: 1.4; color: #000; } .header { text-align: center; font-weight: bold; border-bottom: 2px dashed #000; padding-bottom: 10px; margin-bottom: 10px; } .business-name { font-size: 18px; display: block; margin-bottom: 2px; text-transform: uppercase; } .business-info { font-size: 11px; font-weight: normal; display: block; margin-bottom: 5px; } .title { font-size: 14px; display: block; margin-top: 5px; text-decoration: underline; } .row { display: flex; justify-content: space-between; margin-bottom: 3px; } .placa-box { text-align: center; border: 2px solid #000; font-size: 28px; font-weight: bold; padding: 10px; margin: 10px 0; border-radius: 5px; } .total-box { border-top: 2px solid #000; border-bottom: 2px solid #000; padding: 5px 0; margin-top: 10px; font-weight: bold; font-size: 16px; text-align: center; } .footer { text-align: center; font-size: 11px; margin-top: 15px; border-top: 1px dashed #000; padding-top: 10px; font-style: italic; } @media print { body { width: 100%; } }</style></head><body>${html}</body></html>`);
        ventimp.document.close(); ventimp.focus(); setTimeout(() => { ventimp.print(); ventimp.close(); }, 300);
    }

    const infoParqueadero = `<span class="business-name">PARQUEADERO PIKOTEO</span><span class="business-info">Cra 8 # 5-32 Casco Antiguo, Floridablanca<br>Cel: 313 3088678</span>`;

    window.cerrarModal = () => {
        document.querySelectorAll('.modal').forEach(m => m.style.display = 'none');
    };

    window.abrirTurno = async () => {
        const usuario = document.getElementById('aperturaUsuario').value;
        const base = document.getElementById('aperturaBase').value;
        const res = await fetch('/api/caja/abrir', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ usuario, base })
        });
        const data = await res.json();
        if (data.status === 'ok') {
            cerrarModal();
            checkEstadoCaja();
        } else {
            alert(data.msg || 'Error al abrir caja');
        }
    };

    window.gestionarCaja = async () => {
        if (userRole !== 'ADMIN') return; // Seguridad extra: no hacer nada si no es ADMIN
        const data = await checkEstadoCaja();
        if (data.estado === 'CERRADA') {
            const usersRes = await fetch('/api/usuarios');
            const users = await usersRes.json();
            document.getElementById('aperturaUsuario').innerHTML = users.map(u => `<option value="${u.username}" ${u.username.toLowerCase()===currentUser.toLowerCase()?'selected':''}>${u.name}</option>`).join('');
            document.getElementById('modalApertura').style.display = 'block';
        } else {
            if (userRole === 'ADMIN' || data.usuario.toLowerCase() === currentUser.toLowerCase()) abrirModalCierreLoggro(data);
        }
    };

    window.verResumenCierre = async (id) => {
        const res = await fetch(`/api/caja/${id}`);
        const data = await res.json();
        if (data) abrirModalCierreLoggro(data, true);
    };

    async function abrirModalCierreLoggro(data, esSoloLectura = false) {
        document.getElementById('cuadreFechas').textContent = `Inicio: ${data.fecha_apertura} | Fin: ${data.fecha_cierre || 'EN CURSO'}`;
        document.getElementById('txtResponsableCierre').textContent = data.usuario;

        const isAdmin = (userRole === 'ADMIN');
        const isOwner = (data.usuario.toLowerCase() === currentUser.toLowerCase());
        const inEf = document.getElementById('inEfDig'), inQr = document.getElementById('inQrDig'), btnG = document.getElementById('btnGuardarCierreFinal');
        const chkCerrar = document.getElementById('chkCerrarCajaLoggro');

        // Configuración de permisos y visibilidad
        inEf.disabled = esSoloLectura || !(isAdmin || isOwner);
        inQr.disabled = esSoloLectura || !(isAdmin || isOwner);
        if(chkCerrar) chkCerrar.checked = data.fecha_cierre ? true : false;
        document.getElementById('panelSwitchCierre').style.display = (isAdmin && !data.fecha_cierre) ? 'block' : 'none';
        if(btnG) btnG.style.display = (esSoloLectura || data.fecha_cierre) ? 'none' : ((isAdmin || isOwner) ? 'block' : 'none');

        // Cargar valores
        if (data.fecha_cierre) {
            inEf.value = data.vts_ef_dig;
            inQr.value = data.vts_qr_dig;
            const t = data.vts_ef_dig + data.vts_qr_dig;
            document.getElementById('txtTotalLoggro').textContent = `$ ${t.toLocaleString()}`;
        } else {
            inEf.value = data.valores_actuales.efectivo;
            inQr.value = data.valores_actuales.qr;
            const t = data.valores_actuales.efectivo + data.valores_actuales.qr;
            document.getElementById('txtTotalLoggro').textContent = `$ ${t.toLocaleString()}`;
        }

        document.getElementById('modalCuadre').style.display = 'block';
    }

    window.recalcularTotalLoggro = () => {
        const t = (parseFloat(document.getElementById('inEfDig').value) || 0) + (parseFloat(document.getElementById('inQrDig').value) || 0);
        document.getElementById('txtTotalLoggro').textContent = `$ ${t.toLocaleString()}`;
    };

    window.guardarCambiosCuadre = async () => {
        const cerrado = document.getElementById('chkCerrarCajaLoggro').checked;
        const u = document.getElementById('txtResponsableCierre').textContent;
        const body = { ef_dig: document.getElementById('inEfDig').value, qr_dig: document.getElementById('inQrDig').value, usuario: u };
        if (cerrado) {
            if (userRole !== 'ADMIN') return alert('Solo el administrador puede cerrar la caja.');
            if (!confirm(`¿Cerrar caja definitivamente?`)) return;
            await fetch('/api/caja/cerrar', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
        }
        cerrarModal(); checkEstadoCaja(); if(window.cargarReportes) cargarReportes();
    };

    window.mostrarSeccion = (id) => {
        document.querySelectorAll('.seccion').forEach(s => s.style.display = 'none');
        document.querySelectorAll('.menu-item').forEach(m => m.classList.remove('active'));
        const s = document.getElementById(`seccion-${id}`); if(s) s.style.display = 'block';

        // ACTIVAR CARGADORES AUTOMÁTICOS
        if (id === 'cuadres') cargarReportes();
        if (id === 'reportes') cargarListaCajasExcel();
        if (id === 'estadisticas') { cargarEstadisticas(); cargarListaCajasEst(); }
        if (id === 'auditoria') cargarAuditoria();
        if (id === 'tarifas') cargarTarifas();
        if (id === 'usuarios') cargarUsuarios();
        if (id === 'mensualidades') cargarMensualidades();
    };

    async function cargarListaCajasExcel() {
        const res = await fetch('/api/reportes');
        const data = await res.json();
        const sel = document.getElementById('repCajaId'); if(!sel) return;
        sel.innerHTML = '<option value="">-- Todas las cajas --</option>';
        data.forEach(c => { const opt = document.createElement('option'); opt.value = c.id; opt.textContent = `ID: ${c.id} | ${usersMap[c.usuario.toLowerCase()] || c.usuario} | ${c.fecha_apertura}`; sel.appendChild(opt); });
    }

    async function cargarListaCajasEst() {
        const res = await fetch('/api/reportes');
        const data = await res.json();
        const sel = document.getElementById('estCajaId'); if(!sel) return;
        sel.innerHTML = '<option value="">-- Todas las cajas --</option>';
        data.forEach(c => { const opt = document.createElement('option'); opt.value = c.id; opt.textContent = `ID: ${c.id} | ${usersMap[c.usuario.toLowerCase()] || c.usuario} | ${c.fecha_apertura}`; sel.appendChild(opt); });
    }

    window.cargarReportes = async function() {
        const tbody = document.getElementById('tablaReportesCuerpo'); if (!tbody) return;
        const inc = document.getElementById('chkIncluirEliminados')?.checked || false;
        const res = await (await fetch(`/api/reportes?incluir_eliminados=${inc}`)).json();
        const est = await (await fetch('/api/caja/estado')).json();
        let lista = [...res];
        if (est.estado === 'ABIERTA') {
            const yaEsta = lista.find(x => x.fecha_apertura === est.fecha_apertura && x.usuario === est.usuario);
            if(!yaEsta) lista.unshift({ id: 'ACTIVA', fecha_apertura: est.fecha_apertura, fecha_cierre: '', usuario: est.usuario, base: est.base });
        }
        tbody.innerHTML = lista.map(r => `
            <tr class="${!r.fecha_cierre ? 'fila-abierta' : ''} ${r.estado === 'ELIMINADO' ? 'fila-eliminada' : ''}">
                <td>${r.id}</td>
                <td>${r.fecha_apertura}</td>
                <td>${r.fecha_cierre || 'EN CURSO'}</td>
                <td>${usersMap[r.usuario.toLowerCase()] || r.usuario}</td>
                <td>$${Number(r.base).toLocaleString()}</td>
                <td>${r.fecha_cierre ? 'Si' : 'No'}</td>
                <td style="display:flex; gap:5px;">
                    <button class="btn-loggro-red" onclick="${!r.fecha_cierre ? `abrirPorId('${r.usuario}')` : `verResumenCierre('${r.id}')`}">${!r.fecha_cierre ? 'Cerrar' : 'Ver'}</button>
                    <button class="btn-ver-facturas" onclick="verFacturasCaja('${r.fecha_apertura}', '${r.fecha_cierre || 'EN CURSO'}', '${r.usuario}')">Fac.</button>
                    ${userRole === 'ADMIN' && r.id !== 'ACTIVA' ?
                        (r.estado === 'ELIMINADO' ?
                            `<button class="btn-icon-loggro" onclick="recuperarCaja('${r.id}')" title="Recuperar">🔄</button>` :
                            `<button class="btn-icon-loggro" onclick="eliminarCaja('${r.id}')" title="Eliminar">🗑️</button>`
                        ) : ''
                    }
                </td>
            </tr>`).join('');
    };

    window.eliminarCaja = async (id) => {
        if (!confirm('¿Seguro que desea eliminar este cuadre de caja?')) return;
        const res = await fetch('/api/reportes/eliminar', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ id })
        });
        if ((await res.json()).status === 'ok') cargarReportes();
    };

    window.recuperarCaja = async (id) => {
        const res = await fetch('/api/reportes/recuperar', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ id })
        });
        if ((await res.json()).status === 'ok') cargarReportes();
    };

    window.abrirPorId = async (u) => { const st = await (await fetch('/api/caja/estado?usuario=' + u)).json(); abrirModalCierreLoggro(st); };

    window.verFacturasCaja = async (inicio, fin, usuario) => {
        mostrarSeccion('facturas');
        const data = await (await fetch(`/api/tickets/rango?inicio=${inicio}&fin=${fin}&usuario=${usuario}`)).json();
        document.getElementById('tablaFacturasCuerpo').innerHTML = data.map(t => `<tr><td>${t.ingreso}</td><td>${String(t.id).padStart(5, '0')}</td><td>${t.tipo}</td><td>${t.placa}</td><td>${t.estado}</td><td>${t.medio_pago||'---'}</td><td>$${Number(t.valor).toLocaleString()}</td><td style="display:flex; gap:5px; justify-content:center;"><button class="btn-icon-loggro" onclick="reimprimirTicket('${t.id}')">🖨️</button><button class="btn-icon-loggro" onclick="solicitarDescuento('${t.id}')">💰</button></td></tr>`).join('');
    };

    window.solicitarDescuento = async (id) => {
        const monto = prompt('VALOR A DESCONTAR ($):'); if (!monto || isNaN(monto)) return;
        const motivo = prompt('MOTIVO DEL DESCUENTO:'); if (!motivo) return alert('Motivo obligatorio');
        const res = await fetch('/api/ticket/descuento', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ id, monto, motivo }) });
        const data = await res.json(); if(data.status === 'error') alert(data.msg); else { alert('Aplicado'); reimprimirTicket(id); }
    };

    window.reimprimirTicket = async (id) => {
        const t = await (await fetch(`/api/ticket/${id}`)).json();
        let html = (t.estado === 'ACTIVO') ? `<div class="header">${infoParqueadero}<span class="title">REIMPRESIÓN INGRESO</span></div><div class="row"><span>Fecha:</span><span>${t.ingreso}</span></div><div class="row"><span>Vehículo:</span><span>${t.tipo}</span></div><div class="placa-box">${t.placa}</div><div class="footer">CONSERVE ESTE TICKET</div>` : `<div class="header">${infoParqueadero}<span class="title">REIMPRESIÓN PAGO</span></div><div class="row"><span>Placa:</span><strong>${t.placa}</strong></div><div class="row"><span>Entrada:</span><span>${t.ingreso}</span></div><div class="row"><span>Salida:</span><span>${t.salida}</span></div><div class="row"><span>Medio:</span><span>${t.medio_pago}</span></div><div class="total-box">TOTAL PAGADO: $${Number(t.valor).toLocaleString()}</div><div class="footer">GRACIAS POR SU VISITA</div>`;
        imprimirTicketPro(html);
    };

    window.cargarAuditoria = async function() {
        const d = document.getElementById('audDesde')?.value, h = document.getElementById('audHasta')?.value, a = document.getElementById('audAccion')?.value;
        const data = await (await fetch(`/api/auditoria?accion=${a}&desde=${d}&hasta=${h}`)).json();
        document.getElementById('tablaAuditoriaCuerpo').innerHTML = data.map(log => `<tr><td>${log.fecha}</td><td>${log.usuario}</td><td>${log.accion}</td><td>${log.detalle}</td></tr>`).join('');
    };

    async function cargarTarifas() {
        const d = await (await fetch('/api/tarifas')).json();
        document.getElementById('cfgTarifaCarro').value = d.carro;
        document.getElementById('cfgTarifaMoto').value = d.moto;
        if(document.getElementById('cfgMetaDiaria')) document.getElementById('cfgMetaDiaria').value = d.meta;
    }
    window.guardarTarifas = async () => {
        const body = {
            carro: document.getElementById('cfgTarifaCarro').value,
            moto: document.getElementById('cfgTarifaMoto').value,
            meta: document.getElementById('cfgMetaDiaria')?.value
        };
        await fetch('/api/tarifas', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
        alert('Guardado');
    };
    async function cargarUsuarios() {
        const d = await (await fetch('/api/usuarios')).json();
        document.getElementById('tablaUsuariosCuerpo').innerHTML = d.map(u => `
            <tr>
                <td>${u.name}</td>
                <td style="font-weight: bold; color: #333;">${u.username}</td>
                <td><span class="badge-caja ${u.role === 'ADMIN' ? 'badge-cerrada' : 'badge-abierta'}" style="font-size: 11px;">${u.role || 'OPERARIO'}</span></td>
                <td style="text-align: center;">
                    ${u.username.toLowerCase() === 'admin' || u.username.toLowerCase() === currentUser.toLowerCase()
                        ? '<span style="color:#ccc; font-size:11px;">Protegido</span>'
                        : `<button class="btn-icon-loggro" onclick="eliminarUsuario('${u.username}')" title="Eliminar Usuario">🗑️</button>`
                    }
                </td>
            </tr>`).join('');
    }

    window.eliminarUsuario = async (u) => {
        if(confirm(`¿Está seguro de eliminar al usuario ${u}?\nEsta acción no se puede deshacer.`)) {
            const res = await fetch(`/api/usuarios?username=${u}`, {method:'DELETE'});
            if (res.ok) cargarUsuarios();
            else alert("Error al eliminar el usuario.");
        }
    };

    window.guardarUsuario = async () => {
        const name = document.getElementById('usrRealName').value.trim();
        const email = document.getElementById('usrNombre').value.trim();
        const password = document.getElementById('usrClave').value;
        const role = document.getElementById('usrRol').value;

        // Validaciones básicas
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!name) return alert("Por favor ingrese el nombre del usuario.");
        if (!emailRegex.test(email)) return alert("Por favor ingrese un correo electrónico válido.");
        if (password.length < 6) return alert("La contraseña debe tener al menos 6 caracteres.");

        const res = await fetch('/api/usuarios', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ name: name, username: email, password: password, role: role })
        });

        if (res.ok) {
            alert("Usuario creado correctamente.");
            document.getElementById('usrRealName').value = '';
            document.getElementById('usrNombre').value = '';
            document.getElementById('usrClave').value = '';
            cargarUsuarios();
        } else {
            alert("Error al crear el usuario. Es posible que ya exista.");
        }
    };
    async function cargarMensualidades() {
        const d = await (await fetch('/api/mensualidades')).json();
        const hoy = new Date();
        document.getElementById('tablaMensualidadesCuerpo').innerHTML = d.map(m => {
            const fechaFin = new Date(m.fecha_fin.split('/').reverse().join('-') + 'T00:00:00');
            const diffTime = fechaFin - hoy;
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

            let badgeClass = 'badge-abierta';
            let statusText = 'Activo';

            if (diffDays < 0) {
                badgeClass = 'badge-cerrada';
                statusText = 'Vencido';
            } else if (diffDays <= 5) {
                badgeClass = 'badge-cerrada'; // Usamos rojo para avisar pronto vencimiento
                statusText = `Vence en ${diffDays} días`;
            }

            return `
            <tr>
                <td style="font-weight: bold;">${m.placa}</td>
                <td>${m.cliente}</td>
                <td>${m.fecha_inicio}</td>
                <td>${m.fecha_fin}</td>
                <td>$${Number(m.valor_pagado).toLocaleString()}</td>
                <td><span class="badge-caja ${badgeClass}">${statusText}</span></td>
                <td style="text-align: center;">
                    <button class="btn-icon-loggro" onclick="eliminarMensualidad('${m.placa}')">🗑️</button>
                </td>
            </tr>`;
        }).join('');
    }

    window.eliminarMensualidad = async (p) => {
        if(confirm(`¿Desea eliminar la mensualidad de la placa ${p}?`)) {
            await fetch(`/api/mensualidades?placa=${p}`, {method:'DELETE'});
            cargarMensualidades();
        }
    };

    window.guardarMensualidad = async () => {
        const p = document.getElementById('mPlaca').value.toUpperCase().trim();
        const c = document.getElementById('mCliente').value.trim();
        const i = document.getElementById('mInicio').value;
        const f = document.getElementById('mFin').value;
        const v = document.getElementById('mValor').value;

        if(!p || !c || !i || !f || !v) return alert("Por favor complete todos los campos.");

        await fetch('/api/mensualidades', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({
                placa: p,
                cliente: c,
                inicio: i.split('-').reverse().join('/'),
                fin: f.split('-').reverse().join('/'),
                valor: v
            })
        });

        // Limpiar campos
        document.getElementById('mPlaca').value = '';
        document.getElementById('mCliente').value = '';
        cargarMensualidades();
        alert("Mensualidad registrada correctamente.");
    };

    // Auto-ajustar 30 días en mensualidades
    const inputMInicio = document.getElementById('mInicio');
    if(inputMInicio) {
        const hoy = new Date().toISOString().split('T')[0];
        inputMInicio.value = hoy;

        const setFechaFin = () => {
            const fecha = new Date(inputMInicio.value);
            fecha.setDate(fecha.getDate() + 30);
            document.getElementById('mFin').value = fecha.toISOString().split('T')[0];
        };

        inputMInicio.addEventListener('change', setFechaFin);
        setFechaFin();
    }

    window.consultarReporte = async () => {
        const d = document.getElementById('repDesde').value;
        const h = document.getElementById('repHasta').value;
        const idc = null; // Eliminamos filtro por caja

        if (!d || !h) return alert("Por favor seleccione un rango de fechas.");

        const res = await fetch(`/api/reportes/excel?tipo=json&desde=${d}&hasta=${h}`);
        const data = await res.json();

        const tbody = document.getElementById('tablaReportePreviewCuerpo');
        const msg = document.getElementById('msgNoReporte');
        const btnContainer = document.getElementById('btnDescargarContainer');

        if (data.length === 0) {
            tbody.innerHTML = '';
            msg.style.display = 'block';
            msg.innerHTML = "No se encontraron registros para los filtros seleccionados.";
            if(btnContainer) btnContainer.style.display = 'none';
        } else {
            msg.style.display = 'none';
            if(btnContainer) btnContainer.style.display = 'block';
            tbody.innerHTML = data.map(t => `
                <tr>
                    <td>${String(t.id).padStart(5, '0')}</td>
                    <td style="font-weight:bold;">${t.placa}</td>
                    <td>${t.tipo}</td>
                    <td>${t.ingreso}</td>
                    <td>${t.salida}</td>
                    <td>${t.medio_pago}</td>
                    <td style="font-weight:bold; color:#b40000;">$${Number(t.valor).toLocaleString()}</td>
                </tr>
            `).join('');
        }
    };

    window.descargarReporteExcel = async (tipo) => {
        const d = document.getElementById('repDesde').value;
        const h = document.getElementById('repHasta').value;
        const res = await fetch(`/api/reportes/excel?tipo=${tipo}&desde=${d}&hasta=${h}`);
        const data = await res.json();
        const blob = new Blob(["\uFEFF" + data.csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = `Reporte_Parqueadero.csv`;
        link.click();
    };

    // Inicializar fechas de reportes con hoy (desde 00:00 hasta ahora)
    const initReportDates = () => {
        const d = new Date();
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const hour = String(d.getHours()).padStart(2, '0');
        const min = String(d.getMinutes()).padStart(2, '0');

        if(document.getElementById('repDesde')) document.getElementById('repDesde').value = `${year}-${month}-${day}T00:00`;
        if(document.getElementById('repHasta')) document.getElementById('repHasta').value = `${year}-${month}-${day}T${hour}:${min}`;
    };
    initReportDates();

    let chartVentas, chartSieteDias, gauges = {};
    window.cargarEstadisticas = async () => {
        const d = document.getElementById('estDesde').value;
        const h = document.getElementById('estHasta').value;
        const idc = document.getElementById('estCajaId').value;
        const res = await fetch(`/api/estadisticas/avanzadas?desde=${d}&hasta=${h}&id_caja=${idc}`);
        const data = await res.json();

        // Actualizar Dash Cards de Metas
        const m = data.dashboard_metas;
        const updateMetaCard = (id, suffix, total, meta) => {
            const totalEl = document.getElementById(`stat${id}Total`);
            const metaEl = document.getElementById(`stat${id}Meta`);
            const pctEl = document.getElementById(`txtPctMeta${suffix}`);

            if(totalEl) totalEl.textContent = `$${total.toLocaleString()}`;
            if(metaEl) metaEl.textContent = `$${meta.toLocaleString()}`;

            const pct = meta > 0 ? Math.min(100, Math.round((total / meta) * 100)) : 0;
            if(pctEl) pctEl.textContent = `${pct}%`;

            // Dibujar Mini Gauge con Chart.js
            const canvasId = `gaugeMeta${suffix}`;
            const ctx = document.getElementById(canvasId)?.getContext('2d');
            if (ctx) {
                if (gauges[canvasId]) gauges[canvasId].destroy();
                gauges[canvasId] = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        datasets: [{
                            data: [pct, 100 - pct],
                            backgroundColor: ['#b40000', '#f0f0f0'],
                            borderWidth: 0
                        }]
                    },
                    options: {
                        cutout: '80%',
                        responsive: false,
                        plugins: { tooltip: { enabled: false }, legend: { display: false } }
                    }
                });
            }
        };

        updateMetaCard('Hoy', 'Diaria', m.hoy.total, m.hoy.meta);
        updateMetaCard('Semana', 'Semanal', m.semana.total, m.semana.meta);
        updateMetaCard('Mes', 'Mensual', m.mes.total, m.mes.meta);
        updateMetaCard('Anio', 'Anual', m.anio.total, m.anio.meta);

        // Actualizar Conteos de Periodo
        document.getElementById('statCantCarrosDash').textContent = data.conteos.CARRO;
        document.getElementById('statDineroCarrosDash').textContent = `$${data.dinero.CARRO.toLocaleString()}`;
        document.getElementById('statCantMotosDash').textContent = data.conteos.MOTO;
        document.getElementById('statDineroMotosDash').textContent = `$${data.dinero.MOTO.toLocaleString()}`;

        // Gráfico de Ventas por Hora
        const ctxVentas = document.getElementById('chartVentasHoras').getContext('2d');
        if (chartVentas) chartVentas.destroy();
        chartVentas = new Chart(ctxVentas, {
            type: 'line',
            data: {
                labels: Object.keys(data.por_hora).map(h => `${h}:00`),
                datasets: [
                    { label: 'Carros', data: Object.values(data.por_hora).map(v => v.CARRO), borderColor: '#b40000', backgroundColor: 'rgba(180,0,0,0.1)', fill: true, tension: 0.4 },
                    { label: 'Motos', data: Object.values(data.por_hora).map(v => v.MOTO), borderColor: '#333', backgroundColor: 'rgba(51,51,51,0.1)', fill: true, tension: 0.4 }
                ]
            },
            options: { responsive: true, plugins: { legend: { position: 'bottom' } }, scales: { y: { beginAtZero: true } } }
        });

        // Gráfico de 7 Días
        const ctxSiete = document.getElementById('chartSieteDias').getContext('2d');
        if (chartSieteDias) chartSieteDias.destroy();
        chartSieteDias = new Chart(ctxSiete, {
            type: 'bar',
            data: {
                labels: Object.keys(data.historial_7_dias).map(f => {
                    const parts = f.split('-');
                    const d = new Date(parts[0], parts[1]-1, parts[2]);
                    return d.toLocaleDateString('es-ES', { weekday: 'long' });
                }),
                datasets: [{
                    label: 'Recaudo ($)',
                    data: Object.values(data.historial_7_dias),
                    backgroundColor: '#b40000',
                    borderRadius: 5
                }]
            },
            options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
        });

        // Tabla de Consolidado por Horas
        const tbody = document.getElementById('tablaEstHorasCuerpo');
        if (tbody) {
            tbody.innerHTML = Object.entries(data.por_hora)
                .filter(([h, v]) => (v.CARRO + v.MOTO) > 0)
                .map(([h, v]) => `
                    <tr>
                        <td>${h}:00</td>
                        <td>$${v.CARRO.toLocaleString()}</td>
                        <td>$${v.MOTO.toLocaleString()}</td>
                        <td>${v.cnt_c}</td>
                        <td>${v.cnt_m}</td>
                        <td style="font-weight:bold; color:#b40000;">$${(v.CARRO + v.MOTO).toLocaleString()}</td>
                    </tr>
                `).join('');
        }
    };

    window.abrirModalMetas = async () => {
        const d = await (await fetch('/api/metas')).json();
        document.getElementById('mDiaria').value = d.diaria;
        document.getElementById('mSemanal').value = d.semanal;
        document.getElementById('mMensual').value = d.mensual;
        document.getElementById('mAnual').value = d.anual;
        document.getElementById('modalMetas').style.display = 'block';
    };

    window.abrirModalUltimaHora = () => {
        document.getElementById('modalUltimaHora').style.display = 'block';
        cargarTicketsUltimaHora();
    };

    window.cargarTicketsUltimaHora = async () => {
        const ahora = new Date();
        const haceUnaHora = new Date(ahora.getTime() - (60 * 60 * 1000));

        // Usamos la API de tickets rango con el formato esperado
        const fmt = (d) => d.toLocaleString('es-ES', { day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit', second:'2-digit' }).replace(',', '');

        const res = await fetch(`/api/tickets/rango?inicio=${fmt(haceUnaHora)}&fin=EN CURSO`);
        const data = await res.json();

        // Filtrar solo los que salieron en la última hora y están pagados
        const filtrados = data.filter(t => t.estado === 'PAGADO');

        const tbody = document.getElementById('tablaUltimaHoraCuerpo');
        const msg = document.getElementById('msgNoTickets');

        if (filtrados.length === 0) {
            tbody.innerHTML = '';
            msg.style.display = 'block';
        } else {
            msg.style.display = 'none';
            tbody.innerHTML = filtrados.reverse().map(t => `
                <tr>
                    <td>${String(t.id).padStart(5, '0')}</td>
                    <td style="font-weight:bold;">${t.placa}</td>
                    <td>${t.tipo}</td>
                    <td>${t.salida.split(' ')[1]}</td>
                    <td>$${Number(t.valor).toLocaleString()}</td>
                    <td><button class="btn-icon-loggro" onclick="reimprimirTicket('${t.id}')">🖨️</button></td>
                </tr>
            `).join('');
        }
    };

    window.guardarMetas = async () => {
        const body = {
            diaria: document.getElementById('mDiaria').value,
            semanal: document.getElementById('mSemanal').value,
            mensual: document.getElementById('mMensual').value,
            anual: document.getElementById('mAnual').value
        };
        await fetch('/api/metas', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify(body)
        });
        alert('Metas guardadas correctamente');
        cerrarModal();
        cargarEstadisticas();
    };

    if (txtPlaca) {
        txtPlaca.addEventListener('input', () => {
            txtPlaca.value = txtPlaca.value.toUpperCase().replace(/\s/g, '');
            let v = txtPlaca.value;
            if (v.match(/^[A-Z]{3}\d{3}$/)) tipoVehiculo.value = 'CARRO';
            else if (v.match(/^[A-Z]{3}\d{2}[A-Z]{1,2}X?$/)) tipoVehiculo.value = 'MOTO';
        });
    }

    if (btnIngresar) {
        btnIngresar.onclick = async () => {
            const placa = txtPlaca.value;
            const tipo = tipoVehiculo.value;
            if (!placa) return alert('Ingrese una placa');
            const res = await fetch('/api/ingreso', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ placa, tipo })
            });
            const data = await res.json();
            if (data.status === 'error') alert(data.msg);
            else {
                // Imprimir Ticket de Ingreso
                const t = data.datos;
                const html = `<div class="header">${infoParqueadero}<span class="title">TICKET DE INGRESO</span></div><div class="row"><span>ID:</span><span>${String(t.id).padStart(5, '0')}</span></div><div class="row"><span>Fecha:</span><span>${t.ingreso}</span></div><div class="row"><span>Vehículo:</span><span>${t.tipo}</span></div><div class="placa-box">${t.placa}</div><div class="footer">CONSERVE ESTE TICKET HASTA LA SALIDA</div>`;
                imprimirTicketPro(html);
                txtPlaca.value = '';
                setTimeout(() => location.reload(), 500);
            }
        };
    }

    if (btnSalida) {
        btnSalida.onclick = async () => {
            const placa = txtPlaca.value;
            const medio = prompt('Medio de pago (EFECTIVO/QR):', 'EFECTIVO')?.toUpperCase();
            if (!placa || !medio) return;
            const res = await fetch('/api/salida', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ placa, medio })
            });
            const data = await res.json();
            if (data.status === 'error') alert(data.msg);
            else {
                // Imprimir Ticket de Salida
                const t = data.datos;
                const html = `<div class="header">${infoParqueadero}<span class="title">RECIBO DE PAGO</span></div><div class="row"><span>ID:</span><span>${String(t.id).padStart(5, '0')}</span></div><div class="row"><span>Placa:</span><strong>${t.placa}</strong></div><div class="row"><span>Entrada:</span><span>${t.ingreso}</span></div><div class="row"><span>Salida:</span><span>${t.salida}</span></div><div class="row"><span>Tiempo:</span><span>${t.minutos} min</span></div><div class="row"><span>Medio:</span><span>${t.medio}</span></div><div class="total-box">TOTAL PAGADO: $${Number(t.total).toLocaleString()}</div><div class="footer">¡GRACIAS POR SU VISITA!</div>`;
                imprimirTicketPro(html);
                txtPlaca.value = '';
                setTimeout(() => location.reload(), 500);
            }
        };
    }

    // Inicializar fechas de estadísticas con hoy
    const hoy = new Date().toISOString().split('T')[0];
    if(document.getElementById('estDesde')) document.getElementById('estDesde').value = hoy;
    if(document.getElementById('estHasta')) document.getElementById('estHasta').value = hoy;

    checkEstadoCaja();
});
