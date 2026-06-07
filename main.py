import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import edge_tts

# استيراد كليبات MoviePy بالطريقة المتوافقة مع الإصدارات الحديثة والقديمة
from moviepy.video.VideoClip import ImageClip
from moviepy.audio.io.AudioFileClip import AudioFileClip

app = FastAPI(title="AI Content Creator SaaS - Live Backend")

# 1. تفعيل الـ CORS لتأمين اتصال واجهة الـ HTML بالسيرفر
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. إتاحة قراءة وتشغيل الملفات الثابتة (الصوت والفيديو) عبر المتصفح
app.mount("/static", StaticFiles(directory="."), name="static")

# رابط قاعدة البيانات والـ API Key الخاص بـ SiliconFlow
DATABASE_URL = "postgresql://tayyibat_db_user:qE1UqVkJpOnk8gvcCftPykiQc2IeU3LN@dpg-d8ipe4ernols73c06spg-a.ohio-postgres.render.com/tayyibat_db"
SILICONFLOW_API_KEY = os.getenv("SILICON_KEY", "sk-ytqtkfauygoxfdrlvkbatjetpuxbdgogvebbolxdvgsbvdll")


# دالة الاتصال بقاعدة بيانات رندر
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print("خطأ في الاتصال بقاعدة البيانات:", e)
        return None


