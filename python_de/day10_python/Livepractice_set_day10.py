# DAY 10 | DSA PRACTICE | HASH MAP | HASH SET | TWO POINTER

# Hash map problem

# The goal is to find two numbers in a list whose sum equals the target value and print their indexes.

# two sum problem
input_list = [2, 7, 11, 15]
target = 9

output = [0, 1]

storage = {}

for i, value in enumerate(input_list):
    complement = target - value

    if complement in storage:
        print(storage[complement], i)
        break
    storage[value] = i


# character freq from the string

string_value = 'programming'

# freq = {}

# for s in string_value:
#     if freq.get(s) is None:
#         freq[s] = 1
#     else:
#         freq[s] += 1

# for s in string_value:
#     freq[s] = freq.get(s, 0) + 1

# print(freq)


# non repeating 1st character  from the string

# string = 'abbcde'

# unique = {}

# for char in string:
#     ifunique[char] == 1:
#         print(char)
#         break


# Valid anagram

string1 = "listen"
string2 = "silent"

freq = {}


def anagram(string1, string2):

    if len(string1) != len(string2):
        return False

    for s in string1:
        if freq.get(s) is None:
            freq[s] = 1
        else:
            freq[s] += 1
    print(freq)


anagram(string1, string2)


# # non repeating 1st character from the string
# string_value = "aabbcde"


# # Valid Anagram
# string1 = "listen"
# string2 = "silent"
# freq = {}


# def anagram(string1, string2):

#     if len(string1) != len(string2):
#         return False

#     for s in string1:

#         if freq.get(s) is None:
#             freq[s] = 1

#         else:
#             freq[s] += 1

#     for char in string2:

#         if char not in freq:
#             return False

#         # string 1 has 2 times h and string 2 also has h 2 times 2-3=-1


#         freq[char]-=1 # freq = {'l': -1, 'i': 1, 's': 1, 't': 1, 'e': 1, 'n': 1}

#         if freq[char]<0:
#             return False

#     return True
# anagram(string1, string2)


# string1 = ["Haarioom"]
# string2 = ["aariomoHa"]

# freq = {"H": 0, "a": 0, "r": 0, "i": 0, "o": 0, "m": 0}


# Two Sum II
# Two pointer problem
nums = [2, 3, 4, 7, 8]

target = 11

pointer1 = 0
pointer2 = len(nums)-1

while pointer1 < pointer2:
    total = nums[pointer1] + nums[pointer2]

    if total == target:
        print([pointer1, pointer2])
        break
    elif total < target:
        pointer1 += 1
    else:
        pointer2 -= 1
