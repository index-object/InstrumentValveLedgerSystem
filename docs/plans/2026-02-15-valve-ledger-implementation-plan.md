# 仪表阀门台账管理系统 - 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个完整的仪表阀门台账管理系统，支持增删改查、审批工作流、数据导入导出、照片管理、维护记录等功能。

**Architecture:** Flask + SQLite + Bootstrap 5，采用分层架构（路由层 → 业务逻辑层 → 数据访问层）

**Tech Stack:** Flask 3.x, Flask-SQLAlchemy, Flask-Login, Bootstrap 5, pandas, openpyxl

---

## ⚠️ 前端 UI 设计规则

> **IMPORTANT:** 当实施任何前端 UI 设计工作时（包括创建、修改 HTML 模板、样式、页面布局等），**必须**使用 `ui-ux-pro-max` 技能。
> 
> 使用方式: `task(load_skills=["ui-ux-pro-max"], category="visual-engineering", ...)`

---

## Task 1: 项目初始化与依赖配置

**Files:**
- Create: `requirements.txt`
- Modify: `pyproject.toml`, `README.md`, `.gitignore`

**Step 1: 创建 requirements.txt**

```txt
Flask>=3.0.0
Flask-SQLAlchemy>=3.1.0
Flask-Login>=0.6.3
SQLAlchemy>=2.0.0
pandas>=2.0.0
openpyxl>=3.1.0
Werkzeug>=3.0.0
python-dotenv>=1.0.0
```

**Step 2: 安装依赖**

Run: `pip install -r requirements.txt`

**Step 3: 提交**

```bash
git add requirements.txt .gitignore README.md pyproject.toml
git commit -m "chore: add project dependencies"
```

---

## Task 2: 数据库模型定义

**Files:**
- Create: `app/models.py`

**Step 1: 创建 app 目录和 models.py**

```python
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='employee')  # employee/leader
    real_name = db.Column(db.String(50))
    dept = db.Column(db.String(50))
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Valve(db.Model):
    __tablename__ = 'valves'
    id = db.Column(db.Integer, primary_key=True)
    # 基本信息
    序号 = db.Column(db.String(20))
    装置名称 = db.Column(db.String(100))
    位号 = db.Column(db.String(50), unique=True)
    名称 = db.Column(db.String(100))
    设备等级 = db.Column(db.String(20))
    型号规格 = db.Column(db.String(100))
    生产厂家 = db.Column(db.String(100))
    安装位置及用途 = db.Column(db.String(200))
    # 工艺条件
    工艺条件_介质名称 = db.Column(db.String(50))
    工艺条件_设计温度 = db.Column(db.String(50))
    工艺条件_阀前压力 = db.Column(db.String(50))
    工艺条件_阀后压力 = db.Column(db.String(50))
    # 阀体
    阀体_公称通径 = db.Column(db.String(50))
    阀体_连接方式及规格 = db.Column(db.String(100))
    阀体_材质 = db.Column(db.String(50))
    # 阀内件
    阀内件_阀座直径 = db.Column(db.String(50))
    阀内件_阀芯材质 = db.Column(db.String(50))
    阀内件_阀座材质 = db.Column(db.String(50))
    阀内件_阀杆材质 = db.Column(db.String(50))
    阀内件_流量特性 = db.Column(db.String(50))
    阀内件_泄露等级 = db.Column(db.String(50))
    阀内件_Cv值 = db.Column(db.String(50))
    # 执行机构
    执行机构_形式 = db.Column(db.String(50))
    执行机构_型号规格 = db.Column(db.String(100))
    执行机构_厂家 = db.Column(db.String(100))
    执行机构_作用形式 = db.Column(db.String(50))
    执行机构_行程 = db.Column(db.String(50))
    执行机构_弹簧范围 = db.Column(db.String(50))
    执行机构_气源压力 = db.Column(db.String(50))
    执行机构_故障位置 = db.Column(db.String(50))
    执行机构_关阀时间 = db.Column(db.String(50))
    执行机构_开阀时间 = db.Column(db.String(50))
    # 其他
    设备编号 = db.Column(db.String(50))
    是否联锁 = db.Column(db.String(10))
    备注 = db.Column(db.Text)
    # 状态与审批
    status = db.Column(db.String(20), default='draft')  # draft/pending/approved/rejected
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    creator = db.relationship('User', foreign_keys=[created_by])
    approver = db.relationship('User', foreign_keys=[approved_by])

class ValvePhoto(db.Model):
    __tablename__ = 'valve_photos'
    id = db.Column(db.Integer, primary_key=True)
    valve_id = db.Column(db.Integer, db.ForeignKey('valves.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(200))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    valve = db.relationship('Valve', backref='photos')
    uploader = db.relationship('User')

class MaintenanceRecord(db.Model):
    __tablename__ = 'maintenance_records'
    id = db.Column(db.Integer, primary_key=True)
    valve_id = db.Column(db.Integer, db.ForeignKey('valves.id'), nullable=False)
    类型 = db.Column(db.String(50))  # 维修/检定/保养
    日期 = db.Column(db.Date)
    内容 = db.Column(db.Text)
    负责人 = db.Column(db.String(50))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    valve = db.relationship('Valve', backref='maintenance_records')
    creator = db.relationship('User')

class ApprovalLog(db.Model):
    __tablename__ = 'approval_logs'
    id = db.Column(db.Integer, primary_key=True)
    valve_id = db.Column(db.Integer, db.ForeignKey('valves.id'), nullable=False)
    action = db.Column(db.String(20))  # submit/approve/reject
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    comment = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    valve = db.relationship('Valve', backref='approval_logs')
    user = db.relationship('User')

class Setting(db.Model):
    __tablename__ = 'settings'
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(200))
```

