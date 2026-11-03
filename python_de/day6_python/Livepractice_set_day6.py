# DAY 6 | POSTGRES DB CONNECTION | DB SQL QUERIES USING PYTHON

import psycopg2
# conntect  database  using the python driver for the postgres

host = 'localhost'
database = 'python_practice'
username = 'postgres'
password = 'hari'

connection = psycopg2.connect(
    host=host,
    database=database,
    user=username,
    password=password
)

print("Connection Successful")
connection.close()

cursor = connection.cursor()
'''
cursor.execute('Select * from employyes')
row = cursor.fetchone()  # fetch 1st record
print(row)

rows = cursor.fetchall()  # fetch all record of the table
print(rows)

row2 = cursor.fetchmany(2)  # fetch only 2 rows
print(row2)

cursor.close()
connection.close()

# python(
#     it is used to build the connection with the database programatically
# )-> connection(
#     it will help use to build the conenction
# ) -> postgresdb(
# )
print("End of Code")

'''

query = """
        INSERT INTO employees ( 
        name, deparment, salary, city , joinind_date
    )
    VALUES(
        %s, %s, %s, %s %s
    )

 """

values = (
    "Vikas",
    "Data Engineering",
    90000,
    "Banglore",
    "2025-01-15"
)

cursor.execute(query, values)
# connection.commit()
