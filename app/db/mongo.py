# app/db/mongo.py
from pymongo import MongoClient
from bson.binary import Binary

MONGO_URL = "mongodb://localhost:27017"   # ปรับตามของเราได้
client = MongoClient(MONGO_URL)

db = client["smart_carb"]                 # ชื่อ database
food_images_col = db["food_images"]       # ชื่อ collection ที่ใช้เก็บรูป

# helper เอา bytes ไปห่อเป็น Binary ของ Mongo
def wrap_binary(data: bytes) -> Binary:
    return Binary(data)
