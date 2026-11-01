# DAY 5 | PYTHON | Aug Batch 4+ Months Sessions - 2026/08/08 20:48 IST - Recording
# DAY 5 | FILE HANDLING |  JSON | CSV | REQUESTS METHOD | API CALLS | JSON DATA

import os
import time
import json
import csv
import requests
print("File Handling")


# if you want to call any api in python  you need to get request method for it

# Get Method - To get the data from API
# POST Method - To post the data (to fill the data)
# Put method -  to update the all the records of the API
# Patch method - to update the partial records in API

'''
response = requests.get("https://jsonplaceholder.typicode.com/users")
data = response.json()
# print(data[0].keys())
# print(data[0].values())
print('------------------------------------------------------------------------------------------')
print(data[0].get('username'))
print(data[0].get('address'))
'''

print('------------------------------------------------------------------------------------------')

'''
params = {"userId": 1}
response = requests.get(
    "https://jsonplaceholder.typicode.com/posts",
    # "https://jsonplaceholder.typicode.com/posts?userId=5",
    params=params,
    timeout=10
)

posts = response.json()
print(posts)

print('------------------------------------------------------------------------------------------')

for post in posts:
    # print(post['title'])
    print(post.get('title'))
'''

print('------------------------------------------------------------------------------------------')
print('Reading JSON file')
print('------------------------------------------------------------------------------------------')
'''

# with open method  we can read the file and we have multiple modes to open the file
# using the with statement you do not need the close the file  it will handle


with open('python_de/day5_python/employees.csv', 'r') as file:  # read the file
    data = file.readlines()
    for line in data:
        print(line)

# write the file. it full write the file.
with open('python_de/day5_python/notepad.txt', 'r') as file:
    data = file.readlines()
    for line in data:
        print(line)

with open('python_de/day5_python/notepad.txt', 'a') as file:  # append the data in existing file
    file.write("\nWelcome in Data Engineering Program")


with open('python_de/day5_python/notepad2.txt', 'x') as file:  # create a new file
    file.write("Hi This is new notepad.\nWelcome in Data Engineering Program")
'''

print('------------------------------------------------------------------------------------------')
print('Reading CSV file')
print('------------------------------------------------------------------------------------------')
'''
# print('///////////////////////////////////')
with open('python_de/day5_python/employees.csv', 'r') as file:
    rows = csv.reader(file)
    header = next(rows)
    print('Header==>', header)

    for row in rows:
        print('Rows==>', row)

print("Dictionary Reader-------------------------------")
with open('python_de/day5_python/employees.csv', 'r') as file:
    rows = csv.DictReader(file)

    for row in rows:
        print(row)


# write mode in csv files

with open('output.csv', 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['id', 'name'])
    writer.writerow([1, 'Venky'])
    print("succesful write done ")

with open('output.csv', 'r') as file:
    print(file.read())

'''
print('------------------------------------------------------------------------------------------')
print('Reading JSON file')
print('------------------------------------------------------------------------------------------')
'''
with open('python_de/day5_python/orders.json', 'r') as file:
    data = json.load(file)
    print(data)


with open('python_de/day5_python/order2.json', 'a') as file:
    json.dump(data, file, indent=4)
    print("dumping done........................")
'''
print('------------------------------------------------------------------------------------------')
print('HTTP Method')
print('------------------------------------------------------------------------------------------')


url = "https://jsonplaceholder.typicode.com/posts"

payload = {
    "title": "Python",
    "body": "Learning APIs",
    "userId": 1
}

response = requests.post(url, json=payload)
print(response)
print(response.status_code)
