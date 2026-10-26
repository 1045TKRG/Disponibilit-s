import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Disponibilités Comète - Debug", layout="wide")

st.title("🛡️ Détecteur de Disponibilités (Mode Diagnostic Comète)")
st.markdown("Analyse robuste avec affichage du texte brut pour comprendre l'extraction de Comète.")

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
        
        full_extracted_text = ""
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                full_extracted_text += f"\n--- PAGE {page_num+1} ---\n" + text

        # SECTION DEBUG VISIBLE : Permet de voir ce que lit le script dans le PDF
        with st.expander(f"🔍 Voir le texte brut extrait du PDF : {pdf_file.name}"):
            st.text(full_extracted_text[:3000] + ("\n[... Texte tronqué pour affichage ...]" if len(full_extracted_text) > 3000 else ""))

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

            # Découpage du texte en morceaux autour de chaque date (JJ/MM/AAAA ou JJ/MM)
            date_pattern = r'([0-9]{2}/[0-9]{2}(?:/[0-9]{4})?)'
            parts = re.split(date_pattern, text)

            # parts[0] = en-tête, parts[1] = date 1, parts[2] = texte après date 1, etc.
            i = 1
            while i < len(parts) - 1:
                date_str = parts[i].strip()
                block_text = parts[i+1].upper()
                
                # Vérifications d'absence
                if re.search(r'\b(MALADIE|MAL\.?|CP|CONG[EÉ]S?)\b', block_text):
                    i += 2
                    continue

                # Recherche d'horaires de travail dans ce bloc précis
                time_matches = re.findall(r'([0-2]?[0-9][:H][0-5][0-9])', block_text)
                valid_times = [t for t in time_matches if t != "00:00"]
                
                # S'il y a des horaires de travail dans ce bloc, l'agent TRAVAILLE -> ON EXCLUT STRICTEMENT
                if len(valid_times) > 0:
                    i += 2
                    continue

                # Si le bloc contient explicitement "REPOS" ou s'il n'y a aucun horaire détecté
                is_repos = bool(re.search(r'\b(REPOS)\b', block_text))
                
                if is_repos or len(valid_times) == 0:
                    parsed_data.append({
                        'Agent': agent_name,
                        'Type Contrat': type_contrat,
                        'Date': date_str,
                        'Disponibilité': '🟢 Disponible toute la journée (00:00 à 24:00)'
                    })
                
                i += 2

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
        st.warning("⚠️ Aucun agent disponible trouvé (ou tous les agents travaillent/sont en congés).")

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** et vos **PDF de planning Comète** dans le menu de gauche.")