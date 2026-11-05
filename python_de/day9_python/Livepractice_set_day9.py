# DAY 9 | HASH MAP | HASH SET | LIST | DSA PROBLEM SOLVING

# Remove duplicates based on id
# Hashset

customers = [
    {"id": 101, "name": "Amit", "email": "amit@gmail.com", "weight": 44},
    {"id": 102, "name": "Rahul", "email": "rahul@gmail.com", "weight": 87},
    {"id": 101, "name": "Amit", "email": "amit@gmail.com", "weight": 65},
    {"id": 103, "name": "Priya", "email": "priya@gmail.com", "weight": 61},
    {"id": 102, "name": "Rahul", "email": "rahul@gmail.com", "weight": 70}
]


output = {}

for customer in customers:
    output[customer['id']] = customer
print(list(output.values()))


# list1 = [1, 2, 1, 3, 4, 2]
# output1 = []

# for lis in list1:
#     output1[list1] = list1
# print((output1.values()))


my_set = set()

output2 = []

for customer in customers:

    id = customer["id"]
    if id not in my_set:
        output2.append(customer)
        my_set.add(id)
# print(output2)

print("_________________________________________________________________________________________")
print("Problem")
print("_________________________________________________________________________________________")

emails = [
    "  AMIT@GMAIL.COM ",
    "rahul@gmail.com",
    "priya@gmail",
    "",
    "  raj@yahoo.com",
    "invalid-email",
    None,
    "rahul.kumar@gmail"
]
# Requirements:
# Handle None
# Remove spaces
# Convert to lowercase
# Validate @
# Validate .
# Return None for invalid emails

for email in emails:
    if email is None:
        continue
    email = email.strip().lower()

    if email == "" or "@" not in email or ".com" not in email:
        continue

    print(email)


print("_________________________________________________________________________________________")
print("employees_output")
print("_________________________________________________________________________________________")


employees = [
    {"id": 1, "name": "Amit", "salary": 50000},
    {"id": 2, "name": "Rahul"},
    {"id": 3, "name": "Priya", "salary": None},
    {"id": 4, "name": "Raj", "salary": 70000}
]

for employee in employees:
    if employee.get("salary"):
        employee["salary_status"] = "available"
    else:
        employee["salary"] = 0
        employee["salary_status"] = "missing"
    # print(employee)


# employees_output = [
#     {"id": 1, "name": "Amit", "salary": 50000, "salary_status": "available"},
#     {"id": 2, "name": "Rahul", "salary": 0, "salary_status": "missing"},
#     {"id": 3, "name": "Priya", "salary": 0, "salary_status": "missing"},
#     {"id": 4, "name": "Raj", "salary": 70000, "salary_status": "available"}
# ]


transactions = [
    {"id": 1, "customer": "Amit", "amount": 500},
    {"id": 2, "customer": "Rahul", "amount": -100},
    {"id": 3, "customer": "Priya", "amount": 700},
    {"id": 4, "customer": "Raj", "amount": None},
    {"id": 5, "customer": "Amit", "amount": 500},
    {"id": 3, "customer": "Priya", "amount": 700}
]

# Find:

# Negative amounts
# Missing amounts
# Duplicate transaction IDs
# Valid transactions

# Soltuon

negative_transactions = []
missing_transactions = []
duplicate_transactions = []
valid_transactions = []

# Track transaction IDs that we have already seen

seen_id = set()
# my code

for transaction in transactions:
    # transaction_id = transaction["id"]
    # amount = transaction["amount"]

    if transaction["amount"] is None:
        missing_transactions.append(transaction)

    elif transaction["amount"] < 0:
        negative_transactions.append(transaction)

    elif transaction['id'] in seen_id:
        duplicate_transactions.append(transaction)
    else:
        valid_transactions.append(transaction)

    seen_id.add(transaction["id"])


print("Negative Transactions:", negative_transactions)
print("Missing Transactions:", missing_transactions)
print("Duplicate Transactions:", duplicate_transactions)
print("Valid Transactions:", valid_transactions)
