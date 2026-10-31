# Dictonary
# it is data type key value
# it is mutable
# it will not have index it has key value
# it have dplicates values but not dupicate key

students = {
    "Name": "Rahul",
    "course": "DE",
    "duration": "4 Months",
    "age": 23,
    "age2": 33,
    "marks": [93, 78, 89, 43, 56, 40.5],
    "details": {
        "id": 1,
        "address": "delhi"
    }
}

print(type(students))
print(students)
print(students["age"])
print(students["details"])
# print(students["details"][0])

# print(students["school"])

# it willhelp to define the if key is missing
print(students.get("school", "no school"))
print('----------------------------------------------------------------------------------')

students["school"] = ["Public School", "Delhi Public School"]

print(students)

print('----------------------------------------------------------------------------------')
# it will help us to update the values
students["age"] = 55
# print(students)

print('----------------------------------------------------------------------------------')

del students["age2"]

# print(students)

students.pop("age")
print(students)
print('----------------------------------------------------------------------------------')

# it will remove the latest added item in the dictionary

students.popitem()
# print(stundents)
print('----------------------------------------------------------------------------------')
print("Dictionary Method")
print('----------------------------------------------------------------------------------')

# print(students.keys()) # getting the keys
# print(students.values()) # getting the values

# How to get nested keys

# print(students.get("details")[0].keys()) #found error

# itetrates ditionary keys
for key in students:
    # print(key)
    # we should use get to handle error of if key is not available in dic
    print(students.get(key))


# itetrates ditionary values

for value in students.values():
    print(value)

# it will convert value in tuple
# print(students.items())

# iterating a dictionary with the help of items method
for key, value in students.items():
    print(key, value)
