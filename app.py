import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Disponibilités Comète", layout="wide")

st.title("🛡️ Détecteur de Disponibilités (Spécial Export Comète)")
st.markdown("Analyse par capture de blocs de dates : idéal pour les exports PDF bruts et collés de Comète.")

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
            
            # Extraction du nom de l'agent (souvent présent au début du planning Comète)
            match_agent = re.search(r'Planning\s+(.*?)\s+par SITES', text, re.IGNORECASE)
            if not match_agent:
                match_agent = re.search(r'Agent\s*:\s*(.*?)(?=\s+du|\s+site|\n)', text, re.IGNORECASE)
            
            agent_name = match_agent.group(1).strip() if match_agent else "AGENT INCONNU"
            agents_list.add(agent_name)
            type_contrat = contrat_map.get(agent_name.upper(), "Non spécifié")
            
            text_upper = text.upper()
            
            # Exclusion globale de la page si l'agent est en arrêt maladie ou en congé payé sur toute la période
            if bool(re.search(r'\b(MALADIE|MAL\.?)\b', text_upper)) or bool(re.search(r'\b(CP|CONG[EÉ]S?)\b', text_upper)):
                # Note : Si c'est ponctuel dans le texte, le découpage par date gérera le détail, 
                # mais si c'est global, on peut laisser ou affiner. Restons sur le découpage par date :
                pass

            # DECOUPAGE PAR CAPTURE DE DATE : Sépare le texte exactement au niveau de chaque date (ex: 26/10/2026)
            # Les parenthèses dans re.split gardent la date dans la liste des morceaux résultants.
            date_pattern = r'([0-9]{2}/[0-9]{2}/[0-9]{4})'
            chunks = re.split(date_pattern, text)
            
            # chunks[0] = en-tête (Nom, site, etc.)
            # chunks[1] = date 1, chunks[2] = texte associé à la date 1
            # chunks[3] = date 2, chunks[4] = texte associé à la date 2, etc.
            i = 1
            while i < len(chunks) - 1:
                date_str = chunks[i].strip()
                block_text = chunks[i+1].upper()
                
                # Vérification si l'agent est en congé ou malade ce jour-là spécifiquement
                is_off = bool(re.search(r'\b(MALADIE|MAL\.?|CP|CONG[EÉ]S?)\b', block_text))
                if is_off:
                    i += 2
                    continue

                # Recherche d'horaires de travail dans ce bloc précis (ex: 03:15, 09:10, 03H15...)
                time_matches = re.findall(r'([0-2]?[0-9][:H][0-5][0-9])', block_text)
                valid_times = [t for t in time_matches if t != "00:00"]
                
                # S'il y a des horaires de travail valides dans ce bloc, l'agent travaille -> ON L'EXCLUT
                if len(valid_times) > 0:
                    i += 2
                    continue

                # S'il y a la mention "REPOS" ou aucun horaire de travail détecté dans ce bloc
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

        st.subheader(f"📋 Liste des Créneaux de Disponibilité ({len(df_filtered)} entrées)")
        st.dataframe(df_filtered, use_container_width=True)

    else:
        st.warning("⚠️ Aucun agent disponible trouvé (ou tous les agents travaillent/sont en congés).")

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** et vos **PDF de planning Comète** dans le menu de gauche.")