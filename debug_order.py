import requests
import json

try:
    r = requests.post('http://127.0.0.1:5000/api/order', json={
        'name': 'Test',
        'email': 'test@example.com', 
        'phone': '1234567890',
        'items': []
    })
    print(r.status_code)
    print(r.text)
except Exception as e:
    print(e)
