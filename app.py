import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Disponibilités & Respect des Contraintes", layout="wide")

st.title("🛡️ Calculateur de Disponibilités & Conformité des Contraintes")
st.markdown("Analyse précise des vacations, cumul journalier (max 10h), alertes de dépassement et calcul des fenêtres de disponibilité réelles.")

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
            
            # Exclusions globales : Maladie ou CP sur la page
            if bool(re.search(r'\b(MALADIE|MAL\.?)\b', text_upper)) or bool(re.search(r'\b(CP|CONG[EÉ]S?)\b', text_upper)):
                continue

            # Extraction de TOUTES les dates trouvées sur la page
            dates_trouvees = re.findall(r'((?:Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)?\s*[0-9]{2}/[0-9]{2}(?:/[0-9]{4})?)', text, re.IGNORECASE)
            dates_uniques = list(dict.fromkeys(dates_trouvees))

            # Recherche globale et robuste de tous les horaires de type HH:MM ou HHhMM
            all_horaires_raw = re.findall(r'([0-2]?[0-9])\s*([h:])\s*([0-5][0-9])\s*(?:-|à)\s*([0-2]?[0-9])\s*([h:])\s*([0-5][0-9])', text)
            
            # Conversion en minutes depuis minuit pour chaque vacation
            vacations = []
            total_minutes = 0
            for h1, sep1, m1, h2, sep2, m2 in all_horaires_raw:
                deb_min = int(h1) * 60 + int(m1)
                fin_min = int(h2) * 60 + int(m2)
                if fin_min < deb_min: 
                    fin_min += 24 * 60 # Gestion si dépassement minuit
                dur = fin_min - deb_min
                total_minutes += dur
                vacations.append((deb_min, fin_min))

            # Calcul des heures totales
            total_heures = round(total_minutes / 60, 2)
            is_repos = bool(re.search(r'\b(REPOS|00:00\s*(?:-|à)\s*00:00)\b', text_upper)) and len(vacations) == 0

            # Calcul mathématique des fenêtres de disponibilité globale de la journée (les "trous" entre les vacations)
            # On trie les vacations par ordre chronologique
            vacations.sort(key=lambda x: x[0])
            
            dispo_fenetres = []
            current_time = 0 # 00:00 en minutes

            for deb, fin in vacations:
                if deb > current_time:
                    # Il y a un espace libre avant cette vacation
                    h_d = f"{current_time // 60:02d}:{current_time % 60:02d}"
                    h_f = f"{deb // 60:02d}:{deb % 60:02d}"
                    dispo_fenetres.append(f"de {h_d} à {h_f}")
                current_time = max(current_time, fin)

            # Espace libre après la dernière vacation jusqu'à 24:00 (1440 min)
            if current_time < 1440:
                h_d = f"{current_time // 60:02d}:{current_time % 60:02d}"
                dispo_fenetres.append(f"de {h_d} à 24:00")

            if is_repos or len(vacations) == 0:
                dispo_texte = "🟢 Libre toute la journée (00:00 à 24:00)"
            else:
                if not dispo_fenetres:
                    dispo_texte = "🔴 Aucune disponibilité (Journée complète occupée)"
                else:
                    dispo_texte = "🟢 Libre " + " et ".join(dispo_fenetres)

            # Vérification de la contrainte des 10h maximum par jour
            alerte_contrainte = ""
            if total_heures > 10.0:
                alerte_contrainte = f" ⚠️ ALERTE : Dépassement de la limite légale ({total_heures}h travaillées > 10h max)"

            if dates_uniques:
                for d in dates_uniques:
                    parsed_data.append({
                        'Agent': agent_name,
                        'Type Contrat': type_contrat,
                        'Date': d.strip(),
                        'Cumul Heures': f"{total_heures}h{alerte_contrainte}",
                        'Plages de Disponibilité (Pour les Superviseurs)': dispo_texte
                    })
            else:
                parsed_data.append({
                    'Agent': agent_name,
                    'Type Contrat': type_contrat,
                    'Date': 'Période globale',
                    'Cumul Heures': f"{total_heures}h{alerte_contrainte}",
                    'Plages de Disponibilité (Pour les Superviseurs)': dispo_texte
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

        st.subheader(f"📋 Tableau des Disponibilités & Alertes Contraintes ({len(df_filtered)} entrées)")
        st.dataframe(df_filtered, use_container_width=True)

    else:
        st.warning("⚠️ Aucune donnée exploitable trouvée.")

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** et vos **PDF de planning** dans le menu de gauche.")