# coding=utf-8
def test_login_page(client, init_database):
    """测试登录页面"""
    response = client.get('/login')
    assert response.status_code == 200
    assert b'登录' in response.data

def test_login_success(client, init_database):
    """测试登录成功"""
    response = client.post('/login', data={
        'username': 'admin',
        'password': 'admin123'
    }, follow_redirects=True)
    assert response.status_code == 200

def test_login_failure(client, init_database):
    """测试登录失败"""
    response = client.post('/login', data={
        'username': 'admin',
        'password': 'wrongpassword'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'用户名或密码错误' in response.data

def test_logout(client, init_database):
    """测试登出"""
    client.post('/login', data={
        'username': 'admin',
        'password': 'admin123'
    })
    response = client.get('/logout', follow_redirects=True)
    assert response.status_code == 200
