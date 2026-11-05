# Python Data Engineering Practice

A structured collection of Python lessons, practice problems, solutions, and interview questions for learning core Python concepts used in data engineering.

## Topics Covered

The material is organized by day:

| Day | Topics |
|---|---|
| Day 1 | Variables, data types, operators, lists, and basic input/output |
| Day 2 | Lists, tuples, sets, strings, slicing, and built-in methods |
| Day 3 | Conditional statements, loops, loop control, and comprehensions |
| Day 4 | Dictionaries, nested dictionaries, iteration, and dictionary methods |
| Day 5 | File handling, CSV, JSON, HTTP methods, APIs, and the `requests` library |
| Day 6 | Live practice covering loops, zip, enumerate, comprehensions, and dictionaries |
| Day 7 | Functions, positional and keyword arguments, `*args`, `**kwargs`, lambdas, and copy behavior |
| Day 8 | `map()`, `filter()`, `reduce()`, shallow and deep copy, and combining functional operations |
| Day 9 | Problem-solving patterns, recursion, data cleaning, deduplication, and loop control |
| Day 10 | List and dictionary comprehensions, exception handling, modules, virtual environments, and deployment |

The repository also includes:

- Notebook solutions for Days 1 and 2
- Practice problem sets for each topic
- An interview preparation file containing 210 Python problems
- CSV and JSON examples for file-processing practice
- Examples for calling a public REST API

## Project Structure

```text
python_de/
|-- main.py
|-- interview_problems.md
|-- day1_python/
|   |-- Livepractice_set_day1.py
|   |-- day1_problems.md
|   `-- day1_solution.ipynb
|-- day2_python/
|   |-- Livepractice_set_day2.py
|   |-- day2_notes.md
|   |-- day2_problems.md
|   `-- day2_solution.ipynb
|-- day3_python/
|   |-- Livepractice_set_day3.py
|   |-- day3_notes.md
|   `-- day3_problems.md
|-- day4_python/
|   |-- Livepractice_set_day4.py
|   |-- day4_notes.md
|   `-- day4_problems.md
|-- day5_python/
|   |-- Livepractice_set_day5.py
|   |-- day5_notes.md
|   |-- day5_problems.md
|   |-- employees.csv
|   |-- orders.json
|   `-- order2.json
|-- day6_python/
|   |-- Livepractice_set_day6.py
|   |-- Livepractice_set_day6.1.py
|   |-- day6_notes.md
|   |-- day6_problems.md
|   |-- employees.sql
|   `-- requirements.txt
|-- day7_python/
|   |-- Livepractice_set_day7.py
|   |-- day7_notes.md
|   `-- day7_problems.md
|-- day8_python/
|   |-- Livepractice_set_day8.py
|   |-- day8_notes.md
|   `-- day8_problems.md
|-- day9_python/
|   |-- Livepractice_set_day9.py
|   |-- day9_notes.md
|   `-- day9_problems.md
`-- day10_python/
    |-- Livepractice_set_day10.py
    |-- day10_notes.md
    `-- day10_problems.md
```

## Prerequisites

- Python 3.10 or later recommended
- `requests` package for Day 5 API examples
- Jupyter Notebook or JupyterLab optional, for opening `.ipynb` files

## Setup

Clone the repository and navigate to the parent directory that contains `python_de`:

```bash
cd path/to/data-engineering
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# Windows Command Prompt
.venv\Scripts\activate.bat

# Linux/macOS
source .venv/bin/activate
```

Install the API dependency:

```bash
python -m pip install requests
```

## Usage

Run the environment check:

```bash
python python_de/main.py
```

Run a daily practice script:

```bash
python python_de/day1_python/Livepractice_set_day1.py
python python_de/day4_python/Livepractice_set_day4.py
python python_de/day5_python/Livepractice_set_day5.py
```

Open notebook solutions with Jupyter:

```bash
jupyter notebook python_de/day1_python/day1_solution.ipynb
```

Many examples read files with paths beginning at the repository or parent directory. Run commands from the `data-engineering` directory so paths such as `python_de/day5_python/employees.csv` resolve correctly.

## Recommended Workflow

1. Read the day notes.
2. Attempt the problems in the matching `day*_problems.md` file.
3. Run the live practice script to study working examples.
4. Compare your result with the available notebook solution.
5. Keep solutions separate when possible so the original practice problems remain untouched.

## Interview Practice

The [interview problems](interview_problems.md) file contains 210 problems across areas including:

- Lists, dictionaries, strings, tuples, and sets
- Functions and comprehensions
- Data cleaning and file handling
- API requests
- Database connections
- Arrays, hashing, two pointers, sliding windows, and sorting

## Notes

- Day 5 API examples use the public JSONPlaceholder service: `https://jsonplaceholder.typicode.com`
- Internet access is required for API requests.
- Example scripts contain both active exercises and commented reference code.
- Some scripts use intentionally small examples to demonstrate Python behavior; they are not production applications.
