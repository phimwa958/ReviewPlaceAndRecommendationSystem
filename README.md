# Review Place & Recommendation System

โปรเจกต์นี้คือเว็บแอปพลิเคชันสำหรับรีวิวสถานที่ (ที่พัก, ร้านอาหาร, สถานที่ท่องเที่ยว) ที่มาพร้อมกับระบบแนะนำ (Recommendation System) อัจฉริยะที่สร้างขึ้นอย่างพิถีพิถันเพื่อมอบประสบการณ์ที่เป็นส่วนตัว (Personalized Experience) ให้กับผู้ใช้แต่ละคน

## ภาพรวมระบบ (System Overview)

โปรเจกต์นี้ประกอบด้วย 2 ระบบหลักที่ทำงานร่วมกัน:

**1. ระบบรีวิวและจัดการเนื้อหา (Review & Content Management System)**
เป็นแกนหลักของแอปพลิเคชัน สร้างขึ้นด้วย Django ทำหน้าที่จัดการข้อมูลและปฏิสัมพันธ์ของผู้ใช้ทั้งหมด ตั้งแต่ระบบสมาชิก (ลงทะเบียน, เข้าสู่ระบบ, โปรไฟล์), การสร้าง-อ่าน-ลบ-แก้ไข (CRUD) สำหรับสถานที่, รีวิว, และความคิดเห็น ไปจนถึงระบบจัดการสำหรับผู้ดูแลที่มาพร้อมแดชบอร์ดสำหรับวิเคราะห์ข้อมูล การออกแบบเน้นความเป็นโมดูลและง่ายต่อการบำรุงรักษา
> *อ่านรายละเอียดเชิงลึกของสถาปัตยกรรมส่วนนี้ได้ที่: [`system_overview.md`](./system_overview.md)*

**2. ระบบแนะนำสถานที่ (Recommendation System)**
เป็นระบบเบื้องหลังที่แยกออกมาเป็นแอปพลิเคชันของตัวเอง (`recommendations`) เพื่อความเป็นอิสระในการพัฒนาและดูแลรักษา ระบบนี้ใช้สถาปัตยกรรมแบบไฮบริดที่ผสมผสานโมเดล 3 รูปแบบ (User-Based, Content-Based, Popularity-Based) เข้าด้วยกันเพื่อสร้างคำแนะนำที่แม่นยำและตรงกับความสนใจของผู้ใช้แต่ละคนมากที่สุด ทำงานแบบเบื้องหลัง (Asynchronously) โดยใช้ Celery และ Redis เพื่อประสิทธิภาพสูงสุด
> *อ่านรายละเอียดเชิงลึกของสถาปัตยกรรมส่วนนี้ได้ที่: [`recommendation_system_definitive_guide.md`](./recommendation_system_definitive_guide.md)*

## ✨ คุณสมบัติหลัก (Key Features)

*   **ระบบสมาชิกที่สมบูรณ์:** ลงทะเบียน, เข้าสู่ระบบ, จัดการโปรไฟล์, และรีเซ็ตรหัสผ่าน
*   **การจัดการเนื้อหา (CRUD):** ผู้ใช้สามารถสร้าง, อ่าน, แก้ไข, และลบ **สถานที่**, **รีวิว**, และ **ความคิดเห็น** ได้อย่างเต็มรูปแบบ
*   **ระบบปฏิสัมพันธ์:** กดไลค์, แชร์ไปยังโซเชียลมีเดีย, และรายงานเนื้อหาที่ไม่เหมาะสม
*   **ระบบแนะนำแบบไฮบริด:**
    *   **Personalized Recommendations:** แนะนำสถานที่สำหรับคุณโดยเฉพาะในหน้าแรก
    *   **Similar Items:** แนะนำสถานที่ที่คล้ายกันในหน้ารายละเอียด
