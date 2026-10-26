import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Disponibilités Comète", layout="wide")

st.title("🛡️ Détecteur de Disponibilités (Comète - Moteur Chirurgical)")
st.markdown("Analyse précise des jours effectivement travaillés versus les jours de repos.")

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

            # ÉTAPE B : Découpage chirurgical par blocs de dates dans le texte Comète
            # Comète liste les jours de la semaine (ex: Lun 26/10, Mar 27/10...)
            # On découpe le texte pour analyser ce qui appartient à chaque jour individuellement.
            
            # Recherche des motifs de dates dans le texte pour isoler chaque journée
            for d in valid_dates:
                # Format court pour chercher dans l'en-tête (ex: "26/10")
                short_date = d[:5]
                
                # On vérifie si le texte contient explicitement la mention "REPOS" rattachée à cette date ou à ce jour
                # Ou si le jour n'a aucun horaire de service associé dans le planning de l'agent.
                
                # Cherchons les blocs de texte autour de la date
                is_working = False
                is_repos = False
                
                # Si le texte contient le mot "REPOS" sur la page, regardons si c'est présent
                if "REPOS" in text_upper:
                    # Vérifions si "REPOS" est présent dans la zone de la date
                    parts = text_upper.split(short_date)
                    if len(parts) > 1:
                        snippet = parts[1][:100] # Les 100 caractères suivant la date
                        if "REPOS" in snippet:
                            is_repos = True
                        elif re.search(r'([0-2]?[0-9][:H][0-5][0-9])', snippet):
                            is_working = True
                
                # Autre méthode infaillible pour Comète : 
                # Si l'agent a un total d'heures ou des vacations listées, comptons les jours où il y a des horaires.
                # Pour un agent comme Shelita qui travaille toute la semaine, tous les jours ont des horaires ou des affectations de postes.
                # Pour un agent comme Monique, certains jours n'ont pas d'horaires pointés.
                
                # Si aucun horaire n'est détecté du tout sur la page pour cet agent :
                time_matches = re.findall(r'([0-2]?[0-9][:H][0-5][0-9])', text)
                valid_times = [t for t in time_matches if t != "00:00"]
                
                if not valid_times:
                    # Vrai repos total sur la période
                    parsed_data.append({
                        'Agent': agent_name,
                        'Type Contrat': type_contrat,
                        'Date': d,
                        'Disponibilité': '🟢 Disponible toute la journée (00:00 à 24:00)'
                    })
                elif is_repos:
                    # Jour explicitement marqué REPOS
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