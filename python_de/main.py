import sys
import os

print("Python executable:", sys.executable)
print("Python version:", sys.version)
print("Virtual environment:", os.environ.get("VIRTUAL_ENV", "Not set"))