# تهيئة الجداول تلقائياً عند بدء تشغيل السيرفر
@app.on_event("startup")
def startup_db_init():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users_profile (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                credits INT DEFAULT 50,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS generated_content (
                id SERIAL PRIMARY KEY,
                user_email TEXT NOT NULL,
                content_type TEXT NOT NULL,
                prompt TEXT NOT NULL,
                output_url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("🚀 تم الاتصال بقاعدة البيانات وتهيئة الجداول بنجاح!")


# النماذج البرمجية لاستقبال الطلبات (Data Models)
class UserRegister(BaseModel):
    username: str
    email: str


class ContentRequest(BaseModel):
    email: str
    prompt: str
    voice_name: str = "ar-EG-ShakirNeural"


# دالة مساعدة لترجمة السكريبت إلى الإنجليزية فورياً لضمان استجابة موديل FLUX الاحترافية
def translate_to_english(text):
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=ar&tl=en&dt=t&q={requests.utils.quote(text)}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()[0][0][0]
    except Exception:
        pass
    return "cinematic fantasy landscape, ancient alchemy lab, masterpiece, 4k"


# دالة تحميل الصورة الفنية المحسنة والمؤمنة ضد انقطاع الخدمة أو انتهاء الرصيد
def download_ai_image(prompt, filename):
    url = "https://api.siliconflow.cn/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }

    english_prompt = translate_to_english(prompt)

    payload = {
        "model": "black-forest-labs/FLUX.1-schnell",
        "prompt": f"{english_prompt}, cinematic lighting, masterpiece, 4k, hyper-detailed",
        "image_size": "768x1344",
    }
    
    # المحاولة الأولى: طلب الصورة من SiliconFlow بمهلة ممتدة لـ 40 ثانية كاملة
    try:
        print("🎨 جاري طلب الصورة الفنية من سيرفر SiliconFlow...")
        response = requests.post(url, json=payload, headers=headers, timeout=40)
        
        if response.status_code == 200:
            img_url = response.json()["data"][0]["url"]
            img_data = requests.get(img_url, timeout=30).content
            with open(filename, "wb") as handler:
                handler.write(img_data)
            print("✅ تم تحميل الصورة الأصلية من الموديل بنجاح بنسبة 100%")
            return True
        else:
            print(f"⚠️ سيرفر SiliconFlow رد بكود خطأ: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ خطأ شبكة أو انتهاء مهلة أثناء طلب الصورة: {e}")
        
    # خطة الإنقاذ البديلة (Fallback): سحب لوحة سينمائية مذهلة ومناسبة لجو المنصة لضمان عدم تعطل المونتاج
    try:
        print("🔮 تفعيل خطة الإنقاذ البديلة: جاري معالجة صورة سينمائية جاهزة وعالية الجودة...")
        fallback_image_url = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=768&auto=format&fit=crop"
        img_data = requests.get(fallback_image_url, timeout=15).content
        with open(filename, "wb") as handler:
            handler.write(img_data)
        return True
    except Exception as fallback_error:
        print(f"فشلت خطة الإنقاذ البديلة أيضاً: {fallback_error}")
        
    return False


# --- 1. API تسجيل مستخدم جديد ---
@app.post("/api/register/")
async def register_user(user: UserRegister):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="قاعدة البيانات غير متصلة")
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users_profile (username, email) VALUES (%s, %s) RETURNING *;",
            (user.username, user.email),
        )
        new_user = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        return {
            "status": "success",
            "user": new_user,
            "message": "تم حفظ المستخدم بنجاح!",
        }
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=400, detail="المستخدم مسجل بالفعل")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- 2. API توليد الصوت وحفظه في السيرفر ---
@app.post("/api/generate-audio/")
async def generate_audio(request: ContentRequest):
    file_id = request.email.split("@")[0]
    output_filename = f"audio_{file_id}.mp3"
    try:
        communicate = edge_tts.Communicate(request.prompt, request.voice_name)
        await communicate.save(output_filename)

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO generated_content (user_email, content_type, prompt, output_url) VALUES (%s, %s, %s, %s);",
                (
                    request.email,
                    "audio",
                    request.prompt,
                    f"static/{output_filename}",
                ),
            )
            conn.commit()
            cursor.close()
            conn.close()

        return {
            "status": "success",
            "file_name": f"static/{output_filename}",
            "message": "تم توليد الصوت بنجاح",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- 3. API توليد الصور وعرض رابطها المباشر من الموديل ---
@app.post("/api/generate-image/")
async def generate_image(request: ContentRequest):
    url = "https://api.siliconflow.cn/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }

    english_prompt = translate_to_english(request.prompt)

    payload = {
        "model": "black-forest-labs/FLUX.1-schnell",
        "prompt": f"{english_prompt}, cinematic lighting, 4k",
        "image_size": "768x1344",
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            raise HTTPException(
                status_code=500, detail="فشل سيرفر SiliconFlow، تحقق من الـ Token"
            )

        result = response.json()
        image_url = result["data"][0]["url"]

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO generated_content (user_email, content_type, prompt, output_url) VALUES (%s, %s, %s, %s);",
                (request.email, "image", request.prompt, image_url),
            )
            conn.commit()
            cursor.close()
            conn.close()

        return {"status": "success", "image_url": image_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- 4. API المونتاج الآلي وتوليد الفيديو المكتمل والمنسق ---
@app.post("/api/generate-video/")
async def generate_video(request: ContentRequest):
    file_id = request.email.split("@")[0]
    temp_audio = f"temp_audio_{file_id}.mp3"
    temp_image = f"temp_image_{file_id}.png"
    output_video = f"video_{file_id}.mp4"

    try:
        # أ. إنتاج المسار الصوتي
        communicate = edge_tts.Communicate(request.prompt, request.voice_name)
        await communicate.save(temp_audio)

        # ب. إنتاج وحفظ اللوحة الفنية الخلفية للسيرفر (مزودة بخطة الطوارئ لحماية التوليد)
        if not download_ai_image(request.prompt, temp_image):
            raise HTTPException(
                status_code=500,
                detail="فشل نظام معالجة الصور بالكامل، تعذر استرداد أصول مرئية",
            )

        # ج. تنفيذ عمليات المونتاج الصوتي وتركيب المشهد بأسلوب متوافق مع رندر
        audio_clip = AudioFileClip(temp_audio)
        video_duration = audio_clip.duration

        video_clip = ImageClip(temp_image).set_duration(video_duration)
        final_video = video_clip.set_audio(audio_clip)

        # رندر وتصدير ملف الـ mp4 بجودة معالجة ممتازة وخفيفة لضمان ثبات بيئة الاستضافة
        final_video.write_videofile(
            output_video, fps=24, codec="libx264", audio_codec="aac", logger=None
        )

        # تحرير الذاكرة العشوائية فوراً لحماية الرام المجانية في رندر
        audio_clip.close()
        video_clip.close()
        final_video.close()

        if os.path.exists(temp_audio):
            os.remove(temp_audio)
        if os.path.exists(temp_image):
            os.remove(temp_image)

        video_web_path = f"static/{output_video}"

        # حفظ حركة الإنتاج في الداتابيز
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO generated_content (user_email, content_type, prompt, output_url) VALUES (%s, %s, %s, %s);",
                (request.email, "video", request.prompt, video_web_path),
            )
            conn.commit()
            cursor.close()
            conn.close()

        return {
            "status": "success",
            "video_url": video_web_path,
            "message": "تم إنتاج فيديو الخيمياء المتكامل بنجاح!",
        }

    except Exception as e:
        if os.path.exists(temp_audio):
            os.remove(temp_audio)
        if os.path.exists(temp_image):
            os.remove(temp_image)
        raise HTTPException(
            status_code=500, detail=f"خطأ أثناء معالجة المونتاج: {str(e)}"
        )
