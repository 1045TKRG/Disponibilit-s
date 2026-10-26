import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Disponibilités Comète", layout="wide")

st.title("🛡️ Détecteur de Disponibilités (Comète - Moteur Inversé)")
st.markdown("Approche par exclusion : tous les jours de la semaine sont présumés libres, sauf ceux où des horaires de travail sont détectés.")

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

            # ÉTAPE B : Analyse de la répartition des horaires par jour dans le texte de Comète
            # Dans Comète, le planning liste les jours sous la forme "Lun 26/10 Mar 27/10..." 
            # et associe les horaires de travail en dessous.
            # Découpons le texte de la page en blocs verticaux par date pour voir quels jours ont des heures de travail.
            
            # Pour chaque date de la période de l'agent, on cherche si des heures de travail y sont rattachées.
            for d in valid_dates:
                short_date = d[:5] # ex: "26/10"
                
                # Vérifions si cette date est présente dans le texte avec des horaires de travail proches
                # On cherche si la date apparaît dans le texte
                is_working_day = False
                
                parts = text_upper.split(short_date)
                if len(parts) > 1:
                    # On analyse ce qui suit la date dans le PDF Comète (la zone du jour concerné)
                    snippet = parts[1][:120]
                    
                    # S'il y a des horaires (ex: 03:15, 12:00) ou un code de poste (J01, N01...) dans ce bout de texte, l'agent travaille
                    time_found = re.findall(r'([0-2]?[0-9][:H][0-5][0-9])', snippet)
                    valid_times = [t for t in time_found if t != "00:00"]
                    
                    if len(valid_times) > 0 or "J0" in snippet or "N0" in snippet or "BS" in snippet:
                        is_working_day = True

                # Si ce jour-là n'a pas d'horaires de travail détectés, alors l'agent est DISPONIBLE !
                if not is_working_day:
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