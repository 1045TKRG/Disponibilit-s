import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Suivi Plannings - Debug & Nettoyage", layout="wide")

st.title("🛡️ Analyseur de Plannings & Disponibilités")
st.markdown("Outil de lecture des plannings PDF et des contrats Excel.")

# --- SECTION 1 : Importation ---
st.sidebar.header("📁 Importer les fichiers")
uploaded_contrats = st.sidebar.file_uploader("Fichier des contrats (.xlsx)", type=["xlsx"])
uploaded_pdfs = st.sidebar.file_uploader("Plannings PDF (Plusieurs semaines acceptés)", type=["pdf"], accept_multiple_files=True)

if uploaded_contrats and uploaded_pdfs:
    # 1. Lecture des contrats
    df_contrats = pd.read_excel(uploaded_contrats)
    contrat_map = dict(zip(df_contrats['NOM / PRENOM'].astype(str).str.strip(), df_contrats['Contrats']))

    agents_data = []

    # 2. Analyse des PDF
    for pdf_file in uploaded_pdfs:
        reader = pypdf.PdfReader(pdf_file)
        
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            
            # Extraire le nom de l'agent
            match_agent = re.search(r'Planning\s+(.*?)\s+par SITES', text)
            if not match_agent:
                continue
            agent_name = match_agent.group(1).strip()
            type_contrat = contrat_map.get(agent_name, "Non spécifié")
            
            # Trouver les dates sur la page
            dates_trouvees = re.findall(r'([0-9]{2}/[0-9]{2}/[0-9]{4})', text)
            dates_uniques = list(dict.fromkeys(dates_trouvees))
            
            # Détection des repos explicites
            is_repos = bool(re.search(r'\b(REPOS|00:00\s*(?:-|à)\s*00:00)\b', text, re.IGNORECASE))
            
            # Stockage pour le tableau
            if dates_uniques:
                for date_agent in dates_uniques:
                    if is_repos:
                        dispo_texte = f"🟢 100% DISPONIBLE (Repos le {date_agent})"
                    else:
                        dispo_texte = "⚠️ À vérifier (Vacation détectée)"
                    
                    agents_data.append({
                        'Agent': agent_name,
                        'Type de Contrat': type_contrat,
                        'Date': date_agent,
                        'Statut de Disponibilité': dispo_texte
                    })
            
            # Option pour afficher le texte brut lu par le PDF (très utile pour comprendre)
            with st.expander(f"🔍 [Debug] Voir le texte brut extrait pour : {agent_name} (Page {page_num+1})"):
                st.text(text)

    if agents_data:
        df_result = pd.DataFrame(agents_data).drop_duplicates().reset_index(drop=True)
        st.success(f"✅ Analyse réussie : {len(df_result)} lignes générées.")

        # --- SECTION 2 : Affichage du tableau ---
        st.subheader("📋 Tableau des Disponibilités par Date")
        
        selected_contrat = st.selectbox("Filtrer par type de contrat :", ["Tous"] + list(df_contrats['Contrats'].dropna().unique()))
        
        if selected_contrat != "Tous":
            df_filtered = df_result[df_result['Type de Contrat'] == selected_contrat]
        else:
            df_filtered = df_result

        st.dataframe(df_filtered, use_container_width=True)
    else:
        st.warning("⚠️ Aucun agent n'a pu être reconnu automatiquement avec le motif 'Planning ... par SITES'.")

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** et vos **PDF de planning** dans le menu de gauche.")