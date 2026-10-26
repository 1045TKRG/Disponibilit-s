import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Gestion des Disponibilités Agents", layout="wide")

st.title("🛡️ Table des Disponibilités Agents (Conformité & Repos)")
st.markdown("Affichage exclusif des disponibilités (Exclusion des CP, Malades et intégration des règles de repos).")

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
            match_agent = re.search(r'Planning\s+(.*?)\s+par SITES', text)
            if not match_agent:
                match_agent = re.search(r'Agent\s*:\s*(.*?)(?=\s+du|\s+site|\n)', text, re.IGNORECASE)
            
            agent_name = match_agent.group(1).strip() if match_agent else "AGENT INCONNU"
            agents_list.add(agent_name)
            type_contrat = contrat_map.get(agent_name.upper(), "Non spécifié")
            
            # Recherche des dates (ex: Lundi 26/10 ou 26/10/2026)
            dates_trouvees = re.findall(r'(?:Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)?\s*([0-9]{2}/[0-9]{2}(?:/[0-9]{4})?)', text, re.IGNORECASE)
            dates_uniques = list(dict.fromkeys(dates_trouvees))
            
            text_upper = text.upper()
            
            # Détection des statuts particuliers
            is_maladie = bool(re.search(r'\b(MALADIE|MAL\.?)\b', text_upper))
            is_cp = bool(re.search(r'\b(CP|CONG[EÉ]S?)\b', text_upper))
            is_delegation = bool(re.search(r'D[EÉ]L[EÉ]GATION', text_upper))
            is_repos = bool(re.search(r'\b(REPOS|00:00\s*(?:-|à)\s*00:00)\b', text_upper))
            
            # Recherche des horaires de vacations
            horaires_match = re.findall(r'([0-2]?[0-9])[:h]([0-5][0-9])\s*(?:-|à)?\s*([0-2]?[0-9])[:h]([0-5][0-9])', text)
            
            total_minutes = 0
            for h1, m1, h2, m2 in horaires_match:
                deb_min = int(h1) * 60 + int(m1)
                fin_min = int(h2) * 60 + int(m2)
                dur = fin_min - deb_min
                if dur < 0: 
                    dur += 24 * 60
                total_minutes += dur
            
            # Si heures de délégation, on les assimile à du temps de travail (ex: équivalent 7h si non chiffré, ou basé sur le texte)
            if is_delegation:
                total_minutes += 420  # Ajout forfaitaire de 7h de travail pour une journée de délégation type si non précisé
            
            total_heures_dec = round(total_minutes / 60, 2)
            
            # Un agent est considéré en service s'il a des heures de travail ou une délégation active
            has_work = (len(horaires_match) > 0) or is_delegation
            
            # Si l'agent est en Maladie ou CP, il est STRICTEMENT EXCLU des dispos
            if is_maladie or is_cp:
                continue  # On passe, on ne l'ajoute pas aux agents disponibles

            if dates_uniques:
                for date_agent in dates_uniques:
                    # Si la journée comporte du travail ou une délégation, l'agent n'est pas dispo sur ce créneau
                    if has_work and not is_repos:
                        continue 
                    
                    # Si c'est un repos explicite ou absence de travail, il est disponible
                    if is_repos or not has_work:
                        parsed_data.append({
                            'Agent': agent_name,
                            'Type Contrat': type_contrat,
                            'Date': date_agent,
                            'Disponibilité': '🟢 Disponible (Jour de Repos)'
                        })
            else:
                if not has_work:
                    parsed_data.append({
                        'Agent': agent_name,
                        'Type Contrat': type_contrat,
                        'Date': 'Période globale',
                        'Disponibilité': '🟢 Disponible'
                    })

    df_result = pd.DataFrame(parsed_data)

    if not df_result.empty:
        # Nettoyage strict des doublons
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

        st.subheader(f"📋 Agents Disponibles ({len(df_filtered)} entrées)")
        st.dataframe(df_filtered, use_container_width=True)

    else:
        st.warning("⚠️ Aucun agent disponible trouvé ou tous les agents sont en congés/maladie sur cette période.")

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** et vos **PDF de planning** dans le menu de gauche pour lancer l'application.")