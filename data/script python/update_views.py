import pandas as pd

# โหลดข้อมูล visit_place.xlsx
df_visits = pd.read_excel('visit_place.xlsx')

# รวม visit_place ของแต่ละ place_id
visit_totals = df_visits.groupby('place_id')['visit_place'].sum()

# โหลดข้อมูล places.xlsx
df_places = pd.read_excel('places.xlsx')

# สร้างคอลัมน์ visit_count ถ้ายังไม่มี
if 'visit_count' not in df_places.columns:
    df_places['visit_count'] = 0

# อัปเดตค่า visit_count จาก visit_totals
for place_id, total in visit_totals.items():
    df_places.loc[df_places['id'] == place_id, 'visit_count'] = total

# ตรวจสอบว่ามีสถานที่ครบ 316 แห่งไหม
if df_places.shape[0] != 316:
    print(f"คำเตือน: พบสถานที่ทั้งหมด {df_places.shape[0]} แห่ง (ควรเป็น 276)")

# บันทึกผลกลับไป
df_places.to_excel('places.xlsx', index=False)

print("✔️ อัปเดต visit_count เรียบร้อยแล้ว")
