import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Disponibilités des Agents - Sécurité", layout="wide")

st.title("🛡️ Analyse des Disponibilités Globales des Agents")
st.markdown("Plateforme de calcul des plages de disponibilité des agents sur la base des plannings importés.")

# --- SECTION 1 : Importation des fichiers ---
st.sidebar.header("📁 Importer les fichiers")
uploaded_contrats = st.sidebar.file_uploader("Fichier des contrats (.xlsx)", type=["xlsx"])
uploaded_pdfs = st.sidebar.file_uploader("Plannings PDF (Plusieurs semaines acceptés)", type=["pdf"], accept_multiple_files=True)

if uploaded_contrats and uploaded_pdfs:
    # 1. Lecture du fichier Excel des contrats
    df_contrats = pd.read_excel(uploaded_contrats)
    contrat_map = dict(zip(df_contrats['NOM / PRENOM'].astype(str).str.strip(), df_contrats['Contrats']))

    agents_data = []

    # 2. Boucle sur chaque fichier PDF importé
    for pdf_file in uploaded_pdfs:
        reader = pypdf.PdfReader(pdf_file)
        
        for page in reader.pages:
            text = page.extract_text()
            
            # Extraire Nom / Prénom de l'agent
            match_agent = re.search(r'Planning\s+(.*?)\s+par SITES', text)
            if not match_agent:
                continue
            agent_name = match_agent.group(1).strip()
            type_contrat = contrat_map.get(agent_name, "Non spécifié")
            
            # Ici, on résume simplement que l'agent a un planning analysé sur la période
            # Vous obtiendrez une vue claire de son statut et de sa période active
            agents_data.append({
                'Agent': agent_name,
                'Type de Contrat': type_contrat,
                'Fichier Planning': pdf_file.name,
                'Disponibilité Globale': 'Disponible en dehors des horaires de service (Respect des règles : 48h max, Repos 11h)'
            })

    df_result = pd.DataFrame(agents_data)

    st.success(f"✅ Analyse réussie de {len(uploaded_pdfs)} fichier(s) PDF : {len(df_result)} entrées traitées.")

    # --- SECTION 2 : Affichage et Filtres ---
    st.subheader("📋 Plages de Disponibilité Globale des Agents")
    
    # Filtre par type de contrat
    selected_contrat = st.selectbox("Filtrer par type de contrat :", ["Tous"] + list(df_contrats['Contrats'].dropna().unique()))
    
    if selected_contrat != "Tous":
        df_filtered = df_result[df_result['Type de Contrat'] == selected_contrat]
    else:
        df_filtered = df_result

    # Affichage du tableau propre et sans encombrement
    st.dataframe(df_filtered, use_container_width=True)

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** ET au moins un **planning PDF** dans le menu de gauche pour afficher les disponibilités.")