import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Disponibilités Comète", layout="wide")

st.title("🛡️ Détecteur de Disponibilités (Comète - Moteur Stricte Précision)")
st.markdown("Analyse sécurisée des plannings de type Comète.")

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

            # ÉTAPE B : Sécurité stricte anti-faux positifs
            # On extrait tous les horaires de travail de la page
            time_matches = re.findall(r'([0-2]?[0-9][:H][0-5][0-9])', text)
            valid_times = [t for t in time_matches if t != "00:00"]

            # Si l'agent n'a absolument aucun service sur toute la page (repos total sur la semaine)
            if not valid_times:
                for d in valid_dates:
                    parsed_data.append({
                        'Agent': agent_name,
                        'Type Contrat': type_contrat,
                        'Date': d,
                        'Disponibilité': '🟢 Disponible toute la journée (00:00 à 24:00)'
                    })
                continue

            # Si l'agent a des services : 
            # Sur un modèle comme Monique, on repère si la mention "REPOS" est présente dans le texte,
            # ou si le nombre de jours de travail est inférieur à la semaine complète.
            has_repos = "REPOS" in text_upper
            
            if has_repos:
                # Si le planning contient le mot REPOS, on isole précisément les jours sans vacation
                for d in valid_dates:
                    short_date = d[:5] # ex: "26/10"
                    parts = text_upper.split(short_date)
                    is_day_off = True
                    
                    if len(parts) > 1:
                        snippet = parts[1][:120]
                        # S'il y a un horaire ou un code de poste rattaché à ce morceau, l'agent travaille
                        if re.findall(r'([0-2]?[0-9][:H][0-5][0-9])', snippet) or "J0" in snippet or "N0" in snippet:
                            is_day_off = False
                    
                    if is_day_off:
                        parsed_data.append({
                            'Agent': agent_name,
                            'Type Contrat': type_contrat,
                            'Date': d,
                            'Disponibilité': '🟢 Disponible toute la journée (00:00 à 24:00)'
                        })
            else:
                # Si l'agent travaille tous les jours de sa période sans mention de repos (comme Joseph ou Perle),
                # on ne l'ajoute pas dans les disponibilités.

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