*   **การประมวลผลภาษาธรรมชาติ (NLP):** ใช้ `PyThaiNLP` และ `Gensim Word2Vec` เพื่อทำความเข้าใจเนื้อหาภาษาไทย
*   **แดชบอร์ดผู้ดูแล:** หน้าวิเคราะห์ข้อมูลกิจกรรมผู้ใช้แบบกราฟิกสำหรับผู้ดูแลระบบ

## 🛠️ Technology Stack (เทคโนโลยีที่ใช้)

*   **Backend:** Django
*   **Frontend:** HTML, CSS (Bootstrap, Tailwind CSS), JavaScript, Chart.js
*   **Database:** MySQL (or SQLite for manual fallback)
*   **Web Server:** Gunicorn (in Docker)
*   **Asynchronous Tasks:** Celery, Eventlet (for Windows compatibility)
*   **Caching & Message Broker:** Redis
*   **Containerization:** Docker, Docker Compose
*   **Data Science:** Pandas, NumPy, Scikit-learn, Gensim, PyThaiNLP

---

## 🚀 Getting Started (การติดตั้งและเริ่มต้นใช้งาน)

คุณสามารถเลือกระหว่างการติดตั้งโดยใช้ Docker Compose (แนะนำ) หรือการติดตั้งแบบ Manual ด้วย Virtual Environment

### Option 1: Docker Compose Setup (Recommended)

วิธีนี้เป็นวิธีที่แนะนำและง่ายที่สุดในการเริ่มต้นใช้งานโปรเจกต์ เพราะจะทำการตั้งค่าบริการทั้งหมด (Django, MySQL, Redis, Celery) ให้โดยอัตโนมัติ

**Prerequisites:**
*   Docker
*   Docker Compose

**ขั้นตอนการติดตั้ง:**

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd <repository-folder>
    ```

2.  **Create Environment File:**
    คัดลอกไฟล์ `.env.example` แล้วเปลี่ยนชื่อเป็น `.env` จากนั้นกรอกค่าที่จำเป็น เช่น `DJANGO_SECRET_KEY` และข้อมูลสำหรับ MySQL
    ```bash
    cp .env.example .env
    # Now, edit the .env file with your favorite editor
    # For example: nano .env
    ```

3.  **Build and Run Containers:**
    ใช้ Docker Compose เพื่อ build image และ start บริการทั้งหมดใน detached mode
    ```bash
    docker-compose up --build -d
    ```
    คำสั่งนี้อาจใช้เวลาสักครู่ในครั้งแรกที่รัน

4.  **Apply Database Migrations:**
    รันคำสั่ง `migrate` ภายใน container ของ `web`
    ```bash
    docker-compose exec web python manage.py migrate
    ```

5.  **Populate Initial Data (สำคัญ):**
    ดูหัวข้อ **"การลงข้อมูลเริ่มต้น"** ด้านล่าง

### Option 2: Manual Virtual Environment Setup

วิธีนี้เหมาะสำหรับผู้ที่ต้องการรันโปรเจกต์โดยตรงบนเครื่องของตนเองโดยไม่ใช้ Docker

**Prerequisites:**
*   Python 3.11+
*   Redis Server (ต้องติดตั้งและรันแยกต่างหาก)
*   MySQL Server (หรือสามารถใช้ SQLite fallback ได้)
*   System dependencies for `mysqlclient`:
    *   On Debian/Ubuntu: `sudo apt-get install build-essential default-libmysqlclient-dev`
    *   On macOS: `brew install mysql`

**ขั้นตอนการติดตั้ง:**

1.  **Clone repo and setup `.env` file:**
    ```bash
    git clone <your-repository-url>
    cd <repository-folder>
    cp .env.example .env
    # Edit .env file
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Apply database migrations:**
    ```bash
    python manage.py migrate
    ```

5.  **Run Django Development Server:**
    (ใน terminal แรก)
    ```bash
    python manage.py runserver
    ```

