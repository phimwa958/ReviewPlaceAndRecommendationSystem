import pandas as pd

# โหลดข้อมูล reviews.xlsx
df_reviews = pd.read_excel('reviews.xlsx')

# คำนวณค่าเฉลี่ย rating ของแต่ละ place_id
average_ratings = df_reviews.groupby('place_id')['rating'].mean()

# โหลดข้อมูล places.xlsx
df_places = pd.read_excel('places.xlsx')

# สร้างคอลัมน์ average_rating ถ้ายังไม่มี
if 'average_rating' not in df_places.columns:
    df_places['average_rating'] = 0

# อัปเดตค่า average_rating ใน df_places
for place_id, avg_rating in average_ratings.items():
    df_places.loc[df_places['id'] == place_id, 'average_rating'] = avg_rating

# ตรวจสอบจำนวนสถานที่
if df_places.shape[0] != 316:
    print(f"คำเตือน: พบสถานที่ทั้งหมด {df_places.shape[0]} แห่ง (ควรเป็น 316)")

# บันทึกผลกลับไป (คุณอาจหมายถึงบันทึก df_places ไม่ใช่ df_reviews)
df_places.to_excel('places.xlsx', index=False)

print("✔️ อัปเดต average_rating เรียบร้อยแล้ว")
