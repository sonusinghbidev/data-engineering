# DAY 2 | LIST | STRING | SLICING | LIST METHODS | STRING METHODS
'''
Here is a summary of the learning points covered in the video, organized by topic:

  Repository Management & Git Workflow**
    
  Use `git clone` once initially, then run `git pull origin August batch` daily to update local session materials and notes.

  Python List Fundamentals & Properties**
      *Definition: A sequential data type capable of holding heterogeneous elements (strings, numbers, booleans, etc.).
      *Mutability: Lists are mutable, meaning their elements can be modified, updated, or reassigned directly in place.
      *Duplicates: Lists permit duplicate values.

  *List Slicing Techniques
      * **Basic Slicing (`[start:stop]`):** Extracts items starting from `start` up to `stop - 1` (the `stop` index is excluded).
      * **Open-ended Slicing (`[start:]`):** Omitting the `stop` index slices through the end of the list.
      * **Step Slicing (`[start:stop:step]`):**
          * A step size of `2` skips every other element.
          * A step size of `-1` reverses the list sequence.
      * **Negative Index Slicing:** Negative indices count elements backwards starting from the end (`-1` being the last element).

  *List Methods
      * **`len()`:** Returns the total count of items in a list.
      * **`append(x)`:** Appends the object `x` as a single element to the end of the list (a nested list appended this way remains a single sub-list item).
      * **`extend(iterable)`:** Iterates through an iterable object and appends each element individually to the end of the list.
      * **`insert(index, element)`:** Places a specified value at a precise index position.
      * **`remove(value)`:** Deletes the very first occurrence of a specified value from the list.
      * **`pop([index])`:** Removes and returns an item. If no index is provided, it removes and returns the last element. If an index is provided, it removes the item at that position.
      * **`index(value)`:** Returns the index position of the first occurrence of a specified value.
      * **`count(value)`:** Counts and returns how many times a given value appears in the list.
      * **`copy()` vs. Assignment Operator (`=`):**
          * Using the `=` operator creates a reference pointing to the existing memory address; altering one variable modifies the other.
          * Using `.copy()` creates a distinct shallow copy in a separate memory location, protecting the original list from direct changes.
      * **`sort()` vs. `sorted()`:**
          * `.sort()` modifies the original list directly in place and returns `None`.
          * `sorted()` generates and returns a new sorted list while keeping the original list intact.
          * Passing `reverse=True` to either method sorts the list in descending order.

  *String Properties & Behavior
    
      * **Immutability:** Strings are immutable in Python; individual characters cannot be reassigned or replaced using index assignment (`string[0] = 'a'` throws a TypeError).
      * **Slicing:** Strings support the same indexing and step-slicing mechanics as lists.


'''

'''
a = [1, 2, 3]

# b = a
# b[0] = 10
# print(a, b)

b = a.copy() # with copy method, we can create a new list that is a copy of the original list
b[0] = 10
print(a, b) 
'''
# Sort & Sorted method

'''
s = [3, 4, 9, 1, 2, 5]
s.sort()  # sort method modifies the original list in place
print(s)


s2 = sorted(s)   # sorted function returns a new sorted list, leaving the original list unchanged
print(s, s2)

# sort method with reverse parameter sorts the list in descending order
s.sort(reverse=False)  # sort method modifies the original list in place
print(s)
////////////////////////////////////////////////////////////////////////////////////////////////

'''
'''
////////////////////////////////////////////////////////////////////////////////////////////////
# string methods


name = "Data Engineering"
# name[0] = "p"
# print(name)
# P y t h o n
# 0 1 2 3 4 5
#
print(name[:2:2])  # slicing the string from index 1 to 3 (4 is excluded)
print(name[-5:3])
////////////////////////////////////////////////////////////////////////////////////////////////
'''
'''
////////////////////////////////////////////////////////////////////////////////////////////////
phone = '23169639'
print(phone.isdigit())


alnum = 'SDX67229X'
print(phone.isalnum())

# Tuple is mutable , hold duplicates, slicing indexing

print("Tuple Topics!!!")

tuple1 = (3, 4, "BD")
tuple2 = (5)
tuple3 = (3, )

print(type(tuple1), type(tuple3), type(tuple3))


num = (2, 4, 1, 8, 5, 3, 4)
print(num)
print(num[2:])
print(num[:34])
print(num[34:])


# Tuple Methods

print(num.count(4))

# index method

print("Index Method: ", num.index(8))

student = ("Ashu", "Python", 32)

name, course, age = student
print(name, course, age)
////////////////////////////////////////////////////////////////////////////////////////////////
'''


# Set
'''A set is a collection of unique items in Python. Sets do not allow duplicate items and do 
    not maintain any particular order so it can’t be indexed.'''
# it is mutable
# it does not hold duplicate values
# it is unodered
# slicing & indexing will not work

a = {1, 2, 4, 6, 7, 4, 6}
print(a)
a.add(8)
print(a)
a.remove(8)
print(a)

'''
remove() raises an error if the element is not found.  
discard() does not raise an error if the element is missing.
'''
emptyset = {}  # it will create a empty dictionary
print(emptyset)
print(type(emptyset))

# An empty set cannot be created using {} as it creates an empty dictionary. Use set() instead.
emptyset_construct = set()
print(emptyset_construct)
print(type(emptyset_construct))


# Problem Solving

list = [1, 3, 5, 8]

# remove the 1st and alst value frome it and give the sum of it

list.remove(1)
list.remove(8)
print(list, sum(list))

print('problem 2')

phone_num = ["+91 9329302102", '+1 3212031022',
             '+123 9323843276', '9112134533']

output_2 = []

for num in phone_num:
    digit = num.replace("-", "").replace(" ", "")
    output_2.append(int(digit[-10:]))

print(output_2)

# Problem 3
print('Problem 3')

emails = ['abc@google.com', 'syed@gmail.com',
          'har@dataengineeringdaily.com', 'ashu@yahoo.com', 'bob@gmail.com', 'alice@google.com']

output3 = {}

for email in emails:
    domain = email.split("@")[1]

emails = ['abc@google.com', 'syed@gmail.com',
          'har@dataengineeringdaily.com', 'ashu@yahoo.com', 'bob@gmail.com', 'alice@google.com']

output3 = {}

for email in emails:
    domain = email.split("@")[1]
    # output3.add(domain)

    if domain in output3:
        output3[domain] = output3[domain] + 1
    else:
        output3[domain] = 1


print(output3)


# print(emails.substitue("@"))

# Problem 4
orders = ['order_393993.csv', 'order_773773.csv', 'order_393939.csv']
output4 = []

for files in orders:
    file_num = files.split("_")[1].split('.')[0]
    output4.append(int(file_num))
print(output4)


# Problem 5

input2 = [393993, 773773, 393939]

output5 = []

for order in input2:
    filename = 'order_' + str(order) + '.csv'
    output5.append(filename)

print(output5)


# problem 6

names = [' hAriom', 'we erf', 'RaHuL']

output6 = []

for name in names:
    name = name.replace(' ', '')
    name = name.strip()
    name = name.capitalize()

    output6.append(name)

print(output6)
