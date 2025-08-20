# เอกสารสรุป ระบบแนะนำ (Definitive Guide: Recommendation System)

## 1. ภาพรวมและสถาปัตยกรรม (Overview and Architecture)

### 1.1 วัตถุประสงค์
ระบบแนะนำถูกออกแบบใหม่ทั้งหมดโดยแยกตรรกะออกจากแอปพลิเคชันหลัก (`review_place`) มาไว้ในแอป `recommendations` ของตัวเอง เพื่อเพิ่มความเป็นโมดูล (Modularity) และความสะดวกในการบำรุงรักษา วัตถุประสงค์หลักของระบบคือการวิเคราะห์ข้อมูลพฤติกรรมและคุณลักษณะของผู้ใช้และสถานที่ เพื่อสร้างและนำเสนอรายการสถานที่แนะนำ (Recommendations) ที่มีความเกี่ยวข้องและตรงกับรสนิยมของผู้ใช้แต่ละราย (Personalization)

### 1.2 สถาปัตยกรรมเชิงโมดูล (Modular Architecture)
ระบบถูกแบ่งออกเป็นโมดูลย่อยที่มีหน้าที่รับผิดชอบชัดเจน:
*   **`engine.py`**: เป็น API หลัก (Facade) สำหรับแอปพลิเคชันภายนอก (เช่น `views.py`) เรียกใช้งาน ทำหน้าที่ประสานงานระหว่างโมดูลต่างๆ
*   **`data_utils.py`**: รับผิดชอบการโหลด, ทำความสะอาด, และเตรียมข้อมูลทั้งหมดจากฐานข้อมูล
*   **`popularity_based.py`**: ตรรกะสำหรับโมเดลแนะนำตามความนิยม
*   **`content_based.py`**: ตรรกะสำหรับโมเดล Content-Based Filtering
*   **`user_based.py`**: ตรรกะสำหรับโมเดล User-Based Collaborative Filtering
*   **`hybrid.py`**: ตรรกะในการผสมผสานผลลัพธ์จากทั้ง 3 โมเดล
*   **`cache_management.py` & `cache_keys.py`**: จัดการเรื่องการแคชและคีย์ทั้งหมด
*   **`signals.py`**: กำหนด Signal Handlers ที่คอยดักจับการเปลี่ยนแปลงของข้อมูลใน Model เพื่อ Trigger Task ต่างๆ
*   **`tasks.py`**: Celery tasks สำหรับการประมวลผลเบื้องหลัง (Background processing)

---

## 2. การจัดการข้อมูล (`data_utils.py`)

### 2.1 แหล่งข้อมูล
ข้อมูลดิบถูกดึงมาจาก Django Models ต่อไปนี้:
*   `Place`: `id`, `place_name`, `category`, `location`, `description`, `average_rating`, `price_range`, `total_reviews`, `visit_count`
*   `CustomUser`: `id`, `gender`, `date_of_birth`
*   `Review`: `user_id`, `place_id`, `rating`
*   `PlaceLike`: `user_id`, `place_id`
*   `UserActivity`: `user_id`, `object_id` (สำหรับ `content_type='place'` และ `activity_type` ที่เป็น `view` หรือ `share`)

### 2.2 การรวบรวมและทำความสะอาด (`load_and_clean_all_data`)
ฟังก์ชันนี้เป็นหัวใจของการเตรียมข้อมูล:
1.  **โหลดข้อมูล:** ดึงข้อมูลจากโมเดลต่างๆ มาสร้างเป็น `DataFrame` ของ Pandas
2.  **ทำความสะอาด:** จัดการค่าว่าง (NaN Handling) และแปลงประเภทข้อมูลให้ถูกต้อง
3.  **แคช:** `DataFrame` ที่ผ่านการประมวลผลแล้ว (ในรูปแบบ Dictionary ที่มี `places_df`, `users_df` ฯลฯ) จะถูกแคชไว้ใน Redis ภายใต้คีย์ `cache_keys.CLEANED_DATA_KEY` (ปัจจุบันคือ `'cleaned_data_all_v4'`) โดยมี Timeout ตาม `GLOBAL_CACHE_TIMEOUT` (21600 วินาที)

---

## 3. โมเดลที่ 1: Popularity-Based Filtering (`popularity_based.py`)

