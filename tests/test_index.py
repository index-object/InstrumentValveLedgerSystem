def test_index_requires_login(client, init_database):
    response = client.get('/')
    assert response.status_code == 302

def test_index_with_login(client, init_database):
    client.post('/login', data={'username': 'admin', 'password': 'admin123'})
    response = client.get('/')
    assert response.status_code == 200
    assert b'台账' in response.data
