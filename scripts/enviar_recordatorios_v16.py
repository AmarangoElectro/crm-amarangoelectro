#!/usr/bin/env python3
"""Mail diario de cobranzas de V16 para Angie y Maxi.

Misma configuración que crm-amarangoelectro/scripts/enviar_recordatorios.py:
mismo horario, destinatarios, remitente Gmail (SMTP_APP_PASSWORD) y criterio
(cobros de hoy y de los próximos 3 días, sin vencidos). La fuente es V16:
lee Cobranzas de STAGING mediante el puente operativo autorizado, con la
identidad de una cuenta habilitada, así que el servidor aplica sus permisos.
Sólo lee: no registra pagos ni modifica ventas.
"""
from __future__ import annotations

import html, json, os, re, smtplib, ssl, sys, urllib.request
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
DESTINATARIOS = {
    "Angie": "angie.palavecino96@gmail.com",
    "Maxi": "max.huracan73@gmail.com",
}
APP_URL = "https://amarango-v16-cajones-20260928.amarango-electro.chatgpt.site/administracion#cobranzas"
STAGING_REF = "ugujgbamqmrvxbvzxxou"
DIAS = 3
PAGINA = 100
NARANJA, AZUL = "#ff7900", "#123878"


def persona_canonica(nombre):
    """Unifica los nombres que el CRM considera la misma persona."""
    clave = re.sub(r"[^a-z0-9]+", " ", str(nombre or "").lower()).strip()
    if clave in {"angie", "angela", "angela palavecino", "angie palavecino"}: return "Angie"
    if clave in {"max", "maxi", "maximo", "maxi huracan"}: return "Maxi"
    return str(nombre or "").strip()


def parse_fecha(v):
    try: return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError): return None


