import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Disponibilités des Agents", layout="wide")

st.title("🛡️ Table des Agents Disponibles")
st.markdown("Analyse intelligente ligne par ligne : détection stricte des jours travaillés (Exclusion des CP, Malades et agents en service).")

# --- SECTION 1 : Importation des fichiers ---
st.sidebar.header("📁 Importer les fichiers")
uploaded_contrats = st.sidebar.file_uploader("Fichier des contrats (.xlsx)", type=["xlsx"])
uploaded_pdfs = st.sidebar.file_uploader("Plannings PDF (Plusieurs semaines acceptés)", type=["pdf"], accept_multiple_files=True)

if uploaded_contrats and uploaded_pdfs:
    # 1. Lecture du fichier Excel des contrats
    df_contrats = pd.read_excel(uploaded_contrats)
    contrat_map = {}
    for _, row in df_contrats.iterrows():
        nom = str(row.get('NOM / PRENOM', row.get('Nom', row.get('Agent', '')))).strip().upper()
        type_c = str(row.get('Contrats', row.get('Type', row.get('Contrat', 'Non spécifié')))).strip()
        if nom:
            contrat_map[nom] = type_c

    parsed_data = []
    agents_list = set()

    # 2. Analyse de chaque PDF
    for pdf_file in uploaded_pdfs:
        reader = pypdf.PdfReader(pdf_file)
        
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            
            # Extraction du nom de l'agent
            match_agent = re.search(r'Planning\s+(.*?)\s+par SITES', text, re.IGNORECASE)
            if not match_agent:
                match_agent = re.search(r'Agent\s*:\s*(.*?)(?=\s+du|\s+site|\n)', text, re.IGNORECASE)
            
            agent_name = match_agent.group(1).strip() if match_agent else "AGENT INCONNU"
            agents_list.add(agent_name)
            type_contrat = contrat_map.get(agent_name.upper(), "Non spécifié")
            
            text_upper = text.upper()
            
            # Exclusions globales page entière : Maladie ou CP global
            if bool(re.search(r'\b(MALADIE|MAL\.?)\b', text_upper)) or bool(re.search(r'\b(CP|CONG[EÉ]S?)\b', text_upper)):
                continue

            # Analyse ligne par ligne
            lines = text.split('\n')
            current_date = None
            date_status = {} # Dictionnaire pour stocker l'état de chaque date

            for line in lines:
                line_clean = line.strip()
                line_upper = line_clean.upper()

                # Recherche d'une date sur la ligne (ex: 26/10 ou Lundi 26/10)
                date_match = re.search(r'([0-9]{2}/[0-9]{2}(?:/[0-9]{4})?)', line_clean)
                if date_match:
                    current_date = date_match.group(1)
                    if current_date not in date_status:
                        date_status[current_date] = {'has_work': False, 'is_repos': False, 'is_off': False}

                if current_date:
                    # Vérification des mots clés d'absence
                    if re.search(r'\b(MALADIE|MAL\.?|CP|CONG[EÉ]S?)\b', line_upper):
                        date_status[current_date]['is_off'] = True
                    
                    if re.search(r'\b(REPOS)\b', line_upper):
                        date_status[current_date]['is_repos'] = True

                    # Détection robuste de tout horaire présent sur la ligne (ex: 03:15, 09:10, 04h...)
                    # On s'assure que ce n'est pas un "00:00" de repos
                    time_matches = re.findall(r'([0-2]?[0-9][:h][0-5][0-9])', line_upper)
                    if time_matches:
                        # Si on trouve des heures valides (différentes de 00:00 de repos), l'agent travaille ce jour-là
                        valid_times = [t for t in time_matches if t != "00:00"]
                        if valid_times:
                            date_status[current_date]['has_work'] = True

            # Si des dates ont été trouvées et analysées
            if date_status:
                for d, info in date_status.items():
                    # Si l'agent travaille, est en congé ou malade ce jour-là, IL N'EST PAS DISPONIBLE -> On l'exclut
                    if info['has_work'] or info['is_off']:
                        continue  
                    
                    # S'il est explicitement en repos (ou sans aucun travail détecté ce jour-là)
                    if info['is_repos'] or not info['has_work']:
                        parsed_data.append({
                            'Agent': agent_name,
                            'Type Contrat': type_contrat,
                            'Date': d,
                            'Disponibilité': '🟢 Disponible toute la journée (00:00 à 24:00)'
                        })

    df_result = pd.DataFrame(parsed_data)

    if not df_result.empty:
        # Nettoyage des doublons
        df_result = df_result.drop_duplicates().reset_index(drop=True)

        # --- SECTION 2 : Filtres de visualisation ---
        st.markdown("---")
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            selected_agent = st.selectbox("Filtrer par Agent :", ["Tous"] + sorted(list(agents_list)))
        with col_f2:
            selected_contrat = st.selectbox("Filtrer par Type de Contrat :", ["Tous"] + list(df_contrats['Contrats'].dropna().unique()) if 'Contrats' in df_contrats.columns else ["Tous"])

        # Application des filtres
        df_filtered = df_result.copy()
        if selected_agent != "Tous":
            df_filtered = df_filtered[df_filtered['Agent'] == selected_agent]
        if selected_contrat != "Tous" and 'Type Contrat' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['Type Contrat'] == selected_contrat]

        st.subheader(f"📋 Liste des Créneaux de Disponibilité ({len(df_filtered)} entrées)")
        st.dataframe(df_filtered, use_container_width=True)

    else:
        st.warning("⚠️ Aucun agent disponible trouvé.")

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** et vos **PDF de planning** dans le menu de gauche.")