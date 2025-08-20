import os, time, json
from flask import Flask, request, jsonify, redirect, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

STATE = {
    "master": {"label":"Master","domain":"","gsid":""},
    "followers": [],      # [{name,domain,gsid,risk,active}]
    "live_url": "",       # latest signed becoms/live URL
    "live_updated": 0     # epoch seconds
}

def ok(**kw): 
    d={"ok": True}; d.update(kw); return jsonify(d)

def err(msg, code=400):
    return jsonify({"ok": False, "error": msg}), code

@app.get("/")
def root():
    # Minimal admin (you already have one; this is a fallback)
    return Response("OK", 200)

@app.get("/api/state")
def api_state():
    return jsonify({
        "master": STATE["master"],
        "followers": STATE["followers"],
        "live_url": STATE["live_url"],
        "live_updated": STATE["live_updated"],
        "ts": time.time()
    })

@app.route("/rpc", methods=["GET","POST"])
def rpc():
    op = request.args.get("op") or (request.json or {}).get("op")
    if not op: return err("Missing op")

    if op == "master.save":
        data = request.args or request.json or {}
        STATE["master"]["label"]  = data.get("label","Master")
        STATE["master"]["domain"] = data.get("domain","")
        STATE["master"]["gsid"]   = data.get("gsid","")
        return ok(master=STATE["master"])

    if op == "follower.upsert":
        data = request.args or request.json or {}
        name = data.get("name","").strip()
        if not name: return err("Missing follower name")
        domain = data.get("domain","").strip()
        gsid   = data.get("gsid","").strip()
        risk   = float(data.get("risk", 1.0))
        active = str(data.get("active","true")).lower() in ("1","true","yes","y","on")

        row = next((f for f in STATE["followers"] if f["name"].lower()==name.lower()), None)
        if not row:
            row = {"name":name,"domain":domain,"gsid":gsid,"risk":risk,"active":active}
            STATE["followers"].append(row)
        else:
            row.update({"domain":domain,"gsid":gsid,"risk":risk,"active":active})
        return ok(followers=STATE["followers"])

    if op == "follower.delete":
        data = request.args or request.json or {}
        name = data.get("name","").strip().lower()
        STATE["followers"] = [f for f in STATE["followers"] if f["name"].lower()!=name]
        return ok(followers=STATE["followers"])

    if op == "live.set":
        data = request.args or request.json or {}
        url = data.get("url","").strip()
        if not url: return err("Missing url")
        STATE["live_url"] = url
        STATE["live_updated"] = int(time.time())
        return ok(live_url=STATE["live_url"], live_updated=STATE["live_updated"])

    if op == "live.get":
        return ok(live_url=STATE["live_url"], live_updated=STATE["live_updated"])

    return err("Unknown op")

@app.get("/live")
def live_redirect():
    url = STATE.get("live_url","")
    if not url:
        return Response("Live not ready (no URL yet). Open the master and wait for PMF ON.", 503)
    # Optional: stale guard (tokens usually last ~20–30 min); 1800 = 30 min
    if time.time() - STATE.get("live_updated",0) > 1800:
        return Response("Live link is stale. Open the master to refresh.", 503)
    return redirect(url, code=302)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
