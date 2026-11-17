#!/usr/bin/env python3
"""CLI mínima da UazAPI (uazapiGO v2). Credenciais: UAZAPI_BASE_URL e UAZAPI_INSTANCE_TOKEN
no ambiente ou num .env (procura --env, depois ./.env, depois o .env ao lado deste script).
Nunca imprime o token."""
import argparse, base64, json, os, sys, time, urllib.request, urllib.error

def load_env(path_hint=None):
    env = {k: v for k, v in os.environ.items() if k.startswith("UAZAPI_")}
    for p in [path_hint, os.path.join(os.getcwd(), ".env"), os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")]:
        if p and os.path.isfile(p):
            for line in open(p, encoding="utf-8"):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            break
    base, tok = env.get("UAZAPI_BASE_URL", "").rstrip("/"), env.get("UAZAPI_INSTANCE_TOKEN", "")
    if not base or not tok:
        sys.exit(json.dumps({"erro": "UAZAPI_BASE_URL/UAZAPI_INSTANCE_TOKEN ausentes"}))
    return base, tok

def call(base, tok, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json", "Accept": "application/json", "token": tok})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"erro": f"HTTP {e.code}", "detalhe": e.read().decode(errors="ignore")[:500]}
    except Exception as e:
        return {"erro": str(e)}

def jid(n):
    return n if "@" in n else "".join(c for c in n if c.isdigit()) + "@s.whatsapp.net"

def simplify(m):
    ts = m.get("messageTimestamp") or 0
    ts = ts / 1000 if ts > 1e12 else ts
    c = m.get("content")
    texto = m.get("text") or (c.get("text") if isinstance(c, dict) else c if isinstance(c, str) else None)
    opcoes = None
    if isinstance(c, dict):
        if c.get("buttons"):
            texto = texto or c.get("contentText")
            opcoes = [b.get("buttonText", {}).get("displayText") for b in c["buttons"]]
        elif c.get("sections"):
            texto = texto or c.get("description")
            opcoes = [{"titulo": r.get("title"), "rowID": r.get("rowID"), "desc": r.get("description")}
                      for s in c["sections"] for r in s.get("rows", [])]
    return {"quando": time.strftime("%d/%m/%Y %H:%M", time.localtime(ts)) if ts else None, "ts": ts,
            "deMim": bool(m.get("fromMe")), "tipo": m.get("messageType"), "texto": texto, "opcoes": opcoes,
            "id": m.get("messageid") or m.get("id")}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--env")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("status")
    s = sp.add_parser("send"); s.add_argument("numero"); s.add_argument("texto", nargs="?"); s.add_argument("--b64")
    s.add_argument("--reply"); s.add_argument("--delay", type=int, default=0)
    r = sp.add_parser("read"); r.add_argument("numero"); r.add_argument("--hours", type=float, default=24)
    r.add_argument("--limit", type=int, default=50); r.add_argument("--all", action="store_true")
    c = sp.add_parser("chats"); c.add_argument("--limit", type=int, default=20)
    a = ap.parse_args(); base, tok = load_env(a.env)
    if a.cmd == "status":
        out = call(base, tok, "GET", "/instance/status")
        inst = out.get("instance", out) if isinstance(out, dict) else out
        out = {"status": inst.get("status") if isinstance(inst, dict) else None, "nome": inst.get("name") if isinstance(inst, dict) else None, "erro": out.get("erro") if isinstance(out, dict) else None}
    elif a.cmd == "send":
        txt = base64.b64decode(a.b64).decode() if a.b64 else a.texto
        body = {"number": jid(a.numero), "text": txt}
        if a.reply: body["replyid"] = a.reply
        if a.delay: body["delay"] = a.delay
        res = call(base, tok, "POST", "/send/text", body)
        out = {"ok": "erro" not in res, "id": res.get("messageid") or res.get("id"), "status": res.get("status"), "erro": res.get("erro"), "detalhe": res.get("detalhe")}
    elif a.cmd == "read":
        res = call(base, tok, "POST", "/message/find", {"chatid": jid(a.numero), "limit": a.limit})
        msgs = res.get("messages", res if isinstance(res, list) else [])
        lim = time.time() - a.hours * 3600
        out = [simplify(m) for m in msgs]
        out = [m for m in out if (a.all or not m["deMim"]) and (not m["ts"] or m["ts"] >= lim)]
        if isinstance(res, dict) and res.get("erro"): out = res
    elif a.cmd == "chats":
        res = call(base, tok, "POST", "/chat/find", {"sort": "-wa_lastMsgTimestamp", "limit": a.limit})
        out = [{"chatid": x.get("wa_chatid"), "nome": x.get("wa_name") or x.get("wa_contactName") or x.get("name"),
                "naoLidas": x.get("wa_unreadCount")} for x in res.get("chats", [])] if isinstance(res, dict) and "chats" in res else res
    print(json.dumps(out, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