**Step 2: 初始化数据库**

Run: `python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all(); print('Database initialized!')"`

**Step 3: 提交**

```bash
git add app/models.py
git commit -m "feat: add database models"
```

---

## Task 3: 应用工厂与配置

**Files:**
- Create: `app/__init__.py`
- Create: `config.py`

**Step 1: 创建 config.py**

```python
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///valves.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
```

**Step 2: 创建 app/__init__.py**

```python
from flask import Flask
from config import Config
from app.models import db, User
from flask_login import LoginManager
import os

login_manager = LoginManager()
login_manager.login_view = 'login'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    db.init_app(app)
    login_manager.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    from app import routes
    app.register_blueprint(routes.bp)
    
    return app
```

**Step 3: 提交**

```bash
git add app/__init__.py config.py
git commit -m "feat: add app factory and config"
```

---

## Task 4: 用户认证

**Files:**
- Create: `app/routes/auth.py`
- Modify: `app/routes/__init__.py`

**Step 1: 创建 app/routes/auth.py**

```python
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误')
    
    return render_template('login.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
```

**Step 2: 更新 app/routes/__init__.py**

```python
from flask import Blueprint

bp = Blueprint('main', __name__)

from app.routes import auth, valves, admin
```

**Step 3: 创建登录模板 templates/login.html**

```html
<!DOCTYPE html>
<html>
<head>
    <title>登录 - 仪表阀门台账系统</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container mt-5">
        <div class="row justify-content-center">
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">登录</div>
                    <div class="card-body">
                        {% with messages = get_flashed_messages() %}
                            {% if messages %}
                                {% for message in messages %}
                                    <div class="alert alert-danger">{{ message }}</div>
                                {% endfor %}
                            {% endif %}
                        {% endwith %}
                        <form method="POST">
                            <div class="mb-3">
                                <label>用户名</label>
                                <input type="text" name="username" class="form-control" required>
                            </div>
                            <div class="mb-3">
                                <label>密码</label>
                                <input type="password" name="password" class="form-control" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">登录</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
```

**Step 4: 更新主路由**

```python
# 在 app/routes/__init__.py 添加
@bp.route('/')
@login_required
def index():
    from app.models import Valve, Setting
    total = Valve.query.count()
    pending = Valve.query.filter_by(status='pending').count()
    return render_template('index.html', total=total, pending=pending)
```

**Step 5: 提交**

```bash
git add app/routes/auth.py app/routes/__init__.py config.py
git commit -m "feat: add authentication"
```

---

## Task 5: 台账管理 CRUD

**Files:**
- Create: `app/routes/valves.py`
- Create: `templates/valves/list.html`, `templates/valves/detail.html`, `templates/valves/form.html`

