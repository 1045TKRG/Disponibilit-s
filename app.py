import streamlit as st
import pandas as pd
import pypdf
import re
from datetime import datetime, timedelta
from io import BytesIO

st.set_page_config(page_title="SOS Remplacement - Debug", layout="wide")
st.title("🚨 SOS Remplacement - Mode Diagnostic Avancé")
st.markdown("---")

uploaded_excel = st.sidebar.file_uploader("1. Référentiel (.xlsx)", type=["xlsx", "xls"])
fichiers_planning = st.sidebar.file_uploader("2. Plannings PDF", type=["pdf"], accept_multiple_files=True)

if not uploaded_excel:
    st.warning("⚠️ Veuillez importer votre fichier Excel.")
    st.stop()

# Lecture rapide du référentiel
df_raw = pd.read_excel(uploaded_excel, header=None)
df_raw[0] = df_raw[0].ffill()
donnees_traitees = []
for idx, row in df_raw.iterrows():
    val_col_a = str(row[0]).strip() if pd.notna(row[0]) else ""
    if val_col_a.upper() not in ["SITES", "SITE", "NAN", "", "CONTRATS"]:
        for col_idx in range(1, len(row)):
            agent_nom = str(row[col_idx]).strip() if pd.notna(row[col_idx]) else ""
            if agent_nom and agent_nom.upper() not in ["NAN", "NOM / PRENOM", "AGENT"]:
                donnees_traitees.append({"Contrats": val_col_a, "Agent": agent_nom})

df_agents = pd.DataFrame(donnees_traitees)

st.subheader("1. Agents détectés dans votre Excel :")
st.write(df_agents["Agent"].tolist())

if fichiers_planning:
    st.subheader("2. Analyse des PDF importés :")
    for fichier in fichiers_planning:
        reader = pypdf.PdfReader(fichier)
        texte_complet = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                texte_complet += t + "\n"
        
        st.write(f"**Fichier :** `{fichier.name}` ({len(texte_complet)} caractères extraits)")
        
        # Test de correspondance avec chaque agent de l'Excel
        agents_trouves = []
        for ag in df_agents["Agent"].unique():
            # On nettoie un peu pour comparer
            if ag.upper() in texte_complet.upper():
                agents_trouves.append(ag)
        
        if agents_trouves:
            st.success(f"Agents reconnus dans ce PDF : {agents_trouves}")
        else:
            st.error(f"❌ Aucun agent de l'Excel n'a pu être repéré dans ce PDF. Extrait du texte lu :")
            st.code(texte_complet[:500]) # Affiche les 500 premiers caractères du PDF pour voir à quoi ça ressemble
else:
    st.info("Veuillez importer au moins un fichier PDF dans la barre latérale pour lancer le diagnostic.")
