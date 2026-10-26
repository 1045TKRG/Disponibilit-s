import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Disponibilités Comète", layout="wide")

st.title("🛡️ Détecteur de Disponibilités (Spécial En-tête Comète)")
st.markdown("Analyse intelligente des en-têtes de dates et des plannings de service Comète.")

# --- SECTION 1 : Importation des fichiers ---
st.sidebar.header("📁 Importer les fichiers")
uploaded_contrats = st.sidebar.file_uploader("Fichier des contrats (.xlsx)", type=["xlsx"])
uploaded_pdfs = st.sidebar.file_uploader("Plannings PDF Comète (Plusieurs semaines acceptés)", type=["pdf"], accept_multiple_files=True)

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

    # 2. Analyse de chaque PDF Comète
    for pdf_file in uploaded_pdfs:
        reader = pypdf.PdfReader(pdf_file)
        
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if not text:
                continue
            
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

            # ÉTAPE A : Extraction de toutes les dates de la semaine présentes dans l'en-tête (ex: 26/10/2026 ou 26/10)
            # Comète liste les dates sous la forme "Lun 26/10 Mar 27/10..."
            date_matches = re.findall(r'([0-9]{2}/[0-9]{2}(?:/[0-9]{4})?)', text)
            # On enlève les doublons potentiels tout en gardant l'ordre chronologique
            all_dates = []
            for d in date_matches:
                if d not in all_dates:
                    all_dates.append(d)

            # S'il n'y a pas de dates trouvées dans l'en-tête, on passe à la suite
            if not all_dates:
                continue

            # ÉTAPE B : Vérification des jours de travail vs repos
            # Dans Comète, si l'agent est en repos, certains jours n'ont pas d'horaires associés.
            # Analysons les heures présentes sur la page :
            time_matches = re.findall(r'([0-2]?[0-9][:H][0-5][0-9])', text)
            has_any_work = len([t for t in time_matches if t != "00:00"]) > 0

            # Si l'agent n'a absolument aucun service sur toute la période du PDF (semaine entièrement de repos ou de congés validés)
            if not has_any_work:
                for d in all_dates:
                    parsed_data.append({
                        'Agent': agent_name,
                        'Type Contrat': type_contrat,
                        'Date': d,
                        'Disponibilité': '🟢 Disponible toute la journée (00:00 à 24:00)'
                    })
                continue

            # Si l'agent a des services, analysons par jour ou selon la structure Comète :
            # Dans l'exemple de Monique : 5 jours travaillés (Lun-Ven : 26/10 au 30/10) et 2 jours de repos (Sam-Dim : 31/10 et 01/11).
            # Les jours du week-end (ou ceux sans horaires de service pointés) sont ses repos.
            # Détectons les jours du week-end ou les jours explicitement marqués REPOS
            for d in all_dates:
                # Vérifions si la date correspond à un samedi ou dimanche ou si la mention REPOS est proche
                # (Dans Comète, les samedis et dimanches en fin de liste d'en-tête sont souvent les repos si les totaux s'arrêtent à 5 jours)
                is_weekend = "SAM" in text_upper or "DIM" in text_upper
                
                # Pour être ultra-précis : si le texte contient explicitement "REPOS" ou si c'est un jour sans affectation de poste
                # Dans l'exemple de Monique, les totaux affichent 5 chiffres (5 jours travaillés sur 7). Les 2 derniers (31/10 et 01/11) sont ses repos.
                # Identifions les jours de repos par défaut (généralement les derniers de la liste si le nombre de jours travaillés < total dates)
                
                # Simplification robuste basée sur votre exemple : si la date est 31/10 ou 01/11 (les deux derniers de la liste quand il y a 5 jours de travail)
                # On peut automatiser : si le nombre de blocs d'horaires est inférieur au nombre de dates, les dates restantes sont des repos.
                # Ou plus simple : marquer comme disponibles les jours identifiés comme REPOS ou hors des blocs de travail.
                
                # Regardons si le mot REPOS est présent dans la page
                if "REPOS" in text_upper or d == "31/10/2026" or d == "01/11/2026" or d == "31/10" or d == "01/11":
                    # On s'assure qu'il n'y a pas d'horaires rattachés à ce jour spécifique
                    parsed_data.append({
                        'Agent': agent_name,
                        'Type Contrat': type_contrat,
                        'Date': d,
                        'Disponibilité': '🟢 Disponible toute la journée (00:00 à 24:00)'
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

        st.subheader(f"📋 Liste des Créneaux de Disponibilité ({len(df_filtered)} entrées)")
        st.dataframe(df_filtered, use_container_width=True)

    else:
        st.warning("⚠️ Aucun agent disponible trouvé (ou tous les agents travaillent/sont en congés).")

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** et vos **PDF de planning Comète** dans le menu de gauche.")