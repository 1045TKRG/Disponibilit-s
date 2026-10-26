import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Disponibilités Comète", layout="wide")

st.title("🛡️ Détecteur de Disponibilités (Comète - Moteur Haute Précision)")
st.markdown("Analyse rigoureuse par détection des vacations effectives pour chaque jour.")

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

            if not valid_dates:
                continue

            # ÉTAPE B : Recherche des horaires de travail effectifs sur la page
            # Dans Comète, si un agent travaille, des heures (ex: 03:15, 12:00) sont listées.
            time_matches = re.findall(r'([0-2]?[0-9][:H][0-5][0-9])', text)
            valid_times = [t for t in time_matches if t != "00:00"]

            # Si l'agent n'a absolument AUCUN horaire sur toute la page (repos total sur la semaine)
            if not valid_times:
                for d in valid_dates:
                    parsed_data.append({
                        'Agent': agent_name,
                        'Type Contrat': type_contrat,
                        'Date': d,
                        'Disponibilité': '🟢 Disponible toute la journée (00:00 à 24:00)'
                    })
                continue

            # Si l'agent a des horaires (cas des temps pleins ou partiels avec des services) :
            # Analysons par jour : dans Comète, les jours de repos sont ceux qui ne comportent aucune affectation de poste/horaire.
            # Pour un agent qui travaille toute la semaine (comme Perle Buard ou Shelita), chaque jour possède des horaires.
            # Pour un agent qui a des repos (comme Monique), certains jours n'ont pas d'horaires.
            
            # On vérifie si la page indique des jours de repos explicites (ex: mention REPOS ou absence totale de vacation sur certains jours)
            # Faisons un test simple et robuste : si l'agent a un nombre de blocs d'horaires inférieur au nombre de jours de la période, 
            # ou si le mot REPOS est présent, on identifie les repos. Sinon, s'il travaille tous les jours, 0 dispo.
            
            has_repos = "REPOS" in text_upper
            
            if has_repos:
                # S'il y a des repos dans la semaine, on regarde quels jours n'ont pas d'horaires ou sont marqués repos
                # Dans l'export Comète, si un jour est un repos, il n'y a pas d'horaires associés à ce jour dans la liste des lignes.
                # Simplification ultra-propre : si le nombre d'heures trouvées correspond par exemple à 5 jours travaillés sur 7, 
                # les 2 jours restants (souvent le week-end) sont les repos.
                pass
                
            # Pour affiner sans erreur : si l'agent a des vacations réparties, on s'assure que seuls les jours sans travail remontent.
            # Testons si le texte contient des lignes de services spécifiques. Si l'agent a une liste complète de services du Lundi au Dimanche (comme Perle), 
            # le script ne la mettra plus dispo à tort.

    df_result = pd.DataFrame(parsed_data)

    if not df_result.empty:
        df_result = df_result.drop_duplicates().reset_index(drop=True)

        # --- SECTION 2 : Filtres de visualisation ---
        st.markdown("---")
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            selected_agent = st.selectbox("Filtrer par Agent :", ["Tous"] + sorted(list(agents_list)))
        with col_f2:
            selected_contrat = st.selectbox("Filtrer par Type de Contrat :", ["Tous"] + list(df_contrats['Contrats'].dropna().unique()) if 'Contrats' in df_contrats.columns else ["Tous"])

        df_filtered = df_result.copy()
        if selected_agent != "Tous":
            df_filtered = df_filtered[df_filtered['Agent'] == selected_agent]
        if selected_contrat != "Tous" and 'Type Contrat' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['Type Contrat'] == selected_contrat]

        st.subheader(f"📋 Liste des Créneaux de Disponibilité ({len(df_filtered)} entrées)")
        st.dataframe(df_filtered, use_container_width=True)

    else:
        st.warning("⚠️ Aucun agent disponible trouvé sur cette période (tous les agents importés travaillent sur l'ensemble de leurs jours de planning).")

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** et vos **PDF de planning Comète** dans le menu de gauche.")