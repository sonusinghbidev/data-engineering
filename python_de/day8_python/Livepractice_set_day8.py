# DAY 8 | RECURSIVE FUNCTIONS | PRACTICE QUESTIONS | DATA CLEANING |

# problem solving

a = 9

# if a or b:
#     print('inside if')  # name 'b' is not defined
# #

list1 = [3, 5, 2, 0, 3, 0, 8, 5]

# exp_out = [8, 3, 2, 3]
print(list1[-2::-2])


list2 = [[1, 2], [3, 4], [5, 6, 7, [1, 2, 3]]]

# expected output :[1,2,3,4,5,6,7,1,2,3]

# flat_list = [item for bulist in list2 for item in sublist]
# print(f"flat List: {flat_list}")


def flatten(data):
    return [x for item in data
            for x in (flatten(item) if isinstance(item, list) else [item])]


print(flatten(list2))

# def flatten(data):
#     result = []
#     for item in data:
#         try:
#             result.extend(flatten(item))

#         except TypeError:
#             result.append(item)
#     return result


# print(flatten(list2))

n = 3


def hell(n):
    if n == 0:
        return
    print(f'Hello {n}')
    hell(n-1)


hell(n)


users = [
    {"id": 1, "name": "  amit sharma ", "age": 25},
    {"id": 2, "name": "RAHUL KUMAR", "age": 30},
    {"id": 3, "name": "", "age": 22},
    {"id": 4, "name": " priya ", "age": None},
    {"id": 5, "name": "  raj  ", "age": 28}
]

# Requirements
# Remove records where name is empty.
# Remove records where age is missing.
# Strip spaces from names.
# Convert names to title case.


clean_user = []

for user in users:
    name = user["name"].strip()
    age = user["age"]
    if name == "":
        continue
    if age is None:
        continue
    user["name"] = name.title()
    clean_user.append(user)

# print(clean_user)


# problem 2

list1 = [1, 2, 3, 4, 5]

# for num in list1:
#     if num % 2 == 0:
#         continue
#     print(num)


for num in list1:
    if num > 3:
        break
    print(num)


# lsit_1 =  [1, 2, 1, 3, 4, 2]

# output=[]
# iter1
# output = [1, 2, 3, 4]

# # iter2

# output [1, 2, 3, 4]


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
