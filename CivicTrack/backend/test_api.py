import pytest
import base64
from io import BytesIO
from datetime import timedelta
from PIL import Image
from fastapi.testclient import TestClient
from backend import main as appmod


@pytest.fixture()
def client():
    with TestClient(appmod.app) as test_client:
        with appmod.SessionLocal() as db:
            appmod.seed_demo(db, clear=True)
        yield test_client


def login(client, email, password=appmod.DEMO_PASSWORD):
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_demo_login_and_role_protection(client):
    citizen = login(client, "citizen@civictrack.demo")
    assert client.get("/auth/me", headers=auth(citizen)).json()["user"]["role"] == "citizen"
    assert client.get("/analytics", headers=auth(citizen)).status_code == 403
    assert client.get("/dashboard/summary", headers=auth(citizen)).status_code == 200


def test_report_ai_duplicate_and_complete_verification_workflow(client):
    citizen = login(client, "citizen@civictrack.demo")
    admin = login(client, "admin@civictrack.demo")
    response = client.post("/complaints", headers=auth(citizen), json={
        "title": "Deep pothole by the school crossing",
        "description": "A deep pothole has opened next to the school crossing. Cars swerve around it and cyclists may fall.",
        "latitude": 28.6135, "longitude": 77.2090, "landmark": "Central School crossing",
        "affected_people": 25, "age_hours": 48,
    })
    assert response.status_code == 201, response.text
    report = response.json()
    assert report["category"] == "Road damage"
    assert 0 <= report["priority_score"] <= 100
    assert report["ai_confidence"] > 0
    assert report["history"][0]["status"] == "Pending"
    assert report["duplicates"], "nearby same-category sample should be suggested as a possible duplicate"

    departments = client.get("/departments", headers=auth(admin)).json()
    roads = next(d for d in departments if d["name"] == "Roads & Transport")
    officers = client.get(f"/officers?department_id={roads['id']}", headers=auth(admin)).json()
    officer = officers[0]
    assigned = client.post(f"/complaints/{report['id']}/assign", headers=auth(admin), json={
        "department_id": roads["id"], "officer_id": officer["id"], "explanation": "Route to the roads team",
    })
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["status"] == "Assigned"

    officer_token = login(client, officer["email"])
    started = client.patch(f"/complaints/{report['id']}/status", headers=auth(officer_token), json={
        "status": "In Progress", "explanation": "Inspection started",
    })
    assert started.status_code == 200, started.text
    finished = client.patch(f"/complaints/{report['id']}/status", headers=auth(officer_token), json={
        "status": "Awaiting Verification", "explanation": "Pothole filled and road surface checked",
        "evidence_note": "Repair completed; surface is level and safe for passing traffic.",
    })
    assert finished.status_code == 200, finished.text
    assert finished.json()["status"] == "Awaiting Verification"

    verified = client.post(f"/complaints/{report['id']}/verify", headers=auth(citizen), json={
        "confirmed": True, "rating": 5, "comment": "The road is safe again.",
    })
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "Resolved"
    assert verified.json()["feedback"][0]["resolved_confirmed"] is True


def test_admin_can_review_ai_recommendation(client):
    admin = login(client, "admin@civictrack.demo")
    report = client.get("/complaints?limit=20", headers=auth(admin)).json()[0]
    response = client.patch(f"/complaints/{report['id']}/ai-review", headers=auth(admin), json={
        "category": "Public infrastructure", "priority_score": 61, "explanation": "Human review found this is a broken footpath ramp.",
    })
    assert response.status_code == 200, response.text
    assert response.json()["category"] == "Public infrastructure"
    assert response.json()["priority_level"] == "High"
    assert response.json()["ai_review_status"] == "Adjusted"
    assert response.json()["ai_reviewed_by"] == "Mira Kapoor"


def test_admin_can_create_officer_accounts(client):
    admin = login(client, "admin@civictrack.demo")
    citizen = login(client, "citizen@civictrack.demo")
    department = client.get("/departments", headers=auth(admin)).json()[0]
    created = client.post("/officers", headers=auth(admin), json={
        "name": "New Officer", "email": "new.officer@civictrack.demo",
        "password": "new-officer-password", "department_id": department["id"],
    })
    assert created.status_code == 201, created.text
    assert created.json()["role"] == "officer"
    officer = login(client, "new.officer@civictrack.demo", "new-officer-password")
    assert client.get("/auth/me", headers=auth(officer)).json()["user"]["role"] == "officer"
    assert client.post("/officers", headers=auth(citizen), json={
        "name": "No Access", "email": "no.access@example.test", "password": "safe-password",
        "department_id": department["id"],
    }).status_code == 403


def test_exports_are_admin_only_and_demo_labelled(client):
    admin = login(client, "admin@civictrack.demo")
    citizen = login(client, "citizen@civictrack.demo")
    response = client.get("/reports.csv", headers=auth(admin))
    assert response.status_code == 200
    assert "demonstration report" in response.text.splitlines()[0].lower()
    data = client.get("/reports.json", headers=auth(admin))
    assert data.status_code == 200
    assert data.json() and "citizen_name" not in data.json()[0]
    assert client.get("/reports.csv", headers=auth(citizen)).status_code == 403
    assert client.get("/reports.json", headers=auth(citizen)).status_code == 403


