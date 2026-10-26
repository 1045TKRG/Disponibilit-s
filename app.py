import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Disponibilités des Agents", layout="wide")

st.title("🛡️ Table des Agents Disponibles")
st.markdown("Analyse robuste par détection de ligne : séparation nette entre les jours de travail et les jours de repos.")

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

            # Comme le texte peut être collé, on cherche toutes les occurrences de dates associées à leur contexte immédiat
            # On recherche un motif type "JJ/MM/AAAA" ou "JJ/MM"
            date_matches = list(re.finditer(r'([0-9]{2}/[0-9]{2}(?:/[0-9]{4})?)', text))
            
            for m in date_matches:
                date_str = m.group(1)
                # On extrait un extrait de texte autour de la date (environ 100 caractères après) pour voir ce qu'il y a ce jour-là
                start_snippet = m.end()
                snippet = text[start_snippet:start_snippet + 120].upper()
                
                # Vérifications d'absence (Maladie, CP) dans l'extrait
                if re.search(r'\b(MALADIE|MAL\.?|CP|CONG[EÉ]S?)\b', snippet):
                    continue

                # Recherche d'horaires de travail dans l'extrait (ex: 03:15, 09:10, 04h-12h)
                time_matches = re.findall(r'([0-2]?[0-9][:h][0-5][0-9])', snippet)
                valid_times = [t for t in time_matches if t != "00:00"]
                
                # S'il y a des horaires de travail, l'agent travaille ce jour-là -> ON L'EXCLUT STRICTEMENT
                if len(valid_times) > 0:
                    continue

                # Si c'est explicitement un repos ou qu'aucun horaire de travail n'est détecté
                is_repos = bool(re.search(r'\b(REPOS)\b', snippet))
                
                # On valide uniquement si c'est un vrai repos ou un jour vide de travail
                if is_repos or len(valid_times) == 0:
                    parsed_data.append({
                        'Agent': agent_name,
                        'Type Contrat': type_contrat,
                        'Date': date_str,
                        'Disponibilité': '🟢 Disponible toute la journée (00:00 à 24:00)'
                    })

    df_result = pd.DataFrame(parsed_data)

    if not df_result.empty:
        # Nettoyage strict des doublons (nécessaire avec la recherche par snippet)
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
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** et vos **PDF de planning** dans le menu de gauche.")