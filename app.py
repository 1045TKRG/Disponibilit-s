import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Plages de Disponibilité Agents", layout="wide")

st.title("🛡️ Plages Globales de Disponibilité des Agents")
st.markdown("Affichage direct des fenêtres où les agents sont libres (Exclusion des CP, Malades et prise en compte des créneaux de repos).")

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
            
            # Exclusions strictes : Maladie ou CP
            is_maladie = bool(re.search(r'\b(MALADIE|MAL\.?)\b', text_upper))
            is_cp = bool(re.search(r'\b(CP|CONG[EÉ]S?)\b', text_upper))
            if is_maladie or is_cp:
                continue # On ignore complètement cet agent pour cette période

            # Recherche des dates (ex: Lundi 26/10 ou 26/10/2026)
            dates_trouvees = re.findall(r'(?:Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)?\s*([0-9]{2}/[0-9]{2}(?:/[0-9]{4})?)', text, re.IGNORECASE)
            dates_uniques = list(dict.fromkeys(dates_trouvees))
            
            # Recherche des horaires de travail (ex: 04h à 12h ou 04:00 - 12:00)
            horaires_match = re.findall(r'([0-2]?[0-9])\s*([h:])\s*([0-5][0-9])?\s*(?:-|à)\s*([0-2]?[0-9])\s*([h:])\s*([0-5][0-9])?', text, re.IGNORECASE)
            
            # Si format simple trouvé type 04h à 12h ou 04:00 - 12:00
            horaires_simples = re.findall(r'([0-2]?[0-9][h:][0-5]?[0-9]?)\s*(?:-|à)\s*([0-2]?[0-9][h:][0-5]?[0-9]?)', text, re.IGNORECASE)
            
            is_repos = bool(re.search(r'\b(REPOS|00:00\s*(?:-|à)\s*00:00)\b', text_upper))
            is_delegation = bool(re.search(r'D[EÉ]L[EÉ]GATION', text_upper))

            # Construction des plages de disponibilité globale
            if is_repos or (len(horaires_simples) == 0 and not is_delegation):
                dispo_texte = "🟢 Libre toute la journée (Repos 24h/24)"
            else:
                # S'il y a des vacations, on extrait les heures pour indiquer les dispos globales
                plages_str = []
                for h_debut, h_fin in horaires_simples:
                    plages_str.append(f"Travail de {h_debut} à {h_fin}")
                
                # Formulation claire des disponibilités globales de la journée
                horaires_txt = " et ".join([f"{h[0]} à {h[1]}" for h in horaires_simples])
                dispo_texte = f"🟢 Libre en dehors des vacations ({horaires_txt})"

            if dates_uniques:
                for date_agent in dates_uniques:
                    parsed_data.append({
                        'Agent': agent_name,
                        'Type Contrat': type_contrat,
                        'Date': date_agent,
                        'Plage de Disponibilité Globale': dispo_texte
                    })
            else:
                parsed_data.append({
                    'Agent': agent_name,
                    'Type Contrat': type_contrat,
                    'Date': 'Période globale',
                    'Plage de Disponibilité Globale': dispo_texte
                })

    df_result = pd.DataFrame(parsed_data)

    if not df_result.empty:
        # Nettoyage des doublons éventuels
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
        st.warning("⚠️ Aucune donnée exploitable trouvée (ou tous les agents sont en congés/maladie).")

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** et vos **PDF de planning** dans le menu de gauche.")