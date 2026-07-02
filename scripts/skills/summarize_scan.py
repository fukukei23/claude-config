import json, glob, os

rows = []
for f in sorted(glob.glob(os.path.expanduser("~/.skillspector-reports/*.json"))):
    name = os.path.basename(f)[:-5]
    try:
        d = json.load(open(f))
        ra = d.get("risk_assessment", {})
        score = ra.get("score", -1)
        sev = ra.get("severity", "?")
        rec = ra.get("recommendation", "?")
        n_issues = len(d.get("issues", []))
        rows.append((name, score, sev, rec, n_issues))
    except Exception as e:
        rows.append((name, -1, "ERR", str(e)[:40], 0))

rows.sort(key=lambda x: -(x[1] if isinstance(x[1], (int, float)) else 0))
for name, score, sev, rec, n_issues in rows:
    print(f"{name:30s} score={score:>4} sev={sev:10s} rec={rec:18s} issues={n_issues}")
