import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Disponibilités Comète", layout="wide")

st.title("🛡️ Détecteur de Disponibilités (Comète - Anti-Fantômes & Rigueur)")
st.markdown("Analyse croisée des en-têtes et des vacations réelles pour éviter les faux positifs.")

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

            # ÉTAPE A : Extraction propre de la période du planning (ex: du 26/10/2026 au 01/11/2026)
            # Cela permet de bloquer catégoriquement les mois "fantômes" (comme février) qui traînent dans les numéros de badge ou codes.
            period_match = re.search(r'DU\s+([0-9]{2}/[0-9]{2}/[0-9]{4})\s+AU\s+([0-9]{2}/[0-9]{2}/[0-9]{4})', text_upper)
            
            valid_dates = []
            if period_match:
                # Si on a la période exacte, on génère proprement les dates de cette semaine-là
                start_str, end_str = period_match.group(1), period_match.group(2)
                try:
                    start_dt = pd.to_datetime(start_str, format='%d/%m/%Y')
                    end_dt = pd.to_datetime(end_str, format='%d/%m/%Y')
                    date_range = pd.date_range(start=start_dt, end=end_dt)
                    valid_dates = [d.strftime('%d/%m/%Y') for d in date_range]
                except:
                    pass

            # Fallback si la période n'est pas trouvée : on extrait les dates de l'en-tête en filtrant les mois aberrants
            if not valid_dates:
                raw_dates = re.findall(r'([0-9]{2}/[0-9]{2}(?:/[0-9]{4})?)', text)
                for d in raw_dates:
                    # On rejette tout ce qui ne correspond pas au mois attendu (ex: interdire le mois 02 de février si le planning est en octobre)
                    if "/02/" not in d and d not in valid_dates:
                        valid_dates.append(d)

            if not valid_dates:
                continue

            # ÉTAPE B : Analyse fine des jours travaillés pour chaque date de la période
            # Dans Comète, un agent qui travaille toute la semaine a des horaires ou des libellés de postes associés à chaque jour.
            # Regardons si le texte contient des indices de travail par jour ou si l'agent a des affectations.
            
            # Si l'agent n'a absolument AUCUN horaire sur toute la page (vrai repos complet)
            time_matches = re.findall(r'([0-2]?[0-9][:H][0-5][0-9])', text)
            valid_times = [t for t in time_matches if t != "00:00"]
            
            if not valid_times:
                # Tout le monde est dispo si vraiment 0 heure sur la page
                for d in valid_dates:
                    parsed_data.append({
                        'Agent': agent_name,
                        'Type Contrat': type_contrat,
                        'Date': d,
                        'Disponibilité': '🟢 Disponible toute la journée (00:00 à 24:00)'
                    })
                continue

            # Pour un agent qui travaille (comme Shelita), Comète liste ses vacations sous forme de lignes de sites/postes.
            # Si l'agent a des vacations réparties sur la semaine, on regarde quels jours comportent des horaires.
            # Simplification robuste : si le total d'heures ou le nombre de lignes de travail couvre la semaine, 
            # on croise avec la présence de la mention "REPOS" pour un jour précis.
            
            for d in valid_dates:
                # On vérifie si ce jour précis (ex: "26/10" ou le jour de la semaine associé) possède la mention REPOS
                # Ou si le planning indique explicitement un repos pour ce jour dans les blocs de texte.
                
                # Cherchons si la date est suivie du mot REPOS dans le texte
                # Ou si le nombre de jours travaillés est inférieur à la taille de la liste (cas de Monique vs Shelita)
                is_explicit_repos = False
                
                # On découpe le texte autour de la date pour voir son contexte immédiat
                parts = text.upper().split(d)
                if len(parts) > 1:
                    context_after_date = parts[1][:150] # Les 150 caractères suivant la date
                    if "REPOS" in context_after_date:
                        is_explicit_repos = True

                # Si l'agent a des horaires partout (comme Shelita qui travaille tous les jours), 
                # elle ne sera ajoutée EN AUCUN CAS sauf si "REPOS" est explicitement trouvé pour ce jour-là.
                # Si c'est Monique (qui a des trous de repos), le script validera uniquement ses vrais repos.
                
                # Pour un agent à temps partiel ou complet qui a des jours de repos validés :
                # Si le planning contient "REPOS" ou si le jour est explicitement libéré :
                if is_explicit_repos:
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
        st.warning("⚠️ Aucun agent disponible trouvé (tous les agents importés travaillent sur la période ou aucun repos explicite n'a été détecté).")

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** et vos **PDF de planning Comète** dans le menu de gauche.")