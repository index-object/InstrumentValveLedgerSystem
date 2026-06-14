import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from app import create_app, db
from app.models import User, SheetMapping


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def init_db(app):
    with app.app_context():
        admin = User(username="admin", role="admin", real_name="管理员")
        admin.set_password("admin123")
        db.session.add(admin)
        user = User(username="user1", role="employee", real_name="张三")
        user.set_password("user123")
        db.session.add(user)
        db.session.commit()
        yield db


class TestSheetMapping:
    """SheetMapping 模型 CRUD 测试"""

    def test_create_mapping(self, app, init_db):
        with app.app_context():
            user = User.query.filter_by(username="user1").first()
            m = SheetMapping(
                sheet_name="测试流量",
                type_code="flow_meter",
                created_by=user.id,
            )
            db.session.add(m)
            db.session.commit()

            saved = SheetMapping.query.filter_by(sheet_name="测试流量").first()
            assert saved is not None
            assert saved.type_code == "flow_meter"
            assert saved.created_by == user.id

    def test_unique_sheet_name(self, app, init_db):
        with app.app_context():
            user = User.query.filter_by(username="user1").first()
            m1 = SheetMapping(
                sheet_name="同一Sheet", type_code="flow_meter", created_by=user.id,
            )
            db.session.add(m1)
            db.session.commit()

            m2 = SheetMapping(
                sheet_name="同一Sheet", type_code="valve", created_by=user.id,
            )
            with pytest.raises(Exception):
                db.session.add(m2)
                db.session.commit()

    def test_update_existing_mapping(self, app, init_db):
        with app.app_context():
            user = User.query.filter_by(username="user1").first()
            m = SheetMapping(
                sheet_name="测试", type_code="flow_meter", created_by=user.id,
            )
            db.session.add(m)
            db.session.commit()

            m.type_code = "valve"
            db.session.commit()

            updated = SheetMapping.query.filter_by(sheet_name="测试").first()
            assert updated.type_code == "valve"

    def test_delete_mapping(self, app, init_db):
        with app.app_context():
            user = User.query.filter_by(username="user1").first()
            m = SheetMapping(
                sheet_name="待删除", type_code="temperature", created_by=user.id,
            )
            db.session.add(m)
            db.session.commit()

            db.session.delete(m)
            db.session.commit()

            assert SheetMapping.query.filter_by(sheet_name="待删除").count() == 0

    def test_batch_query(self, app, init_db):
        with app.app_context():
            user = User.query.filter_by(username="user1").first()
            names = ["A", "B", "C", "D"]
            for name in names[:3]:
                db.session.add(SheetMapping(
                    sheet_name=name, type_code="valve", created_by=user.id,
                ))
            db.session.commit()

            result = SheetMapping.query.filter(
                SheetMapping.sheet_name.in_(["A", "B", "X", "Y"])
            ).all()
            assert len(result) == 2

    def test_updated_at_changes_on_update(self, app, init_db):
        from datetime import timedelta
        with app.app_context():
            import time
            user = User.query.filter_by(username="user1").first()
            m = SheetMapping(
                sheet_name="测试时间", type_code="flow_meter", created_by=user.id,
            )
            db.session.add(m)
            db.session.commit()

            original = m.updated_at
            time.sleep(0.01)
            m.type_code = "valve"
            db.session.commit()

            # Refresh to get DB value
            db.session.refresh(m)
            assert m.updated_at > original


class TestAdminSheetMappingRoutes:
    """管理员 SheetMapping 路由测试"""

    def test_route_requires_login(self, app, client):
        response = client.get("/admin/sheet-mappings")
        assert response.status_code in (302, 401)

    def test_route_requires_admin_role(self, app, client, init_db):
        client.post("/login", data={
            "username": "user1", "password": "user123",
        }, follow_redirects=True)
        response = client.get("/admin/sheet-mappings")
        assert response.status_code == 302

    def test_admin_sheet_mappings_page(self, app, client, init_db):
        with app.app_context():
            admin = User.query.filter_by(username="admin").first()
            db.session.add(SheetMapping(
                sheet_name="流量计", type_code="flow_meter",
                created_by=admin.id,
            ))
            db.session.commit()

        client.post("/login", data={
            "username": "admin", "password": "admin123",
        }, follow_redirects=True)
        response = client.get("/admin/sheet-mappings")
        assert response.status_code == 200
        assert "流量计" in response.get_data(as_text=True)
        assert "flow_meter" in response.get_data(as_text=True)

    def test_delete_sheet_mapping(self, app, client, init_db):
        with app.app_context():
            admin = User.query.filter_by(username="admin").first()
            m = SheetMapping(
                sheet_name="待删除映射", type_code="temperature",
                created_by=admin.id,
            )
            db.session.add(m)
            db.session.commit()
            mapping_id = m.id

        client.post("/login", data={
            "username": "admin", "password": "admin123",
        }, follow_redirects=True)
        client.post(f"/admin/sheet-mappings/{mapping_id}/delete")

        with app.app_context():
            assert SheetMapping.query.get(mapping_id) is None

    def test_empty_page_shows_empty_state(self, app, client, init_db):
        client.post("/login", data={
            "username": "admin", "password": "admin123",
        }, follow_redirects=True)
        response = client.get("/admin/sheet-mappings")
        assert response.status_code == 200
        assert "暂无映射记录" in response.get_data(as_text=True)

    def test_delete_with_nonexistent_id_returns_404(self, app, client, init_db):
        client.post("/login", data={
            "username": "admin", "password": "admin123",
        }, follow_redirects=True)
        response = client.post("/admin/sheet-mappings/99999/delete")
        assert response.status_code == 404
