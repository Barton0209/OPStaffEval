import json
import urllib.request

from app.db import SessionLocal
from app.models import User


def post(url, data, token=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def get(url, token):
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as r:
        return json.load(r)


db = SessionLocal()
u = db.query(User).filter(User.tab_no.like("%0140784")).first()
tab = u.tab_no
db.close()

login = post(
    "http://127.0.0.1:8000/api/field/auth/login",
    {"tab_no": tab, "password": "K0140784"},
)
token = login["access_token"]
print("login", login["fio"], login["role"])
asg = get("http://127.0.0.1:8000/api/field/assignments", token)
print("assignments", len(asg))
first = asg[0]
print("first", first["tab_no"], first["fio"], first["assignment_id"])
ev = post(
    f"http://127.0.0.1:8000/api/field/assignments/{first['assignment_id']}/evaluation?submit=true",
    {
        "score_quality": 4,
        "score_discipline": 4,
        "score_safety": 5,
        "score_skills": 4,
        "score_versatility": 3,
        "comment": "smoke test",
        "assignment_version": first["assignment_version"],
        "client_mutation_id": "smoke-1",
    },
    token,
)
print("eval", ev["status"], ev["avg_score"])