def test_admin_configures_persistent_service_targets_and_escalation_levels(client):
    admin = login(client, "admin@civictrack.demo")
    citizen = login(client, "citizen@civictrack.demo")
    policies = client.get("/service-policies", headers=auth(admin))
    assert policies.status_code == 200
    assert client.get("/service-policies", headers=auth(citizen)).status_code == 403
    configured = client.put("/service-policies/Road%20damage", headers=auth(admin), json={
        "deadline_hours": 12, "escalation_grace_hours": 0,
    })
    assert configured.status_code == 200, configured.text

    report = client.post("/complaints", headers=auth(citizen), json={
        "title": "Pothole near the bus crossing",
        "description": "A deep pothole has opened beside the bus crossing and vehicles swerve around it.",
        "category": "Road damage", "latitude": 28.6135, "longitude": 77.2090,
    })
    assert report.status_code == 201, report.text
    created = appmod.datetime.fromisoformat(report.json()["created_at"].replace("Z", "+00:00"))
    deadline = appmod.datetime.fromisoformat(report.json()["deadline_at"].replace("Z", "+00:00"))
    assert round((deadline - created).total_seconds() / 3600) == 12

    with appmod.SessionLocal() as db:
        item = db.get(appmod.Complaint, report.json()["id"])
        item.deadline_at = appmod.utcnow() - timedelta(hours=1)
        db.commit()
        appmod.process_escalations(db)
        appmod.process_escalations(db)
        levels = db.scalars(appmod.select(appmod.Escalation.level).where(
            appmod.Escalation.complaint_id == item.id,
        ).order_by(appmod.Escalation.level)).all()
        assert levels == [1, 2]

    detail = client.get(f"/complaints/{report.json()['id']}", headers=auth(citizen))
    assert [event["level"] for event in detail.json()["escalations"]] == [1, 2]


def test_citizen_reopened_report_can_return_to_officer_workflow(client):
    citizen = login(client, "citizen@civictrack.demo")
    awaiting = next(c for c in client.get("/complaints", headers=auth(citizen)).json() if c["status"] == "Awaiting Verification")
    reopened = client.post(f"/complaints/{awaiting['id']}/verify", headers=auth(citizen), json={
        "confirmed": False, "rating": 2, "comment": "The drain is still blocked.",
    })
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "Reopened"

    with appmod.SessionLocal() as db:
        officer = db.get(appmod.User, awaiting["officer_id"])
        officer_email = officer.email
    officer_token = login(client, officer_email)
    resumed = client.patch(f"/complaints/{awaiting['id']}/status", headers=auth(officer_token), json={
        "status": "In Progress", "explanation": "Follow-up work resumed after resident feedback.",
    })
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == "In Progress"


def test_upload_rejects_invalid_image_data(client):
    citizen = login(client, "citizen@civictrack.demo")
    response = client.post("/complaints", headers=auth(citizen), json={
        "title": "Photo for broken road", "description": "There is a broken road near this local crossing.",
        "latitude": 28.61, "longitude": 77.21, "image_data": "data:image/png;base64,YWJj",
    })
    assert response.status_code == 400


def test_private_images_are_scoped_to_the_report(client):
    citizen = login(client, "citizen@civictrack.demo")
    admin = login(client, "admin@civictrack.demo")
    image = BytesIO()
    Image.new("RGB", (8, 8), (120, 120, 120)).save(image, format="PNG")
    encoded = base64.b64encode(image.getvalue()).decode()
    response = client.post("/complaints", headers=auth(citizen), json={
        "title": "Photo of a broken footpath",
        "description": "A broken footpath is difficult for people to cross near the library.",
        "latitude": 28.62, "longitude": 77.21, "image_data": f"data:image/png;base64,{encoded}",
    })
    assert response.status_code == 201, response.text
    path = response.json()["image_url"]
    assert path
    assert client.get(path, headers=auth(citizen)).status_code == 200
    other = client.post("/auth/register", json={"name": "Other Resident", "email": "other@example.test", "password": "safe-password-123"}).json()
    assert client.get(path, headers=auth(other["access_token"])).status_code == 403
    assert client.get(path, headers=auth(admin)).status_code == 200
    public = client.get(f"/map/issues/{response.json()['id']}", headers=auth(other["access_token"]))
    assert public.status_code == 200
    assert "citizen_name" not in public.json()
    assert "email" not in public.json()


def test_admin_can_restore_demo_dataset(client):
    admin = login(client, "admin@civictrack.demo")
    response = client.post("/admin/reset", headers=auth(admin))
    assert response.status_code == 200, response.text
    fresh_token = response.json()["access_token"]
    assert client.get("/auth/me", headers=auth(fresh_token)).json()["user"]["role"] == "admin"
    assert len(client.get("/complaints", headers=auth(fresh_token)).json()) == 12
