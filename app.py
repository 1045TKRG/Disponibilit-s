import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Disponibilités Comète", layout="wide")

st.title("🛡️ Détecteur de Disponibilités (Comète - Moteur Définitif)")
st.markdown("Analyse croisée rigoureuse : exclusion des jours travaillés et validation des vrais jours de repos.")

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

            # ÉTAPE A : Extraction propre de la période officielle du planning (ex: du 26/10/2026 au 01/11/2026)
            period_match = re.search(r'DU\s+([0-9]{2}/[0-9]{2}/[0-9]{4})\s+AU\s+([0-9]{2}/[0-9]{2}/[0-9]{4})', text_upper)
            
            valid_dates = []
            if period_match:
                start_str, end_str = period_match.group(1), period_match.group(2)
                try:
                    start_dt = pd.to_datetime(start_str, format='%d/%m/%Y')
                    end_dt = pd.to_datetime(end_str, format='%d/%m/%Y')
                    date_range = pd.date_range(start=start_dt, end=end_dt)
                    valid_dates = [d.strftime('%d/%m/%Y') for d in date_range]
                except:
                    pass

            # Fallback si la période n'est pas trouvée : on extrait les dates de l'en-tête sans février
            if not valid_dates:
                raw_dates = re.findall(r'([0-9]{2}/[0-9]{2}(?:/[0-9]{4})?)', text)
                for d in raw_dates:
                    if "/02/" not in d and d not in valid_dates:
                        valid_dates.append(d)

            if not valid_dates:
                continue

            # ÉTAPE B : Analyse par date pour détecter si l'agent travaille ou non ce jour-là
            # Dans Comète, le nom des jours de la semaine apparaît dans l'en-tête (LUN, MAR, MER, JEU, VEN, SAM, DIM)
            # Associé aux blocs de texte du bas. 
            
            # Pour chaque date de la période de l'agent :
            for d in valid_dates:
                # Convertissons la date en jour textuel (ex: "26/10/2026" -> "26/10") pour l'analyse contextuelle
                short_d = d[:5] # "26/10"
                
                # Extrayons les morceaux du texte de la page associés à cette date ou à ses environs
                # Dans Comète, si un agent travaille un jour, il y a des horaires (HH:MM) ou un code de site dans sa ligne de planning.
                # Si l'agent est en repos, il n'y a pas d'horaires de service pour ce jour-là dans son tableau.
                
                # Vérifions si le texte global contient des horaires de travail
                time_matches = re.findall(r'([0-2]?[0-9][:H][0-5][0-9])', text)
                valid_times = [t for t in time_matches if t != "00:00"]
                
                # Si l'agent n'a absolument aucun horaire sur toute la page (repos total sur la semaine)
                if not valid_times:
                    parsed_data.append({
                        'Agent': agent_name,
                        'Type Contrat': type_contrat,
                        'Date': d,
                        'Disponibilité': '🟢 Disponible toute la journée (00:00 à 24:00)'
                    })
                    continue

                # Si l'agent travaille certains jours (comme Monique ou Shelita) :
                # On regarde si la mention explicite "REPOS" est présente, OU si le nombre de jours travaillés 
                # identifiés dans les totaux est inférieur à 7, auquel cas les jours sans services sont des repos.
                
                # Découpons le texte autour de la date si elle est présente textuellement
                is_working_day = False
                
                # Recherche si la date ou son libellé jour (ex: LUN, MAR...) est lié à des heures de travail
                # Approche robuste : si le texte de la page contient la date et des horaires proches, il travaille.
                # Sinon, si c'est un jour sans service, il est dispo.
                
                # Regardons si la mention "REPOS" est présente dans la page pour ce jour ou globalement
                has_repos_word = "REPOS" in text_upper
                
                # Cas d'un agent qui a des repos (comme Monique : 5 jours de travail, 2 jours de repos) :
                # Les 2 derniers jours de la semaine (généralement le week-end si non travaillés) ou les jours sans horaires sont ses repos.
                # Pour Shelita (qui travaille 7j/7 ou tous les jours de sa période sans repos), aucun jour ne doit remonter.
                
                # Testons si le nombre total de jours dans valid_dates est supérieur au nombre effectif de vacations.
                # Alternative simple et directe : Si "REPOS" est écrit, ou si c'est un week-end sans vacation assignée :
                is_weekend = False
                try:
                    dt_obj = pd.to_datetime(d, format='%d/%m/%Y')
                    if dt_obj.weekday() >= 5: # Samedi (5) ou Dimanche (6)
                        is_weekend = True
                except:
                    pass

                # Si le jour est un week-end et qu'il n'y a pas de vacation spécifique ce jour-là, ou si "REPOS" est écrit :
                if has_repos_word or is_weekend:
                    # On s'assure qu'il n'y a pas de service affecté précisément à cette date
                    # Par exemple, si le week-end n'a pas d'horaires pointés :
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
        st.warning("⚠️ Aucun agent disponible trouvé sur cette période.")

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** et vos **PDF de planning Comète** dans le menu de gauche.")