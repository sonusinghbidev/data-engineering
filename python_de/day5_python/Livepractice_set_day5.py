# DAY 5 | PYTHON | Aug Batch 4+ Months Sessions - 2026/08/08 20:48 IST - Recording
# DAY 5 | FILE HANDLING |  JSON | CSV | REQUESTS METHOD | API CALLS | JSON DATA

# import os
# import time
# import csv
# import json
import requests
print("File Handling")


# if you want to call any api in python  you need to get request method for it

# Get Method - To get the data from API
# POST Method - To post the data (to fill the data)
# Put method -  to update the all the records of the API
# Patch method - to update the partial records in API


response = requests.get("https://jsonplaceholder.typicode.com/users")
data = response.json()
# print(data[0].keys())
# print(data[0].values())
print('------------------------------------------------------------------------------------------')

print(data[0].get('username'))
print(data[0].get('address'))