def entero(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def proximas(filas, hoy):
    """Cuotas a recordar: vencen hoy o en los próximos 3 días. Nunca vencidas ni completas."""
    limite = hoy + timedelta(days=DIAS); out = []
    for f in filas:
        if f.get("collection_status") not in ("DUE_TODAY", "UPCOMING"): continue
        vence = parse_fecha(f.get("next_due_date"))
        if not vence or not (hoy <= vence <= limite): continue
        pagadas, total = entero(f.get("installments_paid")), entero(f.get("installments_total"))
        monto = f.get("installment_amount")
        monto = float(monto) if isinstance(monto, (int, float)) and not isinstance(monto, bool) and monto > 0 else None
        responsable = persona_canonica(f.get("responsible"))
        # Igual que el CRM: cada persona recibe lo suyo. Sin responsable reconocible, reciben ambos.
        personas = {responsable} if responsable in DESTINATARIOS else set(DESTINATARIOS)
        out.append({
            "venta": str(f.get("sale_id")), "vence": vence, "monto": monto,
            "num": pagadas + 1 if pagadas is not None else None, "total": total,
            "cliente": f.get("client_name") or "Cliente", "producto": f.get("product_label") or "—",
            "personas": personas,
        })
    return sorted(out, key=lambda x: (x["vence"], str(x["cliente"]).lower()))


def pesos(v): return "$" + f"{round(v):,}".replace(",", ".")


def cuando(f, h):
    d = (f - h).days
    return "Hoy" if d == 0 else "Mañana" if d == 1 else f"En {d} días"


def cuota_txt(x):
    if x["num"] and x["total"]: return f'Cuota {x["num"]}/{x["total"]}'
    return "Cuota"


def crear_email(items, hoy, remitente, destinatario, persona):
    total = sum(x["monto"] for x in items if x["monto"] is not None)
    sin_monto = sum(1 for x in items if x["monto"] is None)
    lineas, tarjetas = [], []
    for x in items:
        dia, fecha = cuando(x["vence"], hoy), x["vence"].strftime("%d/%m/%Y")
        monto = pesos(x["monto"]) if x["monto"] is not None else "Monto a confirmar"
        lineas.append(f'{dia} {fecha} · {x["cliente"]} · {x["producto"]} · {cuota_txt(x)} · {monto}')
        chip = NARANJA if dia == "Hoy" else AZUL
        tarjetas.append(
            f'<tr><td style="padding:0 0 10px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="background:#ffffff;border-radius:16px;border:1px solid #f1e3d3;box-shadow:0 2px 8px rgba(18,56,120,.06)">'
            f'<tr><td style="padding:14px 16px">'
            f'<span style="display:inline-block;background:{chip};color:#fff;font-size:12px;font-weight:bold;border-radius:999px;padding:3px 10px">{dia} · {fecha}</span>'
            f'<div style="font-size:16px;font-weight:bold;color:#18213a;margin-top:8px">{html.escape(str(x["cliente"]))}</div>'
            f'<div style="font-size:13px;color:#5b6475;margin-top:2px">{html.escape(str(x["producto"]))} · {cuota_txt(x)}</div>'
            f'</td><td align="right" style="padding:14px 16px;font-size:18px;font-weight:bold;color:{AZUL};white-space:nowrap">{monto}</td></tr></table></td></tr>')
    msg = EmailMessage()
    msg["Subject"] = f"🐝 AmarangoElectro · {len(items)} cobro(s) próximo(s) de {persona}"
    msg["From"], msg["To"] = remitente, destinatario
    resumen = f"Total a cobrar: {pesos(total)}" + (f" + {sin_monto} cuota(s) con monto a confirmar" if sin_monto else "")
    msg.set_content("Cobranzas de hoy y próximos 3 días\n\n" + "\n".join(lineas) + f"\n\n{resumen}\n\nAbrir Cobranzas: {APP_URL}\n")
    msg.add_alternative(f'''<!doctype html><html><body style="margin:0;background:#fff4ea;font-family:Arial,Helvetica,sans-serif;color:#18213a">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#fff4ea"><tr><td align="center" style="padding:18px 10px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px">
<tr><td style="background:{NARANJA};border-radius:20px 20px 0 0;padding:16px 18px">
<table role="presentation" cellpadding="0" cellspacing="0"><tr>
<td style="width:44px;height:44px;background:#ffffff;border-radius:12px;text-align:center;font-size:26px;line-height:44px">🐝</td>
<td style="padding-left:12px;color:#ffffff"><div style="font-size:12px;letter-spacing:.08em;font-weight:bold;opacity:.9">AMARANGOELECTRO · COBRANZAS</div>
<div style="font-size:19px;font-weight:bold">{len(items)} cobro(s) para {html.escape(persona)}</div></td></tr></table></td></tr>
<tr><td style="background:#fffaf5;padding:16px 14px 6px;border-radius:0 0 20px 20px">
<p style="margin:0 0 12px;font-size:13px;color:#5b6475">Hoy y próximos 3 días. Sin vencidos: solamente los pagos que toca recordar ahora.</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(tarjetas)}</table>
<p style="font-size:18px;margin:8px 4px 14px"><b>{html.escape(resumen)}</b></p>
<p style="margin:0 4px 18px"><a href="{APP_URL}" style="display:inline-block;background:{NARANJA};color:#ffffff;padding:12px 20px;text-decoration:none;border-radius:999px;font-weight:bold">Abrir Cobranzas</a></p>
</td></tr></table></td></tr></table></body></html>''', subtype="html")
    return msg


def config_staging():
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/"); key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    if not url or not key: raise RuntimeError("Faltan los secrets SUPABASE_URL y SUPABASE_SECRET_KEY de STAGING.")
    if STAGING_REF not in url: raise RuntimeError("SUPABASE_URL no es el STAGING autorizado de V16.")
    return url, key


def leer_cobranzas(lector):
    """Lee todas las cobranzas pendientes por el puente autorizado, con la identidad de `lector`."""
    url, key = config_staging(); filas, offset = [], 0
    while True:
        cuerpo = {"p_email": lector, "p_rpc": "v16_collections_list", "p_aal": "aal1",
                  "p_args": {"search_text": None, "status_filter": None, "include_complete": False, "row_limit": PAGINA, "row_offset": offset}}
        req = urllib.request.Request(f"{url}/rest/v1/rpc/v16_chatgpt_operational_bridge", data=json.dumps(cuerpo).encode(), method="POST",
                                     headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r: pagina = json.loads(r.read().decode())
        if not isinstance(pagina, list): raise RuntimeError("Respuesta inesperada de Cobranzas.")
        filas += pagina
        if len(pagina) < PAGINA: return filas
        offset += PAGINA


def main():
    hoy = datetime.now(TZ).date()
    lector = os.getenv("V16_REMINDER_READER_EMAIL", "").strip() or DESTINATARIOS["Maxi"]
    prueba = os.getenv("V16_REMINDER_FIXTURE", "").strip()
    filas = json.load(open(prueba, encoding="utf-8")) if prueba else leer_cobranzas(lector)
    if prueba and os.getenv("V16_REMINDER_TODAY"): hoy = parse_fecha(os.getenv("V16_REMINDER_TODAY"))
    items = proximas(filas, hoy)
    seco = os.getenv("V16_REMINDER_DRY_RUN") == "1" or bool(prueba)
    remitente = os.getenv("SMTP_EMAIL", "").strip() or DESTINATARIOS["Angie"]
    envios = [(p, d, [x for x in items if p in x["personas"]]) for p, d in DESTINATARIOS.items()]
    if seco:
        for persona, destinatario, propios in envios:
            if not propios: print(f"{persona}: sin cobranzas entre hoy y los próximos 3 días. No se envía mail."); continue
            msg = crear_email(propios, hoy, remitente, destinatario, persona)
            print(f"{persona}: PRUEBA, no enviado ({len(propios)} cuota(s)). Asunto: {msg['Subject']}")
        return
    password = os.getenv("SMTP_APP_PASSWORD", "").replace(" ", "")
    if not password: raise RuntimeError("Falta el secret SMTP_APP_PASSWORD en GitHub.")
    enviados = 0
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30) as smtp:
        smtp.login(remitente, password)
        for persona, destinatario, propios in envios:
            if not propios: print(f"{persona}: sin cobranzas entre hoy y los próximos 3 días. No se envía mail."); continue
            smtp.send_message(crear_email(propios, hoy, remitente, destinatario, persona)); enviados += 1
            print(f"{persona}: recordatorio enviado ({len(propios)} cuota(s)).")
    if not enviados: print("No hubo recordatorios para enviar hoy.")


if __name__ == "__main__":
    try: main()
    except Exception as error:
        print(f"Recordatorios V16: {error}", file=sys.stderr); sys.exit(1)
