import streamlit as st
import pandas as pd
import pypdf
import re
from datetime import datetime, timedelta

st.set_page_config(page_title="SOS Remplacement - Debug", layout="wide")
st.title("🚨 SOS Remplacement - Mode Diagnostic")
st.markdown("---")

uploaded_excel = st.sidebar.file_uploader("1. Référentiel (.xlsx)", type=["xlsx", "xls"])
fichiers_planning = st.sidebar.file_uploader("2. Plannings PDF", type=["pdf"], accept_multiple_files=True)

if not uploaded_excel:
    st.warning("⚠️ Veuillez importer votre fichier Excel référentiel.")
    st.stop()

# 1. Lecture Excel
try:
    df_raw = pd.read_excel(uploaded_excel, header=None)
    df_raw[0] = df_raw[0].ffill()
    agents_excel = []
    site_actuel = ""
    for idx, row in df_raw.iterrows():
        val_col_a = str(row[0]).strip() if pd.notna(row[0]) else ""
        if val_col_a.upper() in ["SITES", "SITE", "NAN", ""]:
            continue
        site_actuel = val_col_a
        for col_idx in range(1, len(row)):
            agent_nom = str(row[col_idx]).strip() if pd.notna(row[col_idx]) else ""
            if agent_nom and agent_nom.upper() != "NAN":
                agents_excel.append({"Contrats": site_actuel, "Agent": agent_nom})
    df_agents = pd.DataFrame(agents_excel)
    st.success(f"✅ Fichier Excel lu avec succès : {len(df_agents)} agents trouvés dans le référentiel.")
except Exception as e:
    st.error(f"Erreur lecture Excel : {e}")
    st.stop()

# 2. Lecture PDF
planning_agents = {}
if fichiers_planning:
    for fichier in fichiers_planning:
        try:
            reader = pypdf.PdfReader(fichier)
            texte_complet = ""
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    texte_complet += t + "\n"
            
            # Chercher le nom de l'agent dans le PDF
            agent_name_pdf = "Inconnu"
            for line in texte_complet.split('\n'):
                if "AGENT" in line.upper():
                    agent_name_pdf = line
                    break
            
            st.info(f"📄 **Fichier PDF analysé :** `{fichier.name}` | **Ligne agent détectée :** {agent_name_pdf}")
        except Exception as e:
            st.error(f"Erreur lecture PDF {fichier.name}: {e}")

st.markdown("### 📋 Liste des agents dans votre Référentiel Excel :")
st.dataframe(df_agents, use_container_width=True)