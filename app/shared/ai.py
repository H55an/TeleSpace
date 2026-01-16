import requests
from . import config
import os

# مسار ملف قاعدة المعرفة
KNOWLEDGE_BASE_FILE = os.path.join(os.path.dirname(__file__), 'knowledge_base.md')

# قراءة محتوى قاعدة المعرفة مرة واحدة عند بدء التشغيل
try:
    with open(KNOWLEDGE_BASE_FILE, 'r', encoding='utf-8') as f:
        KNOWLEDGE_BASE_CONTENT = f.read()
except FileNotFoundError:
    KNOWLEDGE_BASE_CONTENT = "خطأ: ملف knowledge_base.md غير موجود."

def get_guide_response(question: str) -> str:
    """
    Sends a user's question along with the knowledge base to the AI.
    """
    if not config.OPENROUTER_API_KEY or config.OPENROUTER_API_KEY == "YOUR_OPENROUTER_API_KEY":
        return "⚠️ لم يتم تكوين مفتاح OpenRouter API. يرجى إضافته إلى ملف `config.py` أو متغيرات البيئة."

    if "خطأ" in KNOWLEDGE_BASE_CONTENT:
        return f"⚠️ لا يمكن الوصول إلى قاعدة المعرفة: {KNOWLEDGE_BASE_CONTENT}"

    system_prompt = """
أنت "مرشد TeleSpace الذكي". مهمتك هي الإجابة على أسئلة المستخدم حول كيفية استخدام بوت تليجرام "TeleSpace" بالاعتماد **فقط** على المعلومات المتوفرة في "قاعدة المعرفة" المرفقة. لا تخترع أي معلومات أو ميزات غير موجودة في النص. إذا كان السؤال غير مرتبط بوظائف البوت أو كانت الإجابة غير موجودة في قاعدة المعرفة، أجب بـ: 'عذرًا، ليس لدي معلومات حول هذا الموضوع. أنا متخصص فقط في الإجابة عن كيفية استخدام بوت TeleSpace.' كن دقيقًا ومباشرًا في إجاباتك.
"""

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "tngtech/deepseek-r1t2-chimera:free",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""قاعدة المعرفة:
---
{KNOWLEDGE_BASE_CONTENT}
---

سؤال المستخدم: {question}"""}
                ]
            }
        )
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        return data['choices'][0]['message']['content']

    except requests.exceptions.RequestException as e:
        print(f"Error calling OpenRouter API: {e}")
        # Check for specific 400 error to give a better message
        if e.response and e.response.status_code == 400:
            return "⚠️ حدث خطأ في الطلب إلى الـ API. قد يكون السبب هو اسم النموذج غير الصحيح أو أن حسابك لا يدعمه. يرجى مراجعة إعدادات OpenRouter."
        return f"⚠️ حدث خطأ أثناء الاتصال بـ OpenRouter API: {e}"
    except (KeyError, IndexError) as e:
        print(f"Error parsing OpenRouter API response: {e}")
        return "⚠️ حدث خطأ أثناء معالجة الرد من واجهة برمجة التطبيقات."
