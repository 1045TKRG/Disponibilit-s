import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Analyseur de Plannings & Disponibilités", layout="wide")

st.title("🛡️ Analyseur de Plannings & Disponibilités")
st.markdown("Suivi des vacations, cumuls journaliers et jours de repos (Contrainte 10h/jour max).")

# --- SECTION 1 : Importation des fichiers ---
st.sidebar.header("📁 Importer les fichiers")
uploaded_contrats = st.sidebar.file_uploader("Fichier des contrats (.xlsx)", type=["xlsx"])
uploaded_pdfs = st.sidebar.file_uploader("Plannings PDF (Plusieurs semaines acceptés)", type=["pdf"], accept_multiple_files=True)

if uploaded_contrats and uploaded_pdfs:
    # 1. Lecture du fichier Excel des contrats
    df_contrats = pd.read_excel(uploaded_contrats)
    contrat_map = {}
    for _, row in df_contrats.iterrows():
        # Recherche flexible des colonnes nom et contrat
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
            
            # Recherche des horaires (ex: 03:15 09:10 ou 03h15 - 09:10)
            horaires_match = re.findall(r'([0-2]?[0-9])[:h]([0-5][0-9])\s*(?:-|à)?\s*([0-2]?[0-9])[:h]([0-5][0-9])', text)
            
            horaires_formates = []
            total_minutes = 0
            
            for h1, m1, h2, m2 in horaires_match:
                deb_min = int(h1) * 60 + int(m1)
                fin_min = int(h2) * 60 + int(m2)
                dur = fin_min - deb_min
                if dur < 0: 
                    dur += 24 * 60
                total_minutes += dur
                horaires_formates.append(f"{h1.zfill(2)}:{m1} à {h2.zfill(2)}:{m2}")
            
            total_heures_dec = round(total_minutes / 60, 2)
            
            # Détection des sites
            site_match = re.findall(r'XVIII\s+[A-Z0-9\s–-]+', text)
            site_nom = site_match[0] if site_match else "ADT FIL – INTERNATIONAL BS"
            
            # Vérification repos
            is_repos = (len(horaires_formates) == 0) or ("REPOS" in text.upper())
            
            if dates_uniques:
                for date_agent in dates_uniques:
                    parsed_data.append({
                        'Agent': agent_name,
                        'Type Contrat': type_contrat,
                        'Date': date_agent,
                        'Site / Affectation': "—" if is_repos else site_nom,
                        'Horaires Vacation(s)': "Case vide (Repos)" if is_repos else " / ".join(horaires_formates),
                        'Total Heures': "0.00h" if is_repos else f"{total_heures_dec}h",
                        '_is_repos': is_repos,
                        '_heures_val': total_heures_dec
                    })
            else:
                parsed_data.append({
                    'Agent': agent_name,
                    'Type Contrat': type_contrat,
                    'Date': 'Période globale',
                    'Site / Affectation': site_nom,
                    'Horaires Vacation(s)ɸ': " / ".join(horaires_formates) if horaires_formates else "Case vide (Repos)",
                    'Total Heures': f"{total_heures_dec}h",
                    '_is_repos': is_repos,
                    '_heures_val': total_heures_dec
                })

    df_result = pd.DataFrame(parsed_data)

    if not df_result.empty:
        # --- SECTION 2 : Filtres de visualisation ---
        st.markdown("---")
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            selected_agent = st.selectbox("Filtrer par Agent :", ["Tous"] + sorted(list(agents_list)))
        with col_f2:
            selected_statut = st.selectbox("Filtrer par Statut :", ["Tous", "Jours de Repos uniquement", "Jours Travaillés uniquement"])

        # Application des filtres
        df_filtered = df_result.copy()
        if selected_agent != "Tous":
            df_filtered = df_filtered[df_filtered['Agent'] == selected_agent]
        if selected_statut == "Jours de Repos uniquement":
            df_filtered = df_filtered[df_filtered['_is_repos'] == True]
        elif selected_statut == "Jours Travaillés uniquement":
            df_filtered = df_filtered[df_filtered['_is_repos'] == False]

        # Suppression des colonnes techniques internes pour l'affichage
        df_display = df_filtered.drop(columns=['_is_repos', '_heures_val'])

        st.subheader(f"📋 Synthèse des Journées ({len(df_display)} lignes)")
        st.dataframe(df_display, use_container_width=True)

    else:
        st.warning("⚠️ Aucune donnée exploitable n'a pu être extraite des PDF.")

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** et vos **PDF de planning** dans le menu de gauche pour lancer l'application.")