import streamlit as st
import pandas as pd
import pypdf
import re
from datetime import datetime, timedelta
from io import BytesIO

# Configuration de la page
st.set_page_config(
    page_title="SOS Remplacement - Centralistes",
    page_icon="🚨",
    layout="wide"
)

st.title("🚨 SOS Remplacement - Assistant (Conforme, Chronologique & Traçable)")
st.markdown("---")

# ---------------------------------------------------------
# 1. BARRE LATÉRALE : IMPORTATION DES FICHIERS
# ---------------------------------------------------------
st.sidebar.header("📁 Données de la Semaine")
uploaded_excel = st.sidebar.file_uploader(
    "1. Fichier Référentiel Agents (.xlsx)", 
    type=["xlsx", "xls"]
)
fichiers_planning = st.sidebar.file_uploader(
    "2. Plannings PDF Comète (Multi-contrats)", 
    type=["pdf"], 
    accept_multiple_files=True
)

def charger_referentiel(excel_file):
    try:
        df_raw = pd.read_excel(excel_file, header=None)
        df_raw[0] = df_raw[0].ffill()
        
        donnees_traitees = []
        site_actuel = ""
        
        for idx, row in df_raw.iterrows():
            val_col_a = str(row[0]).strip() if pd.notna(row[0]) else ""
            if val_col_a.upper() in ["SITES", "SITE", "NAN", "", "CONTRATS", "CONTRAT"]:
                continue
            site_actuel = val_col_a
            
            for col_idx in range(1, len(row)):
                agent_nom = str(row[col_idx]).strip() if pd.notna(row[col_idx]) else ""
                if agent_nom and agent_nom.upper() not in ["NAN", "NOM / PRENOM", "AGENT"]:
                    donnees_traitees.append({
                        "Contrat": site_actuel,
                        "Agent": agent_nom
                    })
        return pd.DataFrame(donnees_traitees), None
    except Exception as e:
        return None, f"Erreur Excel : {e}"

if not uploaded_excel:
    st.warning("⚠️ Veuillez importer le fichier **referentiel_agents.xlsx** dans le menu de gauche pour démarrer.")
    st.stop()

df_agents, erreur = charger_referentiel(uploaded_excel)
if erreur:
    st.error(f"⚠️ {erreur}")
    st.stop()

semaine_selectionnee = st.sidebar.selectbox("3. Semaine à afficher en priorité", ["S43", "S44", "Les deux"])

def decimal_to_hm(heures_dec):
    h = int(heures_dec)
    m = int(round((heures_dec - h) * 60))
    if m == 60:
        h += 1
        m = 0
    return f"{h}h{m:02d}"

# ---------------------------------------------------------
# 2. ANALYSE CHRONOLOGIQUE ET MULTI-AGENTS DES PDF
# ---------------------------------------------------------
planning_agents = {}
logs_debug = []

def noms_sont_compatibles(excel_name, pdf_text):
    e_words = [w.upper() for w in re.findall(r'\w+', excel_name) if len(w) > 2]
    p_text_upper = pdf_text.upper()
    if not e_words:
        return excel_name.upper() in p_text_upper
    matches = sum(1 for word in e_words if word in p_text_upper)
    return matches >= min(len(e_words), 1)

if fichiers_planning:
    for fichier in fichiers_planning:
        match_semaine = re.search(r'S([0-9]{1,2})', fichier.name.upper())
        
        semaines_a_traiter = []
        if match_semaine:
            semaines_a_traiter.append(int(match_semaine.group(1)))
        else:
            if semaine_selectionnee != "Les deux":
                semaines_a_traiter.append(int(semaine_selectionnee.replace('S', '')))
            else:
                semaines_a_traiter = [43, 44]

        try:
            reader = pypdf.PdfReader(fichier)