**Step 1: 创建 app/routes/valves.py**

```python
from flask import Blueprint, render_template, redirect, url_for, request, flash, send_from_directory
from flask_login import login_required, current_user
from app.models import db, Valve, Setting, ApprovalLog, User
from werkzeug.utils import secure_filename
import os

valves = Blueprint('valves', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@valves.route('/valves')
@login_required
def list():
    query = Valve.query
    search = request.args.get('search')
    if search:
        query = query.filter(
            (Valve.位号.contains(search)) | 
            (Valve.名称.contains(search)) |
            (Valve.装置名称.contains(search))
        )
    
    # 员工只能看已审批的，领导看全部
    if current_user.role == 'employee':
        query = query.filter_by(status='approved')
    
    valves_list = query.order_by(Valve.序号).all()
    return render_template('valves/list.html', valves=valves_list)

@valves.route('/valve/<int:id>')
@login_required
def detail(id):
    valve = Valve.query.get_or_404(id)
    # 员工只能看已审批的
    if current_user.role == 'employee' and valve.status != 'approved':
        flash('无权访问')
        return redirect(url_for('valves.list'))
    return render_template('valves/detail.html', valve=valve)

@valves.route('/valve/new', methods=['GET', 'POST'])
@login_required
def new():
    if request.method == 'POST':
        valve = Valve()
        for key in request.form:
            if hasattr(valve, key):
                setattr(valve, key, request.form.get(key))
        
        valve.created_by = current_user.id
        valve.status = 'draft'
        
        db.session.add(valve)
        db.session.commit()
        
        # 记录提交
        log = ApprovalLog(valve_id=valve.id, action='submit', user_id=current_user.id)
        db.session.add(log)
        
        # 审批逻辑
        auto_approve = Setting.query.get('auto_approval')
        if auto_approve and auto_approve.value == 'true':
            valve.status = 'approved'
            valve.approved_by = current_user.id
            log.action = 'approve'
        else:
            valve.status = 'pending'
        
        db.session.commit()
        flash('提交成功')
        return redirect(url_for('valves.list'))
    
    return render_template('valves/form.html', valve=None)

@valves.route('/valve/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    valve = Valve.query.get_or_404(id)
    
    if valve.status not in ['draft', 'rejected']:
        flash('当前状态无法编辑')
        return redirect(url_for('valves.detail', id=id))
    
    if request.method == 'POST':
        for key in request.form:
            if hasattr(valve, key):
                setattr(valve, key, request.form.get(key))
        
        valve.status = 'draft'
        db.session.commit()
        
        # 重新提交
        log = ApprovalLog(valve_id=valve.id, action='submit', user_id=current_user.id)
        db.session.add(log)
        
        auto_approve = Setting.query.get('auto_approval')
        if auto_approve and auto_approve.value == 'true':
            valve.status = 'approved'
            valve.approved_by = current_user.id
            log.action = 'approve'
        else:
            valve.status = 'pending'
        
        db.session.commit()
        flash('提交成功')
        return redirect(url_for('valves.list'))
    
    return render_template('valves/form.html', valve=valve)

@valves.route('/valve/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    valve = Valve.query.get_or_404(id)
    
    # 只能删除草稿或被驳回的
    if valve.status not in ['draft', 'rejected']:
        flash('当前状态无法删除')
        return redirect(url_for('valves.detail', id=id))
    
    db.session.delete(valve)
    db.session.commit()
    flash('删除成功')
    return redirect(url_for('valves.list'))
```

**Step 2: 提交**

```bash
git add app/routes/valves.py
git commit -m "feat: add valve CRUD operations"
```

---

## Task 6: 审批管理

**Files:**
- Modify: `app/routes/valves.py`

**Step 1: 添加审批路由**