### 3.1 หลักการ
เป็นโมเดลพื้นฐานที่ไม่ซับซ้อน (Baseline) ทำหน้าที่จัดอันดับสถานที่ตาม "คะแนนความนิยม" เหมาะสำหรับผู้ใช้ใหม่ (Cold Start) หรือเป็น Fallback กรณีที่โมเดลอื่นทำงานไม่ได้

### 3.2 การคำนวณคะแนน (`get_popularity_based_recommendations`)
1.  **รวบรวมเมตริก:** ดึงข้อมูล `average_rating`, `total_reviews`, `visit_count` จาก `places_df` และคำนวณ `likes_count` และ `shares_count` จาก `likes_df` และ `shares_df`
2.  **Normalization:** ใช้ `MinMaxScaler` ของ Scikit-learn เพื่อปรับมาตราส่วนของแต่ละเมตริกให้อยู่ในช่วง 0 ถึง 1 เพื่อป้องกันไม่ให้เมตริกที่มีค่าสูง (เช่น `visit_count`) มีอิทธิพลมากกว่าเมตริกอื่น
3.  **คำนวณคะแนนถ่วงน้ำหนัก:** นำเมตริกที่ปรับแล้วมาคูณกับน้ำหนักที่กำหนดไว้ใน `settings.py` (`RECOMMENDATION_SETTINGS['POPULARITY_WEIGHTS']`) แล้วรวมกันเป็น `popularity_score` สุดท้าย
    *   **Default Weights:** `{'rating': 0.3, 'reviews': 0.2, 'visits': 0.1, 'likes': 0.2, 'shares': 0.2}`
4.  **แคช:** ผลลัพธ์การจัดอันดับ (list of `place_id`) จะถูกแคชไว้ภายใต้คีย์ `cache_keys.POPULARITY_RECS_KEY`

### 3.3 การแคช (Caching)
*   **กลยุทธ์:** โมเดลนี้ใช้กลยุทธ์ Cache-Aside แบบง่ายๆ
*   **สิ่งที่แคช:** รายการของ `place_id` ทั้งหมดที่เรียงตาม `popularity_score`
*   **คีย์:** `cache_keys.POPULARITY_RECS_KEY` (ค่าปัจจุบัน: `'popularity_recs_v1'`)
*   **การทำงาน:** ก่อนการคำนวณคะแนน ฟังก์ชัน `get_popularity_based_recommendations` จะตรวจสอบแคชก่อนเสมอ หากมีข้อมูลในแคชอยู่แล้วก็จะส่งคืนค่านั้นทันที หากไม่มีก็จะคำนวณใหม่ทั้งหมดแล้วจึงเก็บผลลัพธ์ลงในแคชก่อนส่งคืน

---

## 4. โมเดลที่ 2: Content-Based Filtering (`content_based.py`)

### 4.1 การสร้างโปรไฟล์ไอเท็ม (`_create_item_profiles`)
สร้างเวกเตอร์ตัวเลข (Item Profile) ที่แทนคุณลักษณะของสถานที่แต่ละแห่ง ประกอบด้วย:
1.  **Text Features:**
    *   **Preprocessing (`preprocess_thai_text`):** ทำความสะอาด `Place.description` โดย: 1) `normalize()` จาก `pythainlp`, 2) ลบอักขระที่ไม่ใช่ภาษาไทย, 3) ตัดคำด้วย `word_tokenize` (engine `newmm`), 4) ลบ Stopwords
    *   **Vectorization:** ใช้โมเดล `Word2Vec` ที่โหลดผ่าน `pythainlp.word_vector` เพื่อแปลงรายการโทเค็นเป็น Document Vector ขนาด 300 มิติ ด้วยการหาค่าเฉลี่ยของเวกเตอร์คำศัพท์
2.  **Categorical Features:**
    *   ใช้ `OneHotEncoder` เพื่อแปลงฟีเจอร์ `category`, `location`, `price_range` เป็น Sparse Matrix
3.  **Numerical & Demographic Features:**
    *   ใช้ค่า `average_rating`
    *   **Demographic Aggregation:** คำนวณค่าเฉลี่ยอายุ (`mean_age`) และการกระจายตัวของเพศ (`gender distribution`) ของผู้ใช้ทั้งหมดที่เคยมีปฏิสัมพันธ์กับสถานที่นั้นๆ เพื่อนำมาเป็นคุณลักษณะของสถานที่

