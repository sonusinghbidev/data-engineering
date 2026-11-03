import requests

url = 'https://ev-project-navy-mu.vercel.app/api/auth/login/'

payload = {
    "username": "voltgrid_demo",
    "password": "EVcharge@AU2025"
}

response = requests.post(
    url,
    json=payload
)

# print(response.status_code)
token = response.json().get('token')

print("------------------------------------------------------------------------------------------------")
print("Payments API")
print("------------------------------------------------------------------------------------------------")

base_url = 'https://ev-project-navy-mu.vercel.app/'
payment_endpoint = '/api/db/payments/'
full_url = base_url+payment_endpoint

parmas = {
    "page": 1,
    "page_size": 20,
    "updated_after": '2026-07-01T21:04:00Z'
}

headers = {
    "authorization": f"Token {token}",
    "content-type": 'applicaiton/json'
}


response = requests.get(
    full_url,
    params=parmas,
    headers=headers
)

print(response.json())
