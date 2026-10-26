import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Disponibilités Journalières Précises", layout="wide")

st.title("🛡️ Analyseur de Disponibilités par Jour")
st.markdown("Découpage strict par date : chaque jour est analysé indépendamment (Exclusion des CP, Malades et calcul des fenêtres libres).")

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
            
            # Exclusions globales page entière : Maladie ou CP global
            is_maladie_global = bool(re.search(r'\b(MALADIE|MAL\.?)\b', text_upper))
            is_cp_global = bool(re.search(r'\b(CP|CONG[EÉ]S?)\b', text_upper))
            if is_maladie_global or is_cp_global:
                continue # On ignore cet agent si arrêté/congés sur la page

            # DÉCOUPAGE CHIRURGICAL PAR DATE : On sépare le texte autour de chaque date
            date_pattern = r'((?:Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)?\s*[0-9]{2}/[0-9]{2}(?:/[0-9]{4})?)'
            parts = re.split(date_pattern, text, flags=re.IGNORECASE)

            if len(parts) > 1:
                # On parcourt les morceaux par paires (Date + Bloc de texte associé à cette date)
                i = 1
                while i < len(parts) - 1:
                    date_str = parts[i].strip()
                    chunk_text = parts[i+1].strip().upper()
                    
                    # Analyse spécifique de ce bloc de date
                    is_repos = bool(re.search(r'\b(REPOS|00:00\s*(?:-|à)\s*00:00)\b', chunk_text))
                    is_maladie_jour = bool(re.search(r'\b(MALADIE|MAL\.?)\b', chunk_text))
                    is_cp_jour = bool(re.search(r'\b(CP|CONG[EÉ]S?)\b', chunk_text))
                    
                    # Si l'agent est en congé ou malade ce jour-là, on l'exclut pour cette date
                    if is_maladie_jour or is_cp_jour:
                        i += 2
                        continue

                    # Recherche des horaires dans ce bloc précis
                    horaires_trouves = re.findall(r'([0-2]?[0-9][h:][0-5][0-9])\s*(?:-|à)\s*([0-2]?[0-9][h:][0-5][0-9])', chunk_text)
                    
                    if is_repos or len(horaires_trouves) == 0:
                        dispo_texte = "🟢 Disponible toute la journée (00:00 à 24:00)"
                    else:
                        shifts_str = " et ".join([f"{h[0]} à {h[1]}" for h in horaires_trouves])
                        dispo_texte = f"🟢 Libre en dehors des vacations ({shifts_str})"

                    parsed_data.append({
                        'Agent': agent_name,
                        'Type Contrat': type_contrat,
                        'Date': date_str,
                        'Plage de Disponibilité': dispo_texte
                    })
                    i += 2
            else:
                # Si aucune date n'a pu être isolée par le découpage
                horaires_global = re.findall(r'([0-2]?[0-9][h:][0-5][0-9])\s*(?:-|à)\s*([0-2]?[0-9][h:][0-5][0-9])', text)
                dispo_fallback = "🟢 Disponible toute la journée" if not horaires_global else f"🟢 Libre hors vacations ({', '.join([h[0]+'à'+h[1] for h in horaires_global])})"
                parsed_data.append({
                    'Agent': agent_name,
                    'Type Contrat': type_contrat,
                    'Date': 'Période globale',
                    'Plage de Disponibilité': dispo_fallback
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
        st.warning("⚠️ Aucune donnée exploitable trouvée (ou agents en congés/maladie).")

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** et vos **PDF de planning** dans le menu de gauche.")