```python
@valves.route('/approvals')
@login_required
def approvals():
    if current_user.role != 'leader':
        flash('需要领导权限')
        return redirect(url_for('valves.list'))
    
    pending = Valve.query.filter_by(status='pending').all()
    return render_template('valves/approvals.html', valves=pending)

@valves.route('/valve/approve/<int:id>', methods=['POST'])
@login_required
def approve(id):
    if current_user.role != 'leader':
        flash('需要领导权限')
        return redirect(url_for('valves.list'))
    
    valve = Valve.query.get_or_404(id)
    valve.status = 'approved'
    valve.approved_by = current_user.id
    
    log = ApprovalLog(valve_id=valve.id, action='approve', user_id=current_user.id, 
                      comment=request.form.get('comment', ''))
    db.session.add(log)
    db.session.commit()
    
    flash('审批通过')
    return redirect(url_for('valves.approvals'))

@valves.route('/valve/reject/<int:id>', methods=['POST'])
@login_required
def reject(id):
    if current_user.role != 'leader':
        flash('需要领导权限')
        return redirect(url_for('valves.list'))
    
    valve = Valve.query.get_or_404(id)
    valve.status = 'rejected'
    
    log = ApprovalLog(valve_id=valve.id, action='reject', user_id=current_user.id,
                      comment=request.form.get('comment', ''))
    db.session.add(log)
    db.session.commit()
    
    flash('已驳回')
    return redirect(url_for('valves.approvals'))

@valves.route('/my-applications')
@login_required
def my_applications():
    my_valves = Valve.query.filter_by(created_by=current_user.id).order_by(Valve.created_at.desc()).all()
    return render_template('valves/my_applications.html', valves=my_valves)
```

**Step 2: 提交**

```bash
git commit -m "feat: add approval workflow"
```

---

## Task 7: Excel 导入导出

**Files:**
- Modify: `app/routes/valves.py`

**Step 1: 添加导入导出路由**

