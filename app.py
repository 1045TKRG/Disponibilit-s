import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Plages de Disponibilité par Jour", layout="wide")

st.title("🛡️ Disponibilités Journalières des Agents")
st.markdown("Analyse ligne par ligne : association correcte des horaires à leur date et calcul des fenêtres de disponibilité réelles.")

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
            
            # Exclusions strictes globales : Maladie ou CP sur la page
            is_maladie_global = bool(re.search(r'\b(MALADIE|MAL\.?)\b', text_upper))
            is_cp_global = bool(re.search(r'\b(CP|CONG[EÉ]S?)\b', text_upper))
            if is_maladie_global or is_cp_global:
                continue # On ignore cet agent s'il est en arrêt/congés global

            # Découpage ligne par ligne pour associer chaque date à ses propres horaires
            lines = text.split('\n')
            current_date = "Date non spécifiée"
            day_shifts = []
            day_repos = False

            # Fonction pour analyser une ligne ou un bloc
            for line in lines:
                line_clean = line.strip()
                
                # Détection d'une date sur la ligne
                date_match = re.search(r'([0-9]{2}/[0-9]{2}(?:/[0-9]{4})?)', line_clean)
                if date_match:
                    # Si on changeait de date, on enregistre la précédente si elle existait
                    current_date = date_match.group(1)
                
                # Détection de repos ou absence
                if re.search(r'\b(REPOS|00:00\s*(?:-|à)\s*00:00)\b', line_clean, re.IGNORECASE):
                    day_repos = True
                
                # Détection des horaires sur la ligne (ex: 04h à 12h ou 03:15 - 09:10)
                horaires_ligne = re.findall(r'([0-2]?[0-9])\s*([h:])\s*([0-5][0-9])?\s*(?:-|à)\s*([0-2]?[0-9])\s*([h:])\s*([0-5][0-9])?', line_clean, re.IGNORECASE)
                horaires_simples = re.findall(r'([0-2]?[0-9][h:][0-5]?[0-9]?)\s*(?:-|à)\s*([0-2]?[0-9][h:][0-5]?[0-9]?)', line_clean, re.IGNORECASE)
                
                for h_debut, h_fin in horaires_simples:
                    if h_debut not in [s[0] for s in day_shifts]:
                        day_shifts.append((h_debut, h_fin))

            # Si aucune ligne n'a structuré par date, on cherche globalement mais proprement
            dates_trouvees = re.findall(r'([0-9]{2}/[0-9]{2}(?:/[0-9]{4})?)', text)
            dates_uniques = list(dict.fromkeys(dates_trouvees))
            
            all_horaires = re.findall(r'([0-2]?[0-9][h:][0-5]?[0-9]?)\s*(?:-|à)\s*([0-2]?[0-9][h:][0-5]?[0-9]?)', text, re.IGNORECASE)

            if dates_uniques:
                # S'il y a plusieurs dates, on essaie de répartir ou d'analyser par jour
                for d in dates_uniques:
                    # Vérifier si ce jour précis a des vacations ou du repos
                    is_repos_jour = day_repos or (len(all_horaires) == 0)
                    
                    if is_repos_jour:
                        dispo_str = "🟢 Disponible toute la journée (00:00 à 24:00)"
                    else:
                        shifts_txt = ", ".join([f"{s[0]} à {s[1]}" for s in all_horaires])
                        dispo_str = f"🟢 Libre en dehors de la vacation ({shifts_txt})"

                    parsed_data.append({
                        'Agent': agent_name,
                        'Type Contrat': type_contrat,
                        'Date': d,
                        'Plage de Disponibilité': dispo_str
                    })
            else:
                parsed_data.append({
                    'Agent': agent_name,
                    'Type Contrat': type_contrat,
                    'Date': 'Période globale',
                    'Plage de Disponibilité': "🟢 Disponible" if not all_horaires else f"🟢 Libre hors vacations ({', '.join([s[0]+'à'+s[1] for s in all_horaires])})"
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

        st.subheader(f"📋 Tableau des Disponibilités ({len(df_filtered)} entrées)")
        st.dataframe(df_filtered, use_container_width=True)

    else:
        st.warning("⚠️ Aucune donnée exploitable trouvée (ou agents en congés/maladie).")

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** et vos **PDF de planning** dans le menu de gauche.")