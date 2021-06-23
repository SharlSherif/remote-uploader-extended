import os
from pymongo import MongoClient, InsertOne, DeleteOne, ReplaceOne
from pymongo.errors import BulkWriteError
from dotenv import load_dotenv

load_dotenv()

dbconnection= os.environ.get("dbconnection")
dbname= os.environ.get("dbname")
print(f"DB Name={dbname}")

client = MongoClient(dbconnection, tls=True,tlsAllowInvalidCertificates=True)
metadata_db = client[dbname]
