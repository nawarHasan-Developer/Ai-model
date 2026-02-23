# -*- coding: utf-8 -*-
import pandas as pd
import google.generativeai as genai
import re
import os # هي أهم مكتبة مشان يشتغل على السيرفر

# --- 1. الإعدادات (نظام السيرفر) ---
# الكود بيسحب المفتاح من بيئة السيرفر أوتوماتيكياً
API_KEY = os.getenv("GOOGLE_API_KEY")

if API_KEY:
    genai.configure(api_key=API_KEY.strip(), transport='rest')
else:
    # هي الرسالة بتساعد المبرمج يعرف إذا نسي يضيف المفتاح بالسيرفر
    raise ValueError("GOOGLE_API_KEY not found in environment variables!")

def load_resources():
    try:
        # يفضل دائماً يكون الملف بنفس المجلد على السيرفر
        df = pd.read_excel('customs_global_brain.xlsx')
        df['band_clean'] = df['band_syria'].astype(str).str.replace(r'[^\d]', '', regex=True).str.strip().str.zfill(8)
        df['material_clean'] = df['material_clean'].astype(str).strip()
        return df
    except Exception as e:
        print(f"❌ Error loading Excel: {e}")
        return None

df_main = load_resources()

def get_customs_consultation(user_input):
    if df_main is None: return "⚠️ Database Error."
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # تحديد اللغة
        lang_resp = model.generate_content(f"Identify language for: '{user_input}'. Return ONLY language name.")
        lang = lang_resp.text.strip()

        # البرومت المعدل (القواعد السورية: باذنجان، علكة، بطاطا)
        prompt = (
            f"Rules: 1. 'علكة' = Chewing Gum (HS 170410). 2. 'بانجان'/'باذنجان' = Black Eggplant. "
            f"3. 'بطاطا' = Potatoes. Analyze: '{user_input}'. "
            f"Respond ONLY in {lang}. Provide top 3 HS6 codes. Format: [Category]: [HS6 Code]"
        )
        
        response = model.generate_content(prompt)
        if not response or not response.text: return "⚠️ AI Error."
        
        raw_lines = [line for line in response.text.strip().split('\n') if ':' in line]
        
        # ترجمة العناوين
        labels = model.generate_content(f"Translate to {lang}: 'Item Name','HS6','8-Digit','Description'. Return CSV only.").text.strip().split(',')
        l = [i.strip() for i in labels] if len(labels) >= 4 else ["Item", "HS6", "8-Digit", "Desc"]

        output = ""
        for line in raw_lines:
            # معالجة الكود والمطابقة مع الإكسل
            item_ai, hs_raw = line.rsplit(':', 1)
            hs6 = re.search(r'(\d{4,6})', hs_raw).group(1)[:6]
            matches = df_main[df_main['band_clean'].str.startswith(hs6)]
            
            if not matches.empty:
                row = matches.iloc[0]
                # وصف ذكي ومباشر
                desc = model.generate_content(f"Describe '{row['material_clean']}' for query '{user_input}' in {lang}. 1 direct sentence.").text.strip()
                output += f"🔸 {l[0]}: {item_ai}\n🌐 {l[1]}: {hs6}\n🇸🇾 {l[2]}: {row['band_clean']}\n📝 {l[3]}: {desc}\n────────────────\n"

        return output if output else "❌ No matches found."
    except Exception as e:
        return f"⚠️ System Error: {str(e)}"

# تشغيل يدوي للتجربة (أو استدعاء من قبل السيرفر)
if __name__ == "__main__":
    print("🚀 Across Mena Engine Running...")
    q = input("🔎 الصنف (عيسى): ")
    print(get_customs_consultation(q))