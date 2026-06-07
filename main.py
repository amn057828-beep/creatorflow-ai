import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="SaaS Backend with Render PostgreSQL")

# جلب رابط قاعدة البيانات السري من متغيرات البيئة في رندر (Environment Variables)
# هذا يحمي بياناتك من التسريب ويجعل الربط تلقائياً
DATABASE_URL = os.getenv("DATABASE_URL", "postgres://user:password@host:port/dbname")

def get_db_connection():
    try:
        # الاتصال المباشر بقاعدة بيانات رندر
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print("فشل الاتصال بقاعدة البيانات:", e)
        return None

# دالة لتهيئة الجداول تلقائياً عند تشغيل السيرفر لأول مرة
@app.on_event("startup")
def startup_db_init():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        # إنشاء جدول المستخدمين الحقيقي داخل رندر
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users_profile (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                credits INT DEFAULT 50,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("تمت تهيئة قاعدة بيانات رندر بنجاح!")

class UserRegister(BaseModel):
    username: str
    email: str

# API حقيقي لتسجيل مستخدم جديد ومنحه 50 نقطة لتوليد الصور والأصوات
@app.post("/api/register/")
async def register_user(user: UserRegister):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="خادم قاعدة البيانات غير متاح حالياً")
    
    try:
        cursor = conn.cursor()
        # إدخال البيانات وحفظها في رندر
        cursor.execute(
            "INSERT INTO users_profile (username, email) VALUES (%s, %s) RETURNING *;",
            (user.username, user.email)
        )
        new_user = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success", "user": new_user, "message": "تم الحفظ في قاعدة بيانات رندر الموقتة بنجاح"}
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=400, detail="اسم المستخدم أو الإيميل مسجل مسبقاً")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
