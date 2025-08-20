import pandas as pd
import random

# กำหนดจำนวน
num_users = 60
num_places = 316
target_rows = 12000

# สร้าง user_id และ place_id
user_ids = list(range(1, num_users + 1))
place_ids = list(range(1, num_places + 1))

# ใช้ set เพื่อกันค่าซ้ำ
unique_likes = set()

# วนสร้างข้อมูลไม่ซ้ำจนกว่าจะครบ 9000 แถว
while len(unique_likes) < target_rows:
    u = random.choice(user_ids)
    p = random.choice(place_ids)
    unique_likes.add((u, p))

# แปลงเป็น DataFrame
data = list(unique_likes)
df = pd.DataFrame(data, columns=["user_id", "place_id"])
df.insert(0, "id", range(1, len(df)+1))

# บันทึกเป็น Excel
df.to_excel("place_likes.xlsx", index=False)

print(f"สร้างข้อมูลแล้ว: {df.shape[0]} แถว บันทึกลง place_likes.xlsx")
