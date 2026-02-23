# -*- coding: utf-8 -*-
"""واجهة Streamlit - تعرض النتائج فقط"""
import os
import streamlit as st

import hs_logic

# --- 1. الإعدادات ---
st.set_page_config(page_title="Across Mena - HS Code System", page_icon="🇸🇾", layout="centered")

# قراءة المفتاح من Secrets (على السيرفر) أو من متغيرات البيئة (محلياً)
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"].strip()
except Exception:
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "").strip()

if not GOOGLE_API_KEY:
    st.error("⚠️ مفتاح API غير موجود. يرجى إضافة GOOGLE_API_KEY في إعدادات Secrets.")
    st.stop()

import google.generativeai as genai
genai.configure(api_key=GOOGLE_API_KEY, transport='rest')

# --- 2. تحميل البيانات (مع كاش) ---
@st.cache_data
def load_data():
    return hs_logic.load_resources()

df_main = load_data()
if df_main is None:
    st.error("❌ خطأ في تحميل ملف Excel.")
    st.stop()

# --- 3. الواجهة ---
st.title("🇸🇾 نظام التعرفة الجمركية Across Mena")
st.markdown("---")

query = st.text_input("أدخل اسم الصنف (مثلاً: باذنجان، طماطم، حديد):")

if query:
    with st.spinner('جاري البحث والتحليل...'):
        results, labels = hs_logic.get_customs_consultation(query, df_main)

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