6.  **Run Celery Worker & Beat (ใน terminal ใหม่):**
    เปิด terminal ใหม่, activate virtual environment, และรันคำสั่ง:

    *   **สำหรับ macOS/Linux:**
        ```bash
        # Terminal 2: Worker
        celery -A review worker -l info

        # Terminal 3: Beat
        celery -A review beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
        ```
    *   **สำหรับ Windows (ข้อควรระวัง):**
        Celery ไม่รองรับ Windows อย่างเป็นทางการสำหรับ Production แต่สามารถรันในโหมด Development ได้โดยใช้ `eventlet` pool ซึ่งฉันได้เพิ่มไว้ใน `requirements.txt` แล้ว
        ```bash
        # Terminal 2: Worker on Windows
        celery -A review worker -l info -P eventlet

        # Terminal 3: Beat on Windows
        celery -A review beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
        ```

---

## 📥 Populating Initial Data (การลงข้อมูลเริ่มต้น)

หลังจากที่คุณทำการ `migrate` ฐานข้อมูลเรียบร้อยแล้ว ฐานข้อมูลของคุณจะยังว่างอยู่ คุณจำเป็นต้องรันสคริปต์เพื่อนำเข้าข้อมูลตัวอย่างจากไฟล์ Excel

**รันคำสั่งนี้เพียงครั้งเดียว:**

*   **สำหรับผู้ใช้ Docker Compose:**
    ```bash
    docker-compose exec web python "data/script python/import_from_excel.py"
    ```
*   **สำหรับผู้ใช้ Manual Setup:**
    ```bash
    python "data/script python/import_from_excel.py"
    ```

สคริปต์นี้จะทำการอ่านไฟล์ `.xlsx` จากไดเรกทอรี `data/data_traind` และนำเข้าข้อมูล Users, Places, Reviews, Likes, และอื่นๆ ทั้งหมดลงในฐานข้อมูล(หากต้องการใช้จริงในระบบของคุณเอง ส่วนนี้ไม่จำเป็นต้องใช้)

---

## ⚙️ Key Management Commands (คำสั่งที่สำคัญ)

*   **Train Word2Vec Model:**
    คำสั่งนี้ใช้สำหรับสร้างโมเดลภาษาจากข้อมูล `description` ของสถานที่ทั้งหมดของเว็บไซต์ของคุณ(ตอนนี้ ใช้Vectorของระบบไม่ได้เทรนเอง)
    *   Docker: `docker-compose exec web python manage.py train_word2vec_model`
    *   Manual: `python manage.py train_word2vec_model`

*   **Evaluate Recommendation System:**
    ใช้สำหรับประเมินประสิทธิภาพของระบบแนะนำด้วยเมตริกต่างๆ
    *   Docker: `docker-compose exec web python manage.py evaluate_recommendation_system`
    *   Manual: `python manage.py evaluate_recommendation_system`

---

## 🙌 Contributing (ร่วมเป็นส่วนหนึ่งกับฉัน)

ฉันยินดีต้อนรับทุกการสนับสนุน ไม่ว่าจะเป็นการรายงานบั๊ก การเสนอแนวคิดเพื่อปรับปรุงโปรเจกต์ หรือการส่ง Pull Request เพื่อช่วยให้โปรเจกต์นี้ดียิ่งขึ้น ร่วมสร้างโปรเจกต์ให้น่าสนุกและมีประโยชน์ไปด้วยกัน!

## 🙏 Acknowledgements (คำขอบคุณ)

ขอขอบคุณผู้มีส่วนร่วมทุกคน รวมถึงไลบรารี Open Source ที่ยอดเยี่ยมซึ่งทำให้โปรเจกต์นี้เป็นไปได้

## 📬 Contact (ติดต่อฉัน)

หากมีคำถามหรือข้อเสนอแนะ สามารถติดต่อได้ที่:  
- Email: pim2544varee@gmail.com
- GitHub: [phimwa958](https://github.com/phimwa958)  

หรือสร้าง issue บน GitHub เพื่อรายงานบั๊กรวมถึงเสนอไอเดียใหม่ ๆ
ได้เช่นกัน😊