### 4.2 การสร้างโปรไฟล์ผู้ใช้ (`_create_weighted_user_profile`)
โปรไฟล์ของผู้ใช้ถูกสร้างจาก "ค่าเฉลี่ยถ่วงน้ำหนักของโปรไฟล์ไอเท็ม" ที่ผู้ใช้เคยมีปฏิสัมพันธ์ด้วย น้ำหนักมาจากคะแนนใน `user_item_matrix` ซึ่งสะท้อน "รสนิยม" ของผู้ใช้

### 4.3 การคำนวณความคล้ายคลึง (`get_content_based_recommendations`)
1.  **Scaling:** ข้อมูลโปรไฟล์ไอเท็มทั้งหมดจะถูกปรับมาตราส่วนด้วย `StandardScaler`
2.  **Similarity:** คำนวณ `cosine_similarity` ระหว่างโปรไฟล์ผู้ใช้ (ที่ถูก scale) กับเมทริกซ์โปรไฟล์ไอเท็ม (ที่ถูก scale) เพื่อหาไอเท็มที่คล้ายกับรสนิยมผู้ใช้มากที่สุด

### 4.4 การแคช (Caching)
โมเดลนี้มีการใช้แคชใน 2 ส่วนหลักเพื่อเพิ่มประสิทธิภาพ:
1.  **แคชโปรไฟล์ไอเท็มที่ปรับมาตราส่วนแล้ว (Scaled Item Profiles):**
    *   **สิ่งที่แคช:** `DataFrame` ของโปรไฟล์ไอเท็มทั้งหมดหลังจากผ่าน `StandardScaler` แล้ว
    *   **คีย์:** `cache_keys.SCALED_PROFILES_KEY` (ค่าปัจจุบัน: `'scaled_item_profiles_v3'`)
    *   **กลยุทธ์:** เนื่องจากข้อมูลนี้มีขนาดใหญ่และใช้คำนวณสูง จึงถูกป้องกันด้วยตรรกะ **Build Lock** เพื่อป้องกันปัญหา Cache Stampede 
2.  **แคชสถานที่ที่คล้ายกัน (Similar Places):**
    *   **สิ่งที่แคช:** รายการ `place_id` ของสถานที่ที่คล้ายกับสถานที่ที่กำหนด
    *   **คีย์:** `cache_keys.place_similar_key(place_id)` (เช่น `'similar_to:123_v1'`)
    *   **กลยุทธ์:** ใช้ Cache-Aside แบบง่ายๆ ในฟังก์ชัน `get_similar_places`

---

## 5. โมเดลที่ 3: User-Based Collaborative Filtering (`user_based.py`)

### 5.1 หลักการ
หาผู้ใช้ที่มีความคล้ายคลึงกัน (Neighbors) โดยดูจากประวัติการให้คะแนนไอเท็มที่ผ่านมา แล้วแนะนำไอเท็มที่ผู้ใช้คล้ายๆ กันชอบแต่ผู้ใช้คนปัจจุบันยังไม่เคยมีปฏิสัมพันธ์ด้วย

### 5.2 การสร้าง User-Item Matrix (`_rebuild_user_similarity_matrix`)
1.  **รวบรวมปฏิสัมพันธ์:** ดึงข้อมูลการให้คะแนน (Review), การกดไลค์ (Like),การกดแชร์(share), และการเข้าชม (View) มาแปลงเป็น "คะแนนปฏิสัมพันธ์" โดยใช้ค่าน้ำหนักจาก `settings.py`:
    *   Review: `rating / 5.0`
    *   Like: `LIKE_WEIGHT` (default: 0.6)
    *   View: `VISIT_WEIGHT` (default: 0.3)
    SHARE: `SHARE_WEIGHT`(default: 0.7)
2.  **สร้าง Matrix:** สร้าง `DataFrame` (`user_item_df`) ที่มี `user_id` เป็นแถว, `place_id` เป็นคอลัมน์, และค่าในตารางเป็นผลรวมของคะแนนปฏิสัมพันธ์

