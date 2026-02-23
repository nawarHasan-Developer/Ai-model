# -*- coding: utf-8 -*-
"""واجهة Streamlit - نظام التعرفة الجمركية"""
import os
import re
import pandas as pd
import streamlit as st
import google.generativeai as genai

# --- 1. الإعدادات ---
st.set_page_config(page_title="Across Mena - HS Code System", page_icon="🇸🇾", layout="centered")

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"].strip()
except Exception:
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "").strip()

if not GOOGLE_API_KEY:
    st.error("⚠️ مفتاح API غير موجود. يرجى إضافة GOOGLE_API_KEY في إعدادات Secrets.")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY, transport='rest')

# --- 2. تحميل البيانات ---
@st.cache_data
def load_resources():
    try:
        df = pd.read_excel("customs_global_brain.xlsx")
        df["band_clean"] = (
            df["band_syria"]
            .astype(str)
            .str.replace(r"[^\d]", "", regex=True)
            .str.strip()
            .str.zfill(8)
        )
        df["material_clean"] = df["material_clean"].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"❌ خطأ في تحميل الملف: {e}")
        return None

df_main = load_resources()
if df_main is None:
    st.stop()

# --- 3. منطق البحث ---
def get_customs_consultation(user_input, df_main):
    """البحث عن الرموز الجمركية. يرجع: (outputs, labels) أو (error_str, None)"""
    if df_main is None:
        return "⚠️ الملف غير محمل.", None
    if not (user_input and user_input.strip()):
        return "⚠️ يرجى إدخال اسم الصنف.", None

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        user_input = user_input.strip()

        is_arabic = bool(re.search(r"[\u0600-\u06FF]", user_input))
        if is_arabic:
            target_lang = "Arabic"
            labels = ["الصنف", "البند السداسي", "البند السوري", "الوصف"]
        else:
            lang_resp = model.generate_content(
                f"What is the language of: '{user_input}'? Return only the language name."
            )
            target_lang = lang_resp.text.strip()
            translate_resp = model.generate_content(
                f"Translate to {target_lang}: 'Item','HS6 Code','Syrian Code','Description'. Return CSV only."
            )
            labels_raw = translate_resp.text.strip().split(",")
            labels = [x.strip() for x in labels_raw] if len(labels_raw) >= 4 else ["Item", "HS6", "8-Digit", "Desc"]

        prompt = (
            f"You are a Syrian Customs Consultant. Item: '{user_input}'.\n"
            f"1. Identify 3-5 logical HS6 codes.\n"
            f"2. Your entire response must be in {target_lang}.\n"
            f"3. FORMAT: [Category Name]: [HS6 Code]. One per line. No intros."
        )
        response = model.generate_content(prompt)
        raw_lines = [line for line in response.text.strip().split("\n") if ":" in line]

        outputs = []
        processed_hs6 = set()

        for line in raw_lines:
            parts = line.rsplit(":", 1)
            if len(parts) < 2:
                continue
            item_detail = parts[0].strip()
            hs_match = re.search(r"(\d{4,6})", parts[1])
            if not hs_match:
                continue
            hs6 = hs_match.group(1)[:6]
            if hs6 in processed_hs6:
                continue
            processed_hs6.add(hs6)

            matches = df_main[df_main["band_clean"].str.startswith(hs6)]
            if matches.empty:
                matches = df_main[df_main["band_clean"].str.startswith(hs6[:4])]
            if matches.empty:
                continue

            row = matches.iloc[0]
            if is_arabic:
                desc_resp = model.generate_content(
                    f"لخص هذا الوصف الجمركي بجملة واحدة مفيدة: {row['material_clean']}"
                )
            else:
                desc_resp = model.generate_content(
                    f"Translate and summarize into ONE short sentence in {target_lang}: '{row['material_clean']}'. No Arabic."
                )
            desc = desc_resp.text.strip().replace("*", "")

            outputs.append({
                "item": item_detail,
                "hs6": hs6,
                "band": row["band_clean"],
                "desc": desc,
            })

        return outputs, labels

    except Exception as e:
        return f"⚠️ Error: {str(e)}", None

# --- 4. الواجهة ---
st.title("🇸🇾 نظام التعرفة الجمركية Across Mena")
st.markdown("---")

query = st.text_input("أدخل اسم الصنف (مثلاً: باذنجان، طماطم، حديد):")

if query:
    with st.spinner("جاري البحث والتحليل..."):
        results, labels = get_customs_consultation(query, df_main)

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
