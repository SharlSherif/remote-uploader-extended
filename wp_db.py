import mysql.connector as db

wp_db = db.connect(host="localhost", user='root',
                    password='root', database='porn', buffered=True)

if wp_db.is_connected():
    print('Connected to SQL DB')
else:
    print("DB ERROR")

cursor = wp_db.cursor()