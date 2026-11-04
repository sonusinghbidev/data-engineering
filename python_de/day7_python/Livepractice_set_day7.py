# DAY 7 | PYTHON FUNCTIONS | LAMBDA FUNCTIONS | FILTER | MAP | REDUCE

# what  is functions?
# python functions are reusable and block of code of your use

from functools import reduce
from copy import copy, deepcopy
import copy
name = 'pratik'
# print(f'Hello {name}')
'''

def printfunc():
    print("Hello world custom")


# printfunc()

def sum_custiom(a, b):
    return (a+b)

# keyword arguments functions
# print(sum_custiom(2, 3))

def sumnew(a, b):
    print(a, b)
    return (a+b)

sumnew(b=3, a=5)


def sum_all(*numbers):
    print(numbers)
    return sum(numbers)


sum_all(1, 2, 3, 2, 1)


def sumnew(**info):
    print(info)
    return True

sumnew(b=6, a=7)
'''


print('-------------------------------------------------------------------')
print("Lambda Functions")
print('-------------------------------------------------------------------')


def dosquare(n):
    return n*n


print(dosquare(8))


def square(x): return x*x


print(f'Square of the 7 is: {square(7)}')


list1 = [1, 2, 3, 4, 5, [6, 7, 9]]
list2 = list1
list3 = list1.copy()
list4 = copy.deepcopy(list1)

list1[5][0] = 60

print(f'list2: {list2}, list3 : {list3}, list4: {list4}')

print(list2, list3, list4)

print('-------------------------------------------------------------------')
print("Filter, Map, Reduce")
print('-------------------------------------------------------------------')


# map function

numbers = [1, 2, 3, 4, 5, 6]

square2 = map(lambda x: x*x, numbers)

print(list(square2))

# filter functions
# filter(function, iterable)

even = filter(lambda x: x % 2 == 0, numbers)
print(list(even))


files = ['abc.csv', 'def.json', 'quiet.text', 'employees.csv']
csv_files = filter(lambda files_name: files_name.split('.')
                   [-1] == 'csv', files)
print(list(csv_files))


# Rreduce funtions
num = [1, 2, 3, 4]

total = reduce(lambda a, b: a+b, num)
print(total)

maxnum = [10, 45, 23, 89, 12]

value = reduce(lambda x, y: x if x > y else y, maxnum)
print(f'print the Maximum of value: {value}')


employees = [
    {'name': "Ajay", "salary": 80000},
    {'name': "Rahul", "salary": 55000},
    {'name': "Deep", "salary": 87000},
    {'name': "Shub", "salary": 92000},
]

# def filter_employees_earning_greater_60k (emplooyees):
#     if employe.

max_sal60 = filter(lambda emp: emp["salary"] > 80000, employees)

print(list(max_sal60))
