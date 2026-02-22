# -*- coding: utf-8 -*-
import pandas as pd
import google.generativeai as genai
import re

# --- 1. الإعدادات ---
GOOGLE_API_KEY = "AIzaSyAdjvA26WA4uujcuAcOa7sPo8A75LEvZtA".strip()
genai.configure(api_key=GOOGLE_API_KEY, transport='rest')

def load_resources():
    try:
        df = pd.read_excel('customs_global_brain (6) (1).xlsx')
        df['band_clean'] = df['band_syria'].astype(str).str.replace(r'[^\d]', '', regex=True).str.strip().str.zfill(8)
        df['material_clean'] = df['material_clean'].astype(str).str.strip()
        print("✅ قاعدة البيانات جاهزة")
        return df
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return None

df_main = load_resources()

def get_customs_consultation(user_input):
    if df_main is None:
        return "⚠️ الملف غير محمل."

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # 1. تحديد اللغة بدقة قبل أي شيء (خطوة قفل اللغة)
        lang_lock = model.generate_content(f"Identify the language or dialect of this text: '{user_input}'. Return ONLY the name of the language in English (e.g., French, Syrian Arabic, German).").text.strip()

        # 2. تحليل الصنف (النتائج فقط)
        prompt = (
            f"Analyze the item: '{user_input}'. Provide the top 3 relevant HS6 codes for PHYSICAL PRODUCTS. "
            f"CRITICAL: You must respond ONLY in {lang_lock}. "
            f"Format strictly: [Item Category]: [HS6 Code]"
        )
        response = model.generate_content(prompt)
        raw_lines = [line for line in response.text.strip().split('\n') if ':' in line]

        # 3. ترجمة العناوين للغة المقفولة
        label_prompt = (
            f"Translate these 4 labels to {lang_lock}: "
            f"'Item Name', 'HS6 Code', '8-Digit Code', 'Simplified Description'. "
            f"Return ONLY the labels separated by commas, no extra text."
        )
        labels_raw = model.generate_content(label_prompt).text.strip().split(',')
        l = [item.strip() for item in labels_raw] if len(labels_raw) >= 4 else ["Item", "HS6", "8-Digit", "Desc"]

        final_output = ""
        found_any = False
        processed_codes = set()

        for line in raw_lines:
            item_desc_ai, hs_code_raw = line.rsplit(':', 1)
            hs6_match = re.search(r'(\d{4,6})', hs_code_raw)
            
            if hs6_match:
                hs6 = hs6_match.group(1)[:6]
                if hs6 in processed_codes: continue
                processed_codes.add(hs6)

                matches = df_main[df_main['band_clean'].str.startswith(hs6)]
                if matches.empty:
                    matches = df_main[df_main['band_clean'].str.startswith(hs6[:4])]

                if not matches.empty:
                    found_any = True
                    row = matches.iloc[0] # نأخذ أول مطابقة
                    
                    # 4. توليد وصف ذكي باللغة المقفولة حصراً
                    desc_prompt = (
                        f"Describe this product: '{row['material_clean']}' using ONLY {lang_lock}. "
                        f"Context: The user is asking about '{user_input}'. "
                        f"Keep it short (1-2 sentences). Return ONLY the description."
                    )
                    translated_desc = model.generate_content(desc_prompt).text.strip()

                    final_output += f"🔸 {l[0]}: {item_desc_ai.strip()}\n"
                    final_output += f"🌐 {l[1]}: {hs6}\n"
                    final_output += f"🇸🇾 {l[2]}: {row['band_clean']}\n"
                    final_output += f"📝 {l[3]}: {translated_desc}\n"
                    final_output += "────────────────\n"

        if not found_any:
            err_msg = model.generate_content(f"Translate 'Item not found or non-physical' to {lang_lock}").text.strip()
            return f"❌ {err_msg}"

        return final_output

    except Exception as e:
        return f"⚠️ Error: {str(e)}"

def main():
    print("🚀 محرك Across Mena (نظام المرآة اللغوية)")
    while True:
        query = input("\n🔎 الصنف (عيسى): ").strip()
        if query.lower() in ['exit', 'خروج', 'quit']: break
        if query: print(get_customs_consultation(query))

if __name__ == "__main__":
    main()