### 5.3 การคำนวณความคล้ายคลึงของผู้ใช้
1.  **Mean-Centering:** ปรับค่าในเมทริกซ์โดยการลบค่าเฉลี่ยของแต่ละผู้ใช้ (`user_means`) เพื่อลดอคติในการให้คะแนน
2.  **Cosine Similarity:** คำนวณความคล้ายคลึงระหว่างผู้ใช้ทุกคนจากเมทริกซ์ที่ปรับค่าแล้ว (`user_item_df_centered`) เพื่อสร้าง `user_similarity_df`
3.  **Memory Efficiency:** กระบวนการทั้งหมดถูกออกแบบให้ **ประหยัดหน่วยความจำ** โดยใช้ `chunked_iterator` เพื่อประมวลผลข้อมูลเป็นส่วนๆ (chunk size: 2000) แทนการโหลดทั้งหมดเข้า RAM ในครั้งเดียว

### 5.4 การสร้างคำแนะนำ (`get_user_based_recommendations`)
1.  **หา Neighbors:** ค้นหาผู้ใช้ที่คล้ายที่สุด `k` คน (Top-K Neighbors) จาก `user_similarity_df` โดย `k` จะมีค่าอย่างน้อย 10 หรือ 10% ของจำนวนผู้ใช้ทั้งหมด
2.  **คำนวณคะแนน:** คำนวณคะแนนที่คาดว่าผู้ใช้จะให้สถานที่แต่ละแห่ง โดยใช้ค่าเฉลี่ยถ่วงน้ำหนักของคะแนนที่ Neighbors ให้กับสถานที่นั้นๆ
3.  **กรองและจัดอันดับ:** กรองสถานที่ที่ผู้ใช้เคยมีปฏิสัมพันธ์แล้วออกไป และจัดเรียงตามคะแนนที่คำนวณได้

### 5.5 การแคช (Caching)
*   **สิ่งที่แคช:** ข้อมูลที่จำเป็นสำหรับการคำนวณทั้งหมดของโมเดลนี้จะถูกเก็บไว้ในอ็อบเจกต์ Dictionary เดียว ซึ่งประกอบด้วย:
    1.  `similarity_matrix`: `DataFrame` ของ User-User Similarity
    2.  `user_item_matrix`: `DataFrame` ของ User-Item Interactions
    3.  `all_interactions`: `DataFrame` ของปฏิสัมพันธ์ทั้งหมดก่อน unstack
*   **คีย์:** `cache_keys.USER_COLLABORATIVE_FILTERING_DATA_KEY` (ค่าปัจจุบัน: `'user_collaborative_filtering_data_v1'`)
*   **กลยุทธ์:** เนื่องจากข้อมูลชุดนี้เป็นทรัพยากรที่มีจำนวนมากที่สุดในการคำนวณและมีการใช้งานร่วมกันทุกคน การเข้าถึงข้อมูลนี้จึงถูกควบคุมด้วยตรรกะ **Build Lock** ที่เข้มงวดที่สุดในฟังก์ชัน `get_user_collaborative_filtering_data` เพื่อป้องกัน Cache Stampede และรับประกันเสถียรภาพของระบบ
*   **เหตุผลที่แคชข้อมูลกลาง:** ระบบเลือกที่จะแคช "ข้อมูลกลาง" (เมทริกซ์ต่างๆ) แทนที่จะเป็น "ผลลัพธ์สุดท้าย" (รายการแนะนำ) เพราะการสร้างเมทริกซ์นั้นใช้เวลาคำนวณสูงมาก ในขณะที่การนำเมทริกซ์ไปใช้คำนวณหา 10 อันดับสุดท้ายนั้นรวดเร็วและยืดหยุ่นกว่ามาก ทำให้สามารถขอรายการแนะนำสำหรับผู้ใช้คนใดก็ได้ หรือขอจำนวนเท่าใดก็ได้ โดยไม่ต้องคำนวณใหม่

---

## 6. การผสานโมเดل (`hybrid.py`)

### 6.1 Dynamic Weighting (`get_dynamic_weights`)
ระบบจะปรับน้ำหนักระหว่าง 3 โมเดล (User-Based, Content-Based, Popularity) แบบไดนามิกตามจำนวนกิจกรรม (`total_interactions`) ของผู้ใช้:
*   **Low Interactions ( <5 ):** `(UB: 0.1, CB: 0.3, Pop: 0.6)` - เน้น `Content-Based` และ `Popularity`
*   **Medium Interactions ( 5-30 ):** `(UB: 0.4, CB: 0.5, Pop: 0.1)` - เพิ่มน้ำหนักให้ `User-Based`
*   **High Interactions ( >30 ):** `(UB: 0.6, CB: 0.4, Pop: 0.0)` - ให้น้ำหนักกับ `User-Based` มากที่สุด