```python
@valves.route('/import', methods=['GET', 'POST'])
@login_required
def import_data():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('请选择文件')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('请选择文件')
            return redirect(request.url)
        
        if file:
            import pandas as pd
            from io import BytesIO
            
            df = pd.read_excel(file)
            
            # 字段映射
            column_map = {
                '序号': '序号', '装置名称': '装置名称', '位号': '位号',
                '名称': '名称', '设备等级': '设备等级', '型号规格': '型号规格',
                '生产厂家': '生产厂家', '安装位置及用途': '安装位置及用途',
                '工艺条件_介质名称': '工艺条件_介质名称',
                '工艺条件_设计温度': '工艺条件_设计温度',
                '工艺条件_阀前压力': '工艺条件_阀前压力',
                '工艺条件_阀后压力': '工艺条件_阀后压力',
                '阀体_公称通径': '阀体_公称通径',
                '阀体_连接方式及规格': '阀体_连接方式及规格',
                '阀体_材质': '阀体_材质',
                '阀内件_阀座直径': '阀内件_阀座直径',
                '阀内件_阀芯材质': '阀内件_阀芯材质',
                '阀内件_阀座材质': '阀内件_阀座材质',
                '阀内件_阀杆材质': '阀内件_阀杆材质',
                '阀内件_流量特性': '阀内件_流量特性',
                '阀内件_泄露等级': '阀内件_泄露等级',
                '阀内件_Cv值': '阀内件_Cv值',
                '执行机构_形式': '执行机构_形式',
                '执行机构_型号规格': '执行机构_型号规格',
                '执行机构_厂家': '执行机构_厂家',
                '执行机构_作用形式': '执行机构_作用形式',
                '执行机构_行程': '执行机构_行程',
                '执行机构_弹簧范围': '执行机构_弹簧范围',
                '执行机构_气源压力': '执行机构_气源压力',
                '执行机构_故障位置': '执行机构_故障位置',
                '执行机构_关阀时间': '执行机构_关阀时间',
                '执行机构_开阀时间': '执行机构_开阀时间',
                '设备编号': '设备编号',
                '是否联锁': '是否联锁',
                '备注': '备注',
            }
            
            count = 0
            for _, row in df.iterrows():
                if pd.isna(row.get('位号')):
                    continue
                
                existing = Valve.query.filter_by(位号=row['位号']).first()
                if existing:
                    continue
                
                valve = Valve()
                for excel_col, db_col in column_map.items():
                    if excel_col in df.columns and pd.notna(row.get(excel_col)):
                        setattr(valve, db_col, str(row[excel_col]))
                
                valve.created_by = current_user.id
                
                # 自动审批
                auto_approve = Setting.query.get('auto_approval')
                if auto_approve and auto_approve.value == 'true':
                    valve.status = 'approved'
                    valve.approved_by = current_user.id
                else:
                    valve.status = 'approved'  # 默认自动通过
                
                db.session.add(valve)
                count += 1
            
            db.session.commit()
            flash(f'成功导入 {count} 条记录')
            return redirect(url_for('valves.list'))
    
    return render_template('valves/import.html')

@valves.route('/export')
@login_required
def export_data():
    import pandas as pd
    from flask import make_response
    
    valves = Valve.query.filter_by(status='approved').all()
    
    data = []
    for v in valves:
        data.append({
            '序号': v.序号, '装置名称': v.装置名称, '位号': v.位号,
            '名称': v.名称, '设备等级': v.设备等级, '型号规格': v.型号规格,
            '生产厂家': v.生产厂家, '安装位置及用途': v.安装位置及用途,
            '工艺条件_介质名称': v.工艺条件_介质名称,
            '工艺条件_设计温度': v.工艺条件_设计温度,
            '工艺条件_阀前压力': v.工艺条件_阀前压力,
            '工艺条件_阀后压力': v.工艺条件_阀后压力,
            '阀体_公称通径': v.阀体_公称通径,
            '阀体_连接方式及规格': v.阀体_连接方式及规格,
            '阀体_材质': v.阀体_材质,
            '阀内件_阀座直径': v.阀内件_阀座直径,
            '阀内件_阀芯材质': v.阀内件_阀芯材质,
            '阀内件_阀座材质': v.阀内件_阀座材质,
            '阀内件_阀杆材质': v.阀内件_阀杆材质,
            '阀内件_流量特性': v.阀内件_流量特性,
            '阀内件_泄露等级': v.阀内件_泄露等级,
            '阀内件_Cv值': v.阀内件_Cv值,
            '执行机构_形式': v.执行机构_形式,
            '执行机构_型号规格': v.执行机构_型号规格,
            '执行机构_厂家': v.执行机构_厂家,
            '执行机构_作用形式': v.执行机构_作用形式,
            '执行机构_行程': v.执行机构_行程,
            '执行机构_弹簧范围': v.执行机构_弹簧范围,
            '执行机构_气源压力': v.执行机构_气源压力,
            '执行机构_故障位置': v.执行机构_故障位置,
            '执行机构_关阀时间': v.执行机构_关阀时间,
            '执行机构_开阀时间': v.执行机构_开阀时间,
            '设备编号': v.设备编号,
            '是否联锁': v.是否联锁,
            '备注': v.备注,
        })
    
    df = pd.DataFrame(data)
    output = make_response(df.to_excel(index=False, engine='openpyxl'))
    output.headers["Content-Disposition"] = "attachment; filename=valves.xlsx"
    output.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    return output
```

**Step 2: 提交**

```bash
git commit -m "feat: add Excel import/export"
```

---

## Task 8: 照片管理与维护记录

**Files:**
- Modify: `app/routes/valves.py`
- Create: `templates/valves/photos.html`, `templates/valves/maintenance.html`

**Step 1: 添加照片和维护记录路由**

```python
@valves.route('/valve/<int:id>/photos', methods=['GET', 'POST'])
@login_required
def photos(id):
    valve = Valve.query.get_or_404(id)
    
    if request.method == 'POST':
        if 'photo' not in request.files:
            flash('请选择文件')
            return redirect(request.url)
        
        file = request.files['photo']
        if file and allowed_file(file.filename):
            from flask import current_app
            filename = secure_filename(f"{valve.位号}_{file.filename}")
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
            
            photo = ValvePhoto(
                valve_id=valve.id,
                filename=filename,
                description=request.form.get('description', ''),
                uploaded_by=current_user.id
            )
            db.session.add(photo)
            db.session.commit()
            flash('上传成功')
    
    return render_template('valves/photos.html', valve=valve)

@valves.route('/valve/<int:id>/maintenance', methods=['GET', 'POST'])
@login_required
def maintenance(id):
    valve = Valve.query.get_or_404(id)
    
    if request.method == 'POST':
        record = MaintenanceRecord(
            valve_id=valve.id,
            类型=request.form.get('类型'),
            日期=datetime.strptime(request.form.get('日期'), '%Y-%m-%d').date(),
            内容=request.form.get('内容'),
            负责人=request.form.get('负责人'),
            created_by=current_user.id
        )
        db.session.add(record)
        db.session.commit()
        flash('添加成功')
        return redirect(url_for('valves.maintenance', id=id))
    
    records = MaintenanceRecord.query.filter_by(valve_id=id).order_by(MaintenanceRecord.日期.desc()).all()
    return render_template('valves/maintenance.html', valve=valve, records=records)
```

