# coding=utf-8
# encoding: utf-8
from __future__ import unicode_literals


def _login(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


def test_plan_list_requires_login(client, init_database):
    resp = client.get("/plans")
    assert resp.status_code == 302


def test_leader_creates_plan(client, init_database):
    _login(client, "admin", "admin123")
    resp = client.post("/plan/new", data={"title": "2026 Plan", "description": "Annual"}, follow_redirects=True)
    assert resp.status_code == 200


def test_leader_publishes_plan(client, init_database):
    _login(client, "admin", "admin123")
    client.post("/plan/new", data={"title": "Test Plan", "description": "desc"}, follow_redirects=True)
    resp = client.post("/plan/1/publish", follow_redirects=True)
    assert resp.status_code == 200


def test_employee_sees_published_plan(client, init_database):
    _login(client, "admin", "admin123")
    client.post("/plan/new", data={"title": "Employee View Plan", "description": "desc"}, follow_redirects=True)
    client.post("/plan/1/publish", follow_redirects=True)
    _login(client, "user1", "user123")
    resp = client.get("/plans")
    assert resp.status_code == 200
    assert "Employee View Plan" in resp.data.decode("utf-8")


def test_plan_detail_renders(client, init_database):
    _login(client, "admin", "admin123")
    client.post("/plan/new", data={"title": "Detail Test", "description": "desc"}, follow_redirects=True)
    resp = client.get("/plan/1")
    assert resp.status_code == 200
    assert "Detail Test" in resp.data.decode("utf-8")


def test_leader_archives_plan(client, init_database):
    _login(client, "admin", "admin123")
    client.post("/plan/new", data={"title": "Archive Test", "description": "desc"}, follow_redirects=True)
    client.post("/plan/1/publish", follow_redirects=True)
    resp = client.post("/plan/1/archive", follow_redirects=True)
    assert resp.status_code == 200


def test_employee_cannot_create_plan(client, init_database):
    _login(client, "user1", "user123")
    resp = client.post("/plan/new", data={"title": "Should Not Work"}, follow_redirects=True)
    assert resp.status_code == 200
    text = resp.data.decode("utf-8")
    assert "无权" in text or resp.request.path != "/plans"
