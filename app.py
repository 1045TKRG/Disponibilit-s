import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Suivi Vacations & Disponibilités", layout="wide")

st.title("🛡️ Suivi des Vacations et Disponibilités par Agent")
st.markdown("Distinction claire entre les heures de travail planifiées et les vraies disponibilités.")

# --- SECTION 1 : Importation ---
st.sidebar.header("📁 Importer les fichiers")
uploaded_contrats = st.sidebar.file_uploader("Fichier des contrats (.xlsx)", type=["xlsx"])
uploaded_pdfs = st.sidebar.file_uploader("Plannings PDF (Plusieurs semaines acceptés)", type=["pdf"], accept_multiple_files=True)

if uploaded_contrats and uploaded_pdfs:
    # 1. Lecture des contrats
    df_contrats = pd.read_excel(uploaded_contrats)
    contrat_map = dict(zip(df_contrats['NOM / PRENOM'].astype(str).str.strip(), df_contrats['Contrats']))

    agents_data = []

    # 2. Analyse des PDF
    for pdf_file in uploaded_pdfs:
        reader = pypdf.PdfReader(pdf_file)
        
        for page in reader.pages:
            text = page.extract_text()
            
            # Extraire le nom de l'agent
            match_agent = re.search(r'Planning\s+(.*?)\s+par SITES', text)
            if not match_agent:
                continue
            agent_name = match_agent.group(1).strip()
            type_contrat = contrat_map.get(agent_name, "Non spécifié")
            
            # Trouver toutes les dates sur la page
            dates_trouvees = re.findall(r'([0-9]{2}/[0-9]{2}/[0-9]{4})', text)
            dates_uniques = list(dict.fromkeys(dates_trouvees))
            
            # Vérifier s'il y a un repos explicite
            is_repos = bool(re.search(r'(REPOS|00:00\s*(?:-|à)\s*00:00)', text, re.IGNORECASE))
            
            # Trouver les vraies heures de travail (vacations)
            horaires_travail = re.findall(r'([0-9]{2}[h:][0-9]{2})\s*(?:-|à)\s*([0-9]{2}[h:][0-9]{2})', text)
            
            if dates_uniques:
                for date_agent in dates_uniques:
                    if is_repos and not horaires_travail:
                        travail_texte = "Jour de Repos"
                        dispo_texte = "🟢 Entièrement disponible (Repos)"
                    elif horaires_travail:
                        shifts = ", ".join([f"{h[0]} à {h[1]}" for h in horaires_travail])
                        travail_texte = f"En service : {shifts}"
                        dispo_texte = "⏰ Libre en dehors des horaires de service"
                    else:
                        travail_texte = "Aucune vacation"
                        dispo_texte = "🟢 Entièrement disponible"
                    
                    agents_data.append({
                        'Agent': agent_name,
                        'Type de Contrat': type_contrat,
                        'Date': date_agent,
                        'Vacations (Travail)': travail_texte,
                        'Disponibilité': dispo_texte
                    })
            else:
                agents_data.append({
                    'Agent': agent_name,
                    'Type de Contrat': type_contrat,
                    'Date': 'Période globale',
                    'Vacations (Travail)': 'Voir planning détaillé',
                    'Disponibilité': 'À vérifier'
                })

    df_result = pd.DataFrame(agents_data)
    # Nettoyage des doublons éventuels
    df_result = df_result.drop_duplicates().reset_index(drop=True)

    st.success(f"✅ Analyse réussie : {len(df_result)} lignes générées.")

    # --- SECTION 2 : Affichage du tableau ---
    st.subheader("📋 Tableau de Suivi (Travail vs Disponibilité)")
    
    selected_contrat = st.selectbox("Filtrer par type de contrat :", ["Tous"] + list(df_contrats['Contrats'].dropna().unique()))
    
    if selected_contrat != "Tous":
        df_filtered = df_result[df_result['Type de Contrat'] == selected_contrat]
    else:
        df_filtered = df_result

    # Affichage du tableau propre
    st.dataframe(df_filtered, use_container_width=True)

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** et vos **PDF de planning** dans le menu de gauche.")