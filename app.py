# -*- coding: utf-8 -*-
import pandas as pd
import google.generativeai as genai
import re
import streamlit as st

# --- 1. الإعدادات ---
st.set_page_config(page_title="Across Mena - HS Code System", page_icon="🇸🇾", layout="centered")

import os

# قراءة المفتاح من Secrets (على السيرفر) أو من متغيرات البيئة (محلياً)
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"].strip()
except Exception:
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "").strip()

if not GOOGLE_API_KEY:
    st.error("⚠️ مفتاح API غير موجود. يرجى إضافة GOOGLE_API_KEY في إعدادات Secrets.")
    st.stop()
genai.configure(api_key=GOOGLE_API_KEY, transport='rest')

@st.cache_data
def load_resources():
    try:
        df = pd.read_excel('customs_global_brain.xlsx')
        df['band_clean'] = df['band_syria'].astype(str).str.replace(r'[^\d]', '', regex=True).str.strip().str.zfill(8)
        df['material_clean'] = df['material_clean'].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"❌ خطأ في تحميل الملف: {e}")
        return None

df_main = load_resources()

def get_customs_consultation(user_input):
    if df_main is None:
        return "⚠️ الملف غير محمل."

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # 1. تحديد اللغة (نفس Hs.py)
        lang_resp = model.generate_content(f"Identify language for: '{user_input}'. Return ONLY language name.")
        lang = lang_resp.text.strip()

        # 2. تحليل الصنف (نفس البرومت اللي في Hs.py - القواعد السورية)
        prompt = (
            f"Rules: 1. 'علكة' = Chewing Gum (HS 170410). 2. 'بانجان'/'باذنجان' = Black Eggplant. "
            f"3. 'بطاطا' = Potatoes. Analyze: '{user_input}'. "
            f"Respond ONLY in {lang}. Provide top 3 HS6 codes. Format: [Category]: [HS6 Code]"
        )
        
        response = model.generate_content(prompt)
        if response and response.text:
            raw_lines = [line for line in response.text.strip().split('\n') if ':' in line]
        else:
            return "⚠️ لم يتم استلام نتائج من الذكاء الاصطناعي."

        # 3. ترجمة العناوين (نفس Hs.py)
        labels_raw = model.generate_content(f"Translate to {lang}: 'Item Name','HS6','8-Digit','Description'. Return CSV only.").text.strip().split(',')
        l = [item.strip() for item in labels_raw] if len(labels_raw) >= 4 else ["Item", "HS6", "8-Digit", "Desc"]

        outputs = []

        for line in raw_lines:
            if ':' not in line:
                continue
            item_desc_ai, hs_code_raw = line.rsplit(':', 1)
            hs6_match = re.search(r'(\d{4,6})', hs_code_raw)
            if not hs6_match:
                continue
            hs6 = hs6_match.group(1)[:6]

            # المطابقة مع الإكسل (نفس Hs.py - بدون fallback للـ 4 أرقام)
            matches = df_main[df_main['band_clean'].str.startswith(hs6)]
            if matches.empty:
                continue

            row = matches.iloc[0]

            # 4. وصف المنتج (نفس الأسلوب المباشر في Hs.py)
            desc = model.generate_content(f"Describe '{row['material_clean']}' for query '{user_input}' in {lang}. 1 direct sentence.").text.strip()

            outputs.append({
                "item": item_desc_ai.strip(),
                "hs6": hs6,
                "band": row['band_clean'],
                "desc": desc
            })

        return outputs, l

    except Exception as e:
        return f"⚠️ Error: {str(e)}", None

# --- UI ---
st.title("🇸🇾 نظام التعرفة الجمركية Across Mena")
st.markdown("---")

query = st.text_input("أدخل اسم الصنف (مثلاً: باذنجان، طماطم، حديد):")

if query:
    with st.spinner('جاري البحث والتحليل...'):
        results, labels = get_customs_consultation(query)
        
        if isinstance(results, str):
            st.error(results)
        elif not results:
            st.warning("لم يتم العثور على نتائج.")
        else:
            for res in results:
                st.subheader(f"🔍 {res['item']}")
                st.write(f"**{labels[1]}**: `{res['hs6']}`")
                st.write(f"**🇸🇾 {labels[2]}**: `{res['band']}`")
                st.info(f"**{labels[3]}**: {res['desc']}")
                st.markdown("---")

st.sidebar.title("عن النظام")
st.sidebar.info("هذا النظام يستخدم الذكاء الاصطناعي (Gemini) وقاعدة بيانات مخصصة لتحديد الرموز الجمركية.")
