# -*- coding: utf-8 -*-
import pandas as pd
import google.generativeai as genai
import re
import os

# --- 1. الإعدادات ---
API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=API_KEY.strip(), transport='rest')

def load_resources():
    try:
        df = pd.read_excel('customs_global_brain.xlsx')
        df['band_clean'] = df['band_syria'].astype(str).str.replace(r'[^\d]', '', regex=True).str.strip().str.zfill(8)
        df['material_clean'] = df['material_clean'].astype(str).str.strip()
        return df
    except Exception as e:
        print(f"❌ خطأ في تحميل الملف: {e}")
        return None

df_main = load_resources()

def get_customs_consultation(user_input):
    if df_main is None: return "⚠️ Database Error."

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # 1. كشف لغة الإدخال
        is_arabic = bool(re.search(r'[\u0600-\u06FF]', user_input))
        
        if is_arabic:
            target_lang = "Arabic"
            L = {'item': "الصنف", 'hs6': "البند السداسي", 'sy_band': "البند السوري", 'desc': "الوصف", 'rep': "التقرير الجمركي"}
        else:
            # كشف اللغة للأجانب (ألماني، إنجليزي...)
            detect_lang_prompt = f"What is the language of: '{user_input}'? Return only the language name."
            target_lang = model.generate_content(detect_lang_prompt).text.strip()
            L = {'item': "Category", 'hs6': "HS6 Code", 'sy_band': "Syrian Code", 'desc': "Description", 'rep': "Customs Report"}
            # تحديث العناوين للغة الهدف (بدون CSV)
            translate_labels = model.generate_content(f"Translate these words to {target_lang} individually: Item, HS6 Code, Syrian Code, Description, Customs Report. Return 5 lines.").text.strip().split('\n')
            if len(translate_labels) >= 5:
                L = {'item': translate_labels[0].strip(), 'hs6': translate_labels[1].strip(), 'sy_band': translate_labels[2].strip(), 'desc': translate_labels[3].strip(), 'rep': translate_labels[4].strip()}

        # 2. برومبت "خبير الجمارك" الصارم
        prompt = (
            f"You are a Syrian Customs Consultant. Item: '{user_input}'.\n"
            f"1. Identify 3-5 logical HS6 codes.\n"
            f"2. Your entire response must be in {target_lang}. \n"
            f"3. FORMAT: [Category Name]: [HS6 Code]. One per line. No intros."
        )
        
        response = model.generate_content(prompt)
        raw_lines = [line for line in response.text.strip().split('\n') if ':' in line]
        
        final_output = ""
        processed_hs6 = set()

        for line in raw_lines:
            parts = line.rsplit(':', 1)
            item_detail = parts[0].strip()
            hs_match = re.search(r'(\d{4,6})', parts[1])
            
            if hs_match:
                hs6 = hs_match.group(1)[:6]
                if hs6 in processed_hs6: continue
                processed_hs6.add(hs6)

                matches = df_main[df_main['band_clean'].str.startswith(hs6)]
                if matches.empty:
                    matches = df_main[df_main['band_clean'].str.startswith(hs6[:4])]

                if not matches.empty:
                    row = matches.iloc[0]
                    
                    # 3. معالجة الوصف (إذا عربي وعربي ما في داعي للترجمة، إذا ألماني منترجم)
                    if is_arabic:
                        desc_clean = row['material_clean']
                        # تلخيص الوصف العربي بذكاء
                        desc_clean = model.generate_content(f"لخص هذا الوصف الجمركي بجملة واحدة مفيدة: {desc_clean}").text.strip()
                    else:
                        desc_prompt = f"Translate and summarize this Arabic text into ONE short sentence in {target_lang}: '{row['material_clean']}'. Absolutely NO Arabic characters."
                        desc_clean = model.generate_content(desc_prompt).text.strip().replace('*', '')

                    final_output += f"🔸 {L['item']}: {item_detail}\n"
                    final_output += f"🌐 {L['hs6']}: {hs6}\n"
                    final_output += f"🇸🇾 {L['sy_band']}: {row['band_clean']}\n"
                    final_output += f"📝 {L['desc']}: {desc_clean}\n"
                    final_output += "────────────────\n"

        if not final_output: return f"❌ No results for '{user_input}'."
        return f"\n======= 📋 {L['rep']} =======\n🔎 {user_input}\n────────────────\n{final_output}===================================="

    except Exception as e:
        return f"⚠️ System Error: {str(e)}"

if __name__ == "__main__":
    print("🚀 محرك Across Mena v34 - نسخة الاستقرار الكامل.")
    while True:
        query = input("\n🔎 الصنف (عيسى): ").strip()
        if query.lower() in ['exit', 'خروج']: break
        if query: print(get_customs_consultation(query))