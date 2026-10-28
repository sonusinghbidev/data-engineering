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

'''

# string methods


name = "Data Engineering"
# name[0] = "p"
# print(name)
# P y t h o n
# 0 1 2 3 4 5
#
print(name[:2:2])  # slicing the string from index 1 to 3 (4 is excluded)
