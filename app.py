import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Suivi Plannings & Disponibilités - Sécurité", layout="wide")

st.title("🛡️ Gestion des Plannings & Disponibilités - Multi-Semaines")
st.markdown("Plateforme de consultation des agents, types de contrats et calcul des disponibilités globales.")

# --- SECTION 1 : Importation des fichiers ---
st.sidebar.header("📁 Importer les fichiers")
uploaded_contrats = st.sidebar.file_uploader("Fichier des contrats (.xlsx)", type=["xlsx"])
uploaded_pdfs = st.sidebar.file_uploader("Plannings PDF (Plusieurs semaines acceptés)", type=["pdf"], accept_multiple_files=True)

if uploaded_contrats and uploaded_pdfs:
    # 1. Lecture du fichier Excel des contrats
    df_contrats = pd.read_excel(uploaded_contrats)
    contrat_map = dict(zip(df_contrats['NOM / PRENOM'].astype(str).str.strip(), df_contrats['Contrats']))

    # Dictionnaire pour fusionner les données de plusieurs semaines par agent
    agents_dict = {}

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
            
            # Extraire les indisponibilités / repos / congés du PDF
            indispos = re.findall(r'#(?:[0-9]+)\s*:\s*(.*?)\s+le\s+([0-9]{2}/[0-9]{2}/[0-9]{4})', text)
            
            # Initialiser l'agent dans le dictionnaire s'il n'y est pas encore
            if agent_name not in agents_dict:
                agents_dict[agent_name] = {
                    'Agent': agent_name,
                    'Type de Contrat': type_contrat,
                    'Indisponibilités': []
                }
            
            # Ajouter les indisponibilités trouvées (sans doublons)
            for motif, date_str in indispos:
                item = f"{motif.strip()} le {date_str}"
                if item not in agents_dict[agent_name]['Indisponibilités']:
                    agents_dict[agent_name]['Indisponibilités'].append(item)

    # Transformer le dictionnaire en tableau final propre
    all_agents_data = []
    for agent_name, data in agents_dict.items():
        indispos_text = ", ".join(data['Indisponibilités']) if data['Indisponibilités'] else "Aucune indisponibilité listée sur la période"
        all_agents_data.append({
            'Agent': agent_name,
            'Type de Contrat': data['Type de Contrat'],
            'Disponibilité Globale / Indisponibilités': indispos_text
        })

    df_result = pd.DataFrame(all_agents_data)

    st.success(f"✅ Analyse réussie de {len(uploaded_pdfs)} fichier(s) PDF : {len(df_result)} agents uniques répertoriés.")

    # --- SECTION 2 : Affichage et Filtres ---
    st.subheader("📋 Synthèse des agents et disponibilités globales")
    
    # Filtre par type de contrat
    types_disponibles = ["Tous"] + list(df_contrats['Contrats'].dropna().unique())
    selected_contrat = st.selectbox("Filtrer par type de contrat :", types_disponibles)
    
    if selected_contrat != "Tous":
        df_filtered = df_result[df_result['Type de Contrat'] == selected_contrat]
    else:
        df_filtered = df_result

    # Affichage du tableau interactif
    st.dataframe(df_filtered, use_container_width=True)

    # --- SECTION 3 : Recherche pour vol supplémentaire ---
    st.markdown("---")
    st.subheader("✈️ Recherche d'agents disponibles pour un vol supplémentaire")
    col1, col2 = st.columns(2)
    with col1:
        date_vol = st.date_input("Date du vol supplémentaire")
    with col2:
        st.info("Module de recherche croisée activé.")

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** ET au moins un **planning PDF** dans le menu de gauche pour démarrer.")