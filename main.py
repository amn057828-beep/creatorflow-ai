import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import edge_tts

# استيراد مكتبات معالجة الفيديو برمجياً
from moviepy.editor import ImageClip, AudioFileClip
from PIL import Image

app = FastAPI(title="AI Video Producer SaaS - Live Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="."), name="static")

DATABASE_URL = "postgresql://tayyibat_db_user:qE1UqVkJpOnk8gvcCftPykiQc2IeU3LN@dpg-d8ipe4ernols73c06spg-a.ohio-postgres.render.com/tayyibat_db"
SILICONFLOW_API_KEY = os.getenv("SILICON_KEY", "sk-ytqtkfauygoxfdrlvkbatjetpuxbdgogvebbolxdvgsbvdll")

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print("خطأ داتابيز:", e)
        return None

@app.on_event("startup")
def startup_db_init():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
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

class ContentRequest(BaseModel):
    email: str
    prompt: str
    voice_name: str = "ar-EG-ShakirNeural"

# --- دالة مساعدة لتوليد الصورة وتحميلها مؤقتاً في السيرفر ---
def download_ai_image(prompt, filename):
    url = "https://api.siliconflow.cn/v1/images/generations"
    headers = {"Authorization": f"Bearer {SILICONFLOW_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "black-forest-labs/FLUX.1-schnell",
        "prompt": f"{prompt}, cinematic lighting, masterpiece, 4k",
        "image_size": "768x1344"
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        img_url = response.json()["data"][0]["url"]
        img_data = requests.get(img_url).content
        with open(filename, 'wb') as handler:
            handler.write(img_data)
        return True
    return False

# --- الـ API الأساسي لتوليد فيديو متكامل ومتحرك دقيقة بدقيقة ---
@app.post("/api/generate-video/")
async def generate_video(request: ContentRequest):
    file_id = request.email.split("@")[0]
    temp_audio = f"temp_audio_{file_id}.mp3"
    temp_image = f"temp_image_{file_id}.png"
    output_video = f"video_{file_id}.mp4"
    
    try:
        # 1. توليد الصوت وحفظه مؤقتاً
        communicate = edge_tts.Communicate(request.prompt, request.voice_name)
        await communicate.save(temp_audio)
        
        # 2. توليد الصورة من SiliconFlow وتحميلها للسيرفر
        if not download_ai_image(request.prompt, temp_image):
            raise HTTPException(status_code=500, detail="فشل توليد الصورة الفنية للمقطع")
            
        # 3. دمج المكونات برمجياً وصناعة حركات عبر MoviePy
        audio_clip = AudioFileClip(temp_audio)
        video_duration = audio_clip.duration # جعل مدة الفيديو متطابقة تماماً مع طول مدة الكلام الصوتي
        
        # إنشاء المقطع المرئي وتحديد مدته
        image_clip = ImageClip(temp_image).set_duration(video_duration)
        
        # إضافة حركة زووم ودوران خفيفة (Pan & Zoom effect) لجعل الفيديو نابضاً بالحياة ومتحركاً
        # تحريك الصورة بمعدل تغير طفيف يعتمد على الوقت t
        video_clip = image_clip.resize(lambda t: 1 + 0.04 * t) # تكبير تدريجي سينمائي بمقدار 4% كل ثانية
        
        # دمج الصوت المولد مع الصورة المتحركة
        final_video = video_clip.set_audio(audio_clip)
        
        # تصدير الفيديو النهائي بجودة عالية وسرعة معالجة مناسبة لسيرفر رندر
        final_video.write_videofile(
            output_video, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac",
            logger=None # إخفاء اللوغز لتسريع الإنتاج
        )
        
        # إغلاق الكليبات لتحرير مساحة الذاكرة (RAM) في السيرفر المجاني
        audio_clip.close()
        video_clip.close()
        final_video.close()
        
        # تنظيف الملفات المؤقتة
        if os.path.exists(temp_audio): os.remove(temp_audio)
        if os.path.exists(temp_image): os.remove(temp_image)
        
        # 4. حفظ رابط الفيديو النهائي في قاعدة بيانات رندر
        video_web_path = f"static/{output_video}"
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO generated_content (user_email, content_type, prompt, output_url) VALUES (%s, %s, %s, %s);",
                (request.email, "video", request.prompt, video_web_path)
            )
            conn.commit()
            cursor.close()
            conn.close()
            
        return {
            "status": "success",
            "video_url": video_web_path,
            "message": "🔮 تهانينا! تم إنتاج الفيديو السينمائي المتكامل بنجاح"
        }
        
    except Exception as e:
        # تأمين حذف الملفات إذا حدث خطأ لمنع امتلاء السيرفر
        if os.path.exists(temp_audio): os.remove(temp_audio)
        if os.path.exists(temp_image): os.remove(temp_image)
        raise HTTPException(status_code=500, detail=str(e))