### 6.2 การรวมคะแนน (`compute_hybrid_scores`)
1.  **ดึงผลลัพธ์:** รับรายการแนะนำจากทั้ง 3 โมเดล
2.  **ปรับน้ำหนัก:** หากโมเดลใดไม่คืนผลลัพธ์ ระบบจะปรับน้ำหนักของโมเดลที่เหลือโดยอัตโนมัติเพื่อให้น้ำหนักรวมยังคงเป็น 1
3.  **แปลงอันดับเป็นคะแนน:** ใช้วิธี Exponential Decay (`score = DECAY_ALPHA ** rank` โดย `DECAY_ALPHA`=0.99) เพื่อให้คะแนนกับอันดับต้นๆ สูงกว่าอันดับท้ายๆ
4.  **Normalization:** ปรับคะแนนของแต่ละโมเดลให้อยู่ในสเกลเดียวกัน (ผลรวมเป็น 1)
5.  **รวมคะแนน:** รวมคะแนนจากทั้งสามโมเดลโดยใช้น้ำหนักไดนามิกที่ปรับแล้ว

---

## 7. การให้บริการและการประมวลผลเบื้องหลัง

### 7.1 Serving Layer (`engine.py`)
`RecommendationEngine` เป็น Singleton instance ที่ทำหน้าที่เป็น API หลัก:
*   `get_hybrid_recommendations()`: เป็นเมธอดที่ `views.py` เรียกใช้เพื่อขอคำแนะนำส่วนบุคคล ที่สำคัญคือเมธอดนี้จะ **รวมคะแนนจาก Batch Layer และ Speed Layer เข้าด้วยกัน** ก่อนส่งผลลัพธ์สุดท้าย
*   `get_similar_places()`: เป็นเมธอดที่ `views.py` เรียกใช้ในหน้ารายละเอียดสถานที่

### 7.2 Batch Layer (`tasks.py`)
*   `generate_batch_recommendations`: Task ที่ถูกเรียกเป็นระยะๆ (ทุก 6 ชั่วโมง) เพื่อคำนวณ Hybrid Scores ล่วงหน้าสำหรับผู้ใช้ที่ Active (last_login ภายใน 7 วัน) และเก็บผลลัพธ์ลง Cache

### 7.3 Speed Layer (`signals.py` และ `tasks.py`)
*   **Triggers (`signals.py`):** ใช้ `post_save` และ `post_delete` signal บนโมเดล `Review`, `PlaceLike`, และ `UserActivity` เพื่อดักจับการเปลี่ยนแปลง
*   **Task (`process_realtime_interaction`):** เมื่อมี Signal เกิดขึ้น Task นี้จะถูกเรียกใช้ทันทีเพื่อ:
    1.  ค้นหาสถานที่ที่คล้ายกับสถานที่ที่เพิ่งมีปฏิสัมพันธ์
    2.  เพิ่ม/ลด "Boost Score" เล็กน้อย (10% ของคะแนนปฏิสัมพันธ์) ให้กับสถานที่ที่คล้ายกันเหล่านั้นใน Redis Hash
    3.  คะแนน Boost นี้จะถูกนำไปรวมกับคะแนนจาก Batch Layer ใน `get_hybrid_recommendations`

---

## 8. การดำเนินงานและการประเมินผล

### 8.1 Management Commands
*   `python manage.py train_word2vec_model`: ใช้สำหรับฝึกโมเดล Word2Vec ใหม่จากข้อมูล `Place.description` ล่าสุดของคุณเอง(ตอนนี้ ใช้Vectorของระบบไม่ได้เทรนเอง)
*   `python manage.py evaluate_recommendation_system`: ใช้สำหรับรันสคริปต์ประเมินผลโมเดลด้วยเมตริกต่างๆ

### 8.2 Evaluation Metrics (`evaluation.py`)
ระบบมีฟังก์ชันสำหรับวัดประสิทธิภาพของโมเดลในด้านต่างๆ เช่น:
*   **Precision@k & Recall@k:** วัดความแม่นยำและความสามารถในการค้นหา
*   **nDCG@k:** วัดคุณภาพของการจัดอันดับ (Ranking)
*   **Diversity & Coverage:** วัดความหลากหลายของผลลัพธ์ที่แนะนำ