**Step 2: 提交**

```bash
git commit -m "feat: add photo and maintenance management"
```

---

## Task 9: 后台管理

**Files:**
- Create: `app/routes/admin.py`
- Create: `templates/admin/users.html`, `templates/admin/settings.html`

**Step 1: 创建 app/routes/admin.py**

```python
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models import db, User, Setting

admin = Blueprint('admin', __name__, url_prefix='/admin')

@admin.route('/')
@login_required
def index():
    if current_user.role != 'leader':
        flash('需要领导权限')
        return redirect(url_for('valves.list'))
    return render_template('admin/index.html')

@admin.route('/users', methods=['GET', 'POST'])
@login_required
def users():
    if current_user.role != 'leader':
        flash('需要领导权限')
        return redirect(url_for('valves.list'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        real_name = request.form.get('real_name')
        dept = request.form.get('dept')
        
        if User.query.filter_by(username=username).first():
            flash('用户名已存在')
        else:
            user = User(username=username, role=role, real_name=real_name, dept=dept)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('用户添加成功')
    
    users_list = User.query.all()
    return render_template('admin/users.html', users=users_list)

@admin.route('/user/delete/<int:id>', methods=['POST'])
@login_required
def delete_user(id):
    if current_user.role != 'leader':
        flash('需要领导权限')
        return redirect(url_for('valves.list'))
    
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('不能删除自己')
        return redirect(url_for('admin.users'))
    
    user.status = 'inactive'
    db.session.commit()
    flash('用户已禁用')
    return redirect(url_for('admin.users'))

@admin.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if current_user.role != 'leader':
        flash('需要领导权限')
        return redirect(url_for('valves.list'))
    
    if request.method == 'POST':
        auto_approval = request.form.get('auto_approval')
        setting = Setting.query.get('auto_approval')
        if setting:
            setting.value = auto_approval
        else:
            setting = Setting(key='auto_approval', value=auto_approval)
            db.session.add(setting)
        db.session.commit()
        flash('设置已保存')
    
    auto_approve = Setting.query.get('auto_approval')
    current_value = auto_approve.value if auto_approve else 'true'
    return render_template('admin/settings.html', auto_approval=current_value)
```

**Step 2: 提交**

```bash
git add app/routes/admin.py
git commit -m "feat: add admin management"
```

---

## Task 10: 前端模板完善

**Files:**
- Create: `templates/base.html`, `templates/index.html`, `templates/valves/*.html`, `templates/admin/*.html`

**Step 1: 创建 base.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}仪表阀门台账系统{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
</head>
<body>
    {% if current_user.is_authenticated %}
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container-fluid">
            <a class="navbar-brand" href="{{ url_for('index') }}">仪表阀门台账</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('index') }}">首页</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('valves.list') }}">台账列表</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('valves.new') }}">录入申请</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('valves.my_applications') }}">我的申请</a>
                    </li>
                    {% if current_user.role == 'leader' %}
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('valves.approvals') }}">审批管理</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('admin.index') }}">后台管理</a>
                    </li>
                    {% endif %}
                </ul>
                <span class="navbar-text me-3">
                    {{ current_user.real_name or current_user.username }} ({{ current_user.role }})
                </span>
                <a href="{{ url_for('auth.logout') }}" class="btn btn-sm btn-outline-light">退出</a>
            </div>
        </div>
    </nav>
    {% endif %}
    
    <div class="container mt-4">
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for message in messages %}
                    <div class="alert alert-info">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        {% block content %}{% endblock %}
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
```

**Step 2: 创建 index.html**

```html
{% extends "base.html" %}

{% block title %}首页 - 仪表阀门台账系统{% endblock %}

