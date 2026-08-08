#!/usr/bin/env python3
"""Mail diario de cobranzas para Angie y Maxi."""
from __future__ import annotations

import calendar, html, json, math, os, re, smtplib, ssl, urllib.parse, urllib.request
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
DESTINATARIOS = ("angie.palavecino96@gmail.com", "max.huracan73@gmail.com")
CRM_URL = "https://amarangoelectro.github.io/crm-amarangoelectro/"
PORCENTAJES = {2: 15, 3: 36, 4: 55, 5: 66, 6: 78}

def config_supabase():
    url, key = os.getenv("SUPABASE_URL", "").strip(), os.getenv("SUPABASE_KEY", "").strip()
    if url and key: return url.rstrip("/"), key
    index = (Path(__file__).resolve().parents[1] / "index.html").read_text(encoding="utf-8")
    mu = re.search(r'const\s+SUPABASE_URL\s*=\s*["\']([^"\']+)', index)
    mk = re.search(r'const\s+SUPABASE_KEY\s*=\s*["\']([^"\']+)', index)
    if not mu or not mk: raise RuntimeError("No encontré la configuración de Supabase.")
    return mu.group(1).rstrip("/"), mk.group(1)

def supabase_get(tabla):
    url, key = config_supabase()
    req = urllib.request.Request(f"{url}/rest/v1/{tabla}?select=*", headers={"apikey":key,"Authorization":f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read().decode())

def parse_fecha(v):
    try: return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError): return None

def sumar_meses(f, meses):
    total = f.year*12 + f.month-1 + meses
    year, m0 = divmod(total, 12); month = m0+1
    return date(year, month, min(f.day, calendar.monthrange(year, month)[1]))

def redondeo_js(v):
    """Equivale a Math.round para los importes positivos del CRM."""
    return math.floor(v + 0.5)

def cuotas_plan(precio, n):
    if n <= 1: return [redondeo_js(precio/500)*500]
    if n <= 6: total = precio*(1+PORCENTAJES[n]/100)
    elif n <= 12:
        total = precio*1.78
        for k in range(7,n+1): total *= 1.05 if k==7 else 1.03
    else: total = precio
    cuota = redondeo_js((total/n)/1000)*1000
    return [cuota]*n

def cuotas_venta(v):
    try: n=max(1,int(v.get("cuotas") or 1))
    except (TypeError,ValueError): n=1
    inicio=parse_fecha(v.get("fecha"))
    if not inicio: return []
    manual=float(v.get("montoCuota") or 0)
    montos=[manual]*n if manual>0 else cuotas_plan(float(v.get("precioVenta") or 0),n)
    try: pagadas=int(v.get("pagadas") or 0)
    except (TypeError,ValueError): pagadas=0
    abonos=v.get("abonos") if isinstance(v.get("abonos"),dict) else {}
    apl=abonos.get("__fechasAplazadas",{}); apl=apl if isinstance(apl,dict) else {}
    salida=[]
    for i in range(n):
        num=i+1
        if i<pagadas: continue
        vence=parse_fecha(v.get("venceManual")) if i==0 and v.get("venceManual") else None
        if not vence: vence=inicio if n<=1 else (inicio+timedelta(days=i*15) if v.get("quincenal") is True else sumar_meses(inicio,i))
        vence=parse_fecha(apl.get(str(num),apl.get(num))) or vence
        try: abono=float(abonos.get(str(num),abonos.get(num,0)) or 0)
        except (TypeError,ValueError): abono=0
        restante=max(0,float(montos[i])-abono)
        if restante>0: salida.append({"num":num,"total":n,"vence":vence,"monto":restante})
    return salida

def proximas(ventas, clientes, hoy):
    nombres={str(c.get("id")):c.get("nombre") or "Cliente" for c in clientes}; limite=hoy+timedelta(days=3); out=[]
    for v in ventas:
        for c in cuotas_venta(v):
            if hoy <= c["vence"] <= limite:
                out.append({**c,"cliente":nombres.get(str(v.get("clienteId")),"Cliente"),"producto":v.get("producto") or "—"})
    return sorted(out,key=lambda x:(x["vence"],str(x["cliente"]).lower()))

def pesos(v): return "$"+f"{round(v):,}".replace(",", ".")
def cuando(f,h):
    d=(f-h).days
    return "Hoy" if d==0 else "Mañana" if d==1 else f"En {d} días"

def crear_email(items,hoy,remitente):
    th=[]; tt=[]; total=0
    for x in items:
        total+=x["monto"]; dia=cuando(x["vence"],hoy); fecha=x["vence"].strftime("%d/%m/%Y")
        tt.append(f'{dia} {fecha} · {x["cliente"]} · {x["producto"]} · Cuota {x["num"]}/{x["total"]} · {pesos(x["monto"])}')
        th.append(f'<tr><td>{dia}<br><small>{fecha}</small></td><td><b>{html.escape(str(x["cliente"]))}</b></td><td>{html.escape(str(x["producto"]))}</td><td>Cuota {x["num"]}/{x["total"]}</td><td style="text-align:right"><b>{pesos(x["monto"])}</b></td></tr>')
    msg=EmailMessage(); msg["Subject"]=f"🐝 AmarangoElectro · {len(items)} cobro(s) próximo(s)"; msg["From"]=remitente; msg["To"]=', '.join(DESTINATARIOS)
    msg.set_content("Cobranzas de hoy y próximos 3 días\n\n"+'\n'.join(tt)+f"\n\nTotal a cobrar: {pesos(total)}\n\nAbrir Cobranzas: {CRM_URL}\n")
    msg.add_alternative(f'''<html><body style="font-family:Arial,sans-serif;color:#18213a"><h2>🐝 Cobranzas de hoy y próximos 3 días</h2><p>Sin vencidos: solamente los pagos que toca recordar ahora.</p><div style="overflow-x:auto"><table style="border-collapse:collapse;width:100%;max-width:900px" cellpadding="9" border="1"><thead style="background:#123878;color:white"><tr><th>Cuándo</th><th>Cliente</th><th>Producto</th><th>Cuota</th><th>Monto</th></tr></thead><tbody>{''.join(th)}</tbody></table></div><p style="font-size:18px"><b>Total a cobrar: {pesos(total)}</b></p><p><a href="{CRM_URL}" style="background:#ff7900;color:white;padding:11px 18px;text-decoration:none;border-radius:8px">Abrir Cobranzas</a></p></body></html>''',subtype="html")
    return msg

def main():
    password=os.getenv("SMTP_APP_PASSWORD","").replace(" ",""); remitente=os.getenv("SMTP_EMAIL",DESTINATARIOS[0]).strip()
    if not password: raise RuntimeError("Falta el secret SMTP_APP_PASSWORD en GitHub.")
    hoy=datetime.now(TZ).date(); items=proximas(supabase_get("ventas"),supabase_get("clientes"),hoy)
    if not items:
        print("No hay cobranzas entre hoy y los próximos 3 días. No se envía mail."); return
    with smtplib.SMTP_SSL("smtp.gmail.com",465,context=ssl.create_default_context(),timeout=30) as smtp:
        smtp.login(remitente,password); smtp.send_message(crear_email(items,hoy,remitente))
    print(f"Recordatorio enviado correctamente: {len(items)} cuota(s).")

if __name__ == "__main__": main()
