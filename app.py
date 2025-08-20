import os
from datetime import datetime
from flask import Flask, jsonify, request, Response

app = Flask(__name__)

# Bump this string anytime you want to prove a new deploy is live
VERSION = "inline-admin v3 — 2025-08-20 17:35Z"

STATE = {
    "master": {"label": "Master", "domain": "", "gsid": ""},
    "followers": {},  # name -> {domain, gsid, riskx, active}
    "logs": []
}

def log(account, typ, stake, status, message):
    STATE["logs"].append({
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "account": account,
        "type": typ,
        "stake": stake,
        "status": status,
        "message": message,
    })
    if len(STATE["logs"]) > 2000:
        STATE["logs"] = STATE["logs"][-1000:]

def ok(**extra): 
    return jsonify({"ok": True, **extra})

def err(msg, code=400):
    return jsonify({"ok": False, "error": msg}), code

def parse_bool(v): return str(v).lower() in ("1", "true", "yes", "on")

ADMIN_HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Prime Mirror Admin</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root { color-scheme: dark; }
    body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 24px; background:#0b0f14; color:#e6eef7; }
    h1 { margin: 0 0 16px; font-size: 20px; }
    .card { border: 1px solid #1f2a36; border-radius: 10px; padding: 16px; margin: 14px 0; background:#111722; }
    label { font-size: 12px; color:#9fb1c7; display:block; margin-bottom:6px }
    input, select { width:100%; border:1px solid #273446; background:#0f1520; color:#e6eef7; padding:10px 12px; border-radius:8px; }
    .row { display:grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap:12px; }
    .row4{ display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap:12px; }
    .actions { display:flex; gap:10px; margin-top:12px }
    button { background:#155ee0; border:0; color:white; padding:10px 14px; border-radius:8px; cursor:pointer; }
    button.alt { background:#263345 }
    table { width:100%; border-collapse: collapse; margin-top:8px }
    th, td { text-align:left; padding:8px 6px; border-bottom:1px solid #1f2a36 }
    .ok { color:#6ee7b7 }
    .bad{ color:#fca5a5 }
    small.mono{font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color:#9fb1c7}
  </style>
</head>
<body>
  <h1>Prime Mirror Admin</h1>
  <small class="mono">Build: {{VERSION}}</small>

  <div class="card">
    <h3>Master account settings (server-side)</h3>
    <div class="row">
      <div><label>Label</label><input id="master_label" placeholder="Master" value="Master"/></div>
      <div><label>Domain (e.g. crazywager247.com)</label><input id="master_domain" placeholder="domain"/></div>
      <div><label>GSID cookie</label><input id="master_gsid" placeholder="paste GSID"/></div>
    </div>
    <div class="actions">
      <button id="btn_save_master">Save Master</button>
      <button class="alt" id="btn_open_master">Open Master (new tab)</button>
    </div>
    <small class="mono">Uses <code>GET /rpc?op=master.save&label=&domain=&gsid=</code></small>
  </div>

  <div class="card">
    <h3>Add / Update Follower</h3>
    <div class="row4">
      <div><label>Name (required)</label><input id="f_name" placeholder="e.g. Crazywager"/></div>
      <div><label>Domain (e.g. crazywager247.com)</label><input id="f_domain" placeholder="domain"/></div>
      <div><label>GSID cookie</label><input id="f_gsid" placeholder="paste GSID"/></div>
      <div><label>Risk ×</label><input id="f_riskx" type="number" step="0.1" value="1.0"/></div>
    </div>
    <div class="actions">
      <label style="display:flex;align-items:center;gap:8px"><input id="f_active" type="checkbox" checked/> Active</label>
      <button id="btn_upsert_f">Add / Update</button>
    </div>

    <table id="followers_tbl">
      <thead><tr><th>Name</th><th>Domain</th><th>Risk×</th><th>Active</th><th>Actions</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <div class="card">
    <h3>Logs</h3>
    <table id="logs_tbl">
      <thead><tr><th>When (UTC)</th><th>Account</th><th>Type</th><th>Stake</th><th>Status</th><th>Message</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

<script>
const q = s => document.querySelector(s);

async function apiState(){ const r = await fetch("/api/state"); return r.json(); }
async function rpc(params){
  const url = "/rpc?" + new URLSearchParams(params).toString();
  const r = await fetch(url); return r.json();
}
function row(html){ const tr=document.createElement('tr'); tr.innerHTML=html; return tr; }

async function refresh(){
  const data = await apiState();
  q('#master_label').value  = data.master.label || 'Master';
  q('#master_domain').value = data.master.domain || '';
  q('#master_gsid').value   = data.master.gsid || '';

  const tb = q('#followers_tbl tbody'); tb.innerHTML = "";
  Object.entries(data.followers||{}).forEach(([name,f])=>{
    tb.appendChild(row(
      `<td>${name}</td><td>${f.domain||''}</td><td>${f.riskx||1}</td><td>${f.active?'<span class="ok">yes</span>':'<span class="bad">no</span>'}</td><td><button data-del="${name}">Delete</button></td>`
    ));
  });

  const lb = q('#logs_tbl tbody'); lb.innerHTML="";
  (data.logs||[]).slice(-150).reverse().forEach(l=>{
    lb.appendChild(row(`<td>${l.ts}</td><td>${l.account}</td><td>${l.type}</td><td>${l.stake}</td><td>${l.status}</td><td>${l.message}</td>`));
  });
}

q('#btn_save_master').onclick = async () => {
  const label = q('#master_label').value.trim()||'Master';
  const domain = q('#master_domain').value.trim();
  const gsid = q('#master_gsid').value.trim();
  if(!domain||!gsid){ alert('Enter domain and GSID'); return; }
  const j = await rpc({op:'master.save', label, domain, gsid});
  if(!j.ok){ alert('Save failed: '+(j.error||'error')); return; }
  await refresh();
};
q('#btn_open_master').onclick = () => {
  const d = q('#master_domain').value.trim();
  if(!d) return alert('Enter master domain first.');
  const url = d.startsWith('http') ? d : ('https://'+d);
  window.open(url,'_blank','noopener');
};
q('#btn_upsert_f').onclick = async () => {
  const name = q('#f_name').value.trim();
  const domain = q('#f_domain').value.trim();
  const gsid = q('#f_gsid').value.trim();
  const riskx = q('#f_riskx').value || '1';
  const active = q('#f_active').checked ? '1':'0';
  if(!name){ alert('Enter follower name'); return; }
  if(!domain||!gsid){ alert('Enter follower domain & GSID'); return; }
  const j = await rpc({op:'follower.upsert', name, domain, gsid, riskx, active});
  if(!j.ok){ alert('Follower save failed: '+(j.error||'error')); return; }
  q('#f_name').value='';
  await refresh();
};
q('#followers_tbl').onclick = async (e)=>{
  const name = e.target?.dataset?.del; if(!name) return;
  if(!confirm(`Delete follower "${name}"?`)) return;
  const j = await rpc({op:'follower.delete', name});
  if(!j.ok){ alert('Delete failed: '+(j.error||'error')); return; }
  await refresh();
};

refresh(); setInterval(refresh, 5000);
</script>
</body></html>
""".replace("{{VERSION}}", VERSION)

def admin_response(): return Response(ADMIN_HTML, mimetype="text/html")

@app.get("/")
@app.get("/pmf/")
def admin(): return admin_response()

@app.get("/favicon.ico")
@app.get("/pmf/favicon.ico")
def favicon(): return Response(status=204)

@app.get("/__version")
def version(): return Response(VERSION, mimetype="text/plain")

@app.get("/api/state")
@app.get("/pmf/api/state")
def api_state():
    return jsonify({"master": STATE["master"], "followers": STATE["followers"], "logs": STATE["logs"]})

@app.get("/api/events")
@app.get("/pmf/api/events")
def api_events():
    return jsonify([])

def rpc_logic(args):
    op = (args.get("op") or "").strip()

    if op == "master.save":
        domain = (args.get("domain") or "").strip()
        gsid   = (args.get("gsid") or "").strip()
        label  = (args.get("label") or "Master").strip() or "Master"
        if not domain: return err("Missing domain")
        if not gsid:   return err("Missing gsid")
        STATE["master"] = {"label": label, "domain": domain, "gsid": gsid}
        log("master","config",0,"ok",f"Master saved: {label} @ {domain}")
        return ok(saved="master")

    if op == "follower.upsert":
        name   = (args.get("name") or "").strip()
        domain = (args.get("domain") or "").strip()
        gsid   = (args.get("gsid") or "").strip()
        riskx  = float(args.get("riskx") or 1.0)
        active = (args.get("active") or "1") in ("1","true","True","yes","on")
        if not name:   return err("Missing follower name")
        if not domain: return err("Missing follower domain")
        if not gsid:   return err("Missing follower gsid")
        STATE["followers"][name] = {"domain": domain, "gsid": gsid, "riskx": riskx, "active": active}
        log(name,"config",0,"ok",f"Follower saved: riskx={riskx}, active={active}")
        return ok(saved="follower", name=name)

    if op == "follower.delete":
        name = (args.get("name") or "").strip()
        if not name: return err("Missing follower name")
        existed = STATE["followers"].pop(name, None)
        if existed:
            log(name,"config",0,"ok","Follower deleted")
            return ok(deleted=name)
        return err("Follower not found", 404)

    return err("Unknown op", 400)

@app.route("/rpc", methods=["GET", "POST"])
@app.route("/pmf/rpc", methods=["GET", "POST"])
def rpc():
    args = request.args if request.method == "GET" else request.form
    return rpc_logic(args)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5055)))
