# if else elif for loop and while loop

# number = 10

# if number > 2:
#     print('Grater 2')
# else:
#     print("less 2")

# # need to print numbers from 1 to 10

# for i in range(11):
#     print(i)

# for j in range(1, 10, 2):
#     print(j)


list1 = [5, 3, 9, 0, 11, 10]

for value in list1:
    if value > 5:
        print(value)

print('Newllllllllllllllll')
for value in list1[1:3]:
    if value > 5:
        print(value)

# for while loop


# num = 1
# while num < 101:
#     print(num)
#     num += 1


# List comprehension
# output = [
#     num**2 for num in numbers
# ]
# print(output)


# number = [1, 2, 3, 4, 5, 6]

# for num in input:
#     if num%2==0:
#         print(num)


# output = [num for num in number if num%2==0 ]
# print(output)


# output = ["Even" if num%2==0 else "Odd" for num in number]
# print(output)


# matrix = [
#     [1, 2],
#     [3, 4],
#     [5, 6]
# ]
# expted output should be [1, 2, 3, 4, 5, 6]

# output = [
#     num
#         for row in matrix
#         for num in row
#     ]
# print(output)

# numbers = [1, 2, 3, 4, 5, 6]
# output = {}
# expected output = { 1: 1, 2: 4, 3: 9, 4: 16, 5: 25, 6: 36}

# for num in numbers:
#     output[num] = num**2
# print(output)

# output = {
#     num:num**2 for num in numbers
# }
# print(output)

# duplicate_numbers = [1, 2, 1, 1, 2, 3, 3, 5]
# print(duplicate_numbers)
# output = {}
# for number in duplicate_numbers:
#     if number not in output.keys():
#         output[number] = 1
#     else:
#         output[number]+=1
# print(output)

# 1st iteration number=1, output= {1:1}
# 2nd iteration number=2, output= {1:1, 2: 1}
# 3rd iteration number=1, output = {1:2, 2:1}
# 4th iteration number=1, output = {1:3, 2:1}
# 5th iteration number=2, output= {1:3, 2: 2}

keys = ['name', 'phone', 'email']
values = ['Rahul', 8388833, 'rahul@gmail.com']

# print(zip(keys, values))
# output = {}
# for key, value in zip(keys, values): # zip will make data like this [('name', 'rahul'), ('phone', 4388338)]
#     output[key] = value
# print(output)


# expected output = {
#     "name": "Rahul",
#     "phone": 8388833,
#     "email": 'rahul@gmail.com'
# }


# expected output

# enuerate will hold values like this [(0, 'rahul'), (1, 3434343)]
for index, value in enumerate(values):
    print(index, value)

# {
#     0: "Rahul",
#     1: 388383,
#     2: 'rahul@gmail.com'
# }
