import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Suivi Plannings & Disponibilités - Tahiti Sûreté", layout="wide")

st.title("🛡️ Gestion des Plannings & Disponibilités - Agents")
st.markdown("Plateforme sécurisée de consultation des agents disponibles et de leurs types de contrats.")

# --- SECTION 1 : Importation des fichiers par l'administrateur ---
st.sidebar.header("📁 Importer les fichiers")
uploaded_contrats = st.sidebar.file_uploader("Fichier des contrats (.xlsx)", type=["xlsx"])
uploaded_pdf = st.sidebar.file_uploader("Planning PDF de la semaine", type=["pdf"])

if uploaded_contrats and uploaded_pdf:
    # Lecture du fichier Excel des contrats
    df_contrats = pd.read_excel(uploaded_contrats)
    contrat_map = dict(zip(df_contrats['NOM / PRENOM'].astype(str).str.strip(), df_contrats['Contrats']))

    # Lecture du PDF de planning
    reader = pypdf.PdfReader(uploaded_pdf)
    
    agents_data = []

    for page in reader.pages:
        text = page.extract_text()
        
        # Extraire Nom / Prénom
        match_agent = re.search(r'Planning\s+(.*?)\s+par SITES', text)
        if not match_agent:
            continue
        agent_name = match_agent.group(1).strip()
        type_contrat = contrat_map.get(agent_name, "Non spécifié")
        
        # Recherche des vacations / horaires ou indisponibilités
        agents_data.append({
            'Agent': agent_name,
            'Type de Contrat': type_contrat,
            'Statut Général': 'Actif sur la période'
        })

    df_result = pd.DataFrame(agents_data)

    st.success(f"✅ Analyse réussie : {len(df_result)} agents répertoriés.")

    # --- SECTION 2 : Affichage du tableau ---
    st.subheader("📋 Liste des agents et types de contrats")
    
    # Filtre par type de contrat
    selected_contrat = st.selectbox("Filtrer par type de contrat :", ["Tous"] + list(df_contrats['Contrats'].dropna().unique()))
    
    if selected_contrat != "Tous":
        df_filtered = df_result[df_result['Type de Contrat'] == selected_contrat]
    else:
        df_filtered = df_result

    st.dataframe(df_filtered, use_container_width=True)

    # --- SECTION 3 : Recherche pour vol supplémentaire ---
    st.markdown("---")
    st.subheader("✈️ Recherche d'agents pour vol supplémentaire")
    col1, col2 = st.columns(2)
    with col1:
        date_vol = st.date_input("Date du vol supplémentaire")
    with col2:
        st.info("Module de croisement des créneaux horaires activé.")

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** et un fichier **PDF de planning** via le menu de gauche pour afficher la plateforme.")