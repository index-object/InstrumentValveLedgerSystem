import requests
import json

BASE_URL = "http://127.0.0.1:5000"

session = requests.Session()

login_url = f"{BASE_URL}/login"
login_data = {"username": "admin", "password": "admin123"}

response = session.post(login_url, data=login_data, allow_redirects=False)
print(f"Login status: {response.status_code}")
print(f"Cookies: {session.cookies.get_dict()}")

if response.status_code == 200 or response.status_code == 302:
    create_url = f"{BASE_URL}/valve/new"

    attachments_data = [
        {
            "attachment_type": "技术文档",
            "name": "测试附件1",
            "device_grade": "A级",
            "model": "Model-X",
            "manufacturer": "厂家A",
        },
        {
            "attachment_type": "检验报告",
            "name": "测试附件2",
            "device_grade": "B级",
            "model": "Model-Y",
            "manufacturer": "厂家B",
        },
    ]

    form_data = {
        "位号": "TEST-ATTACH-001",
        "名称": "测试阀门-附件",
        "装置名称": "测试装置",
        "设备等级": "A",
        "型号规格": "DN100",
        "生产厂家": "测试厂家",
        "attachments": json.dumps(attachments_data),
    }

    response = session.post(create_url, data=form_data, allow_redirects=False)
    print(f"\nCreate valve status: {response.status_code}")
    print(f"Response headers: {dict(response.headers)}")
    if response.status_code == 200:
        print(f"Response content: {response.text[:500]}")
    elif response.status_code == 302:
        print(f"Redirect to: {response.headers.get('Location')}")

    from app import create_app, db
    from app.models import Valve, ValveAttachment

    app = create_app()
    with app.app_context():
        valve = Valve.query.filter_by(位号="TEST-ATTACH-001").first()
        if valve:
            print(f"\nValve created: id={valve.id}, 位号={valve.位号}")
            attachments = ValveAttachment.query.filter_by(valve_id=valve.id).all()
            print(f"Attachments count: {len(attachments)}")
            for att in attachments:
                print(
                    f"  - id={att.id}, type={att.type}, 名称={att.名称}, 设备等级={att.设备等级}"
                )
        else:
            print("\nValve not found!")
else:
    print("Login failed!")