{% block content %}
<div class="row">
    <div class="col-md-12">
        <h1>欢迎使用仪表阀门台账管理系统</h1>
        <hr>
    </div>
</div>

<div class="row mt-4">
    <div class="col-md-4">
        <div class="card text-center">
            <div class="card-body">
                <h5 class="card-title">台账总数</h5>
                <h2 class="text-primary">{{ total }}</h2>
            </div>
        </div>
    </div>
    {% if current_user.role == 'leader' %}
    <div class="col-md-4">
        <div class="card text-center">
            <div class="card-body">
                <h5 class="card-title">待审批</h5>
                <h2 class="text-warning">{{ pending }}</h2>
                <a href="{{ url_for('valves.approvals') }}" class="btn btn-sm btn-outline-primary">查看</a>
            </div>
        </div>
    </div>
    {% endif %}
    <div class="col-md-4">
        <div class="card text-center">
            <div class="card-body">
                <h5 class="card-title">快捷操作</h5>
                <a href="{{ url_for('valves.new') }}" class="btn btn-primary">录入台账</a>
                <a href="{{ url_for('valves.import_data') }}" class="btn btn-outline-primary">导入数据</a>
                <a href="{{ url_for('valves.export_data') }}" class="btn btn-outline-primary">导出数据</a>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

**Step 3: 批量创建其他模板**

根据实际需要创建：
- `templates/valves/list.html` - 台账列表
- `templates/valves/detail.html` - 台账详情
- `templates/valves/form.html` - 台账表单
- `templates/valves/my_applications.html` - 我的申请
- `templates/valves/approvals.html` - 审批列表
- `templates/valves/import.html` - 导入页面
- `templates/valves/photos.html` - 照片管理
- `templates/valves/maintenance.html` - 维护记录
- `templates/admin/index.html` - 管理首页
- `templates/admin/users.html` - 用户管理
- `templates/admin/settings.html` - 系统设置

**Step 4: 提交**

```bash
git add templates/
git commit -m "feat: add frontend templates"
```

---

## Task 11: 主程序入口

**Files:**
- Modify: `main.py`

**Step 1: 更新 main.py**

```python
from app import create_app, db

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
```

**Step 2: 创建初始管理员用户**

Run: `python -c "
from app import create_app, db
from app.models import User, Setting

app = create_app()
with app.app_context():
    # 创建管理员
    admin = User(username='admin', role='leader', real_name='管理员', dept='管理部')
    admin.set_password('admin123')
    db.session.add(admin)
    
    # 创建测试员工
    employee = User(username='user1', role='employee', real_name='张三', dept='维修部')
    employee.set_password('user123')
    db.session.add(employee)
    
    # 默认自动审批
    setting = Setting(key='auto_approval', value='true')
    db.session.add(setting)
    
    db.session.commit()
    print('初始化完成!')
    print('管理员: admin / admin123')
    print('员工: user1 / user123')
"`

**Step 3: 提交**

```bash
git add main.py
git commit -m "feat: add main entry point and init data"
```

---

## Task 12: 测试运行

**Step 1: 运行应用**

Run: `python main.py`

Expected: 应用启动成功，访问 http://127.0.0.1:5000

**Step 2: 登录测试**

- 管理员: admin / admin123
- 员工: user1 / user123

**Step 3: 功能验证**

- [ ] 登录/登出
- [ ] 台账列表查看
- [ ] 新增台账
- [ ] 编辑台账
- [ ] 删除台账
- [ ] Excel 导入
- [ ] Excel 导出
- [ ] 照片上传
- [ ] 维护记录
- [ ] 审批管理（手动模式）
- [ ] 用户管理
- [ ] 系统设置

**Step 4: 提交**

```bash
git commit -m "chore: verify all features work"
```

---

## 实施计划完成

所有任务完成后，系统将具备以下功能：

1. ✅ 用户认证（登录/登出）
2. ✅ 台账管理（增删改查）
3. ✅ 审批工作流（自动审批 + 手动审批）
4. ✅ Excel 导入导出
5. ✅ 照片管理
6. ✅ 维护记录
7. ✅ 用户管理
8. ✅ 系统设置（自动审批开关）
