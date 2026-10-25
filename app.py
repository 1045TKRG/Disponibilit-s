import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Suivi Plannings & Disponibilités - Sécurité", layout="wide")

st.title("🛡️ Gestion des Plannings & Disponibilités - Règles Sûreté")
st.markdown("Plateforme de calcul des temps de travail (Plafond 48h, Repos 11h, Max 10h/jour).")

# --- SECTION 1 : Importation des fichiers ---
st.sidebar.header("📁 Importer les fichiers")
uploaded_contrats = st.sidebar.file_uploader("Fichier des contrats (.xlsx)", type=["xlsx"])
uploaded_pdfs = st.sidebar.file_uploader("Plannings PDF (Plusieurs semaines acceptés)", type=["pdf"], accept_multiple_files=True)

if uploaded_contrats and uploaded_pdfs:
    # 1. Lecture du fichier Excel des contrats
    df_contrats = pd.read_excel(uploaded_contrats)
    contrat_map = dict(zip(df_contrats['NOM / PRENOM'].astype(str).str.strip(), df_contrats['Contrats']))

    agents_data = []

    # 2. Boucle sur chaque fichier PDF importé
    for pdf_file in uploaded_pdfs:
        reader = pypdf.PdfReader(pdf_file)
        
        for page in reader.pages:
            text = page.extract_text()
            
            # Extraire Nom / Prénom de l'agent
            match_agent = re.search(r'Planning\s+(.*?)\s+par SITES', text)
            if not match_agent:
                continue
            agent_name = match_agent.group(1).strip()
            type_contrat = contrat_map.get(agent_name, "Non spécifié")
            
            # Recherche des plages horaires de type 03h15, 09:10, etc.
            # On cherche par exemple des formats comme "03h15 - 09:10" ou similaires dans le texte
            horaires_trouves = re.findall(r'([0-9]{2}[h:][0-9]{2})\s*(?:-|à)\s*([0-9]{2}[h:][0-9]{2})', text)
            
            agents_data.append({
                'Agent': agent_name,
                'Type de Contrat': type_contrat,
                'Fichier Source': pdf_file.name,
                'Horaires Détectés': horaires_trouves if horaires_trouves else ["Aucun horaire brut détecté"]
            })

    df_result = pd.DataFrame(agents_data)

    st.success(f"✅ Analyse réussie de {len(uploaded_pdfs)} fichier(s) PDF.")

    # --- SECTION 2 : Affichage et Filtres ---
    st.subheader("📋 Synthèse des agents et plannings extraits")
    
    selected_contrat = st.selectbox("Filtrer par type de contrat :", ["Tous"] + list(df_contrats['Contrats'].dropna().unique()))
    
    if selected_contrat != "Tous":
        df_filtered = df_result[df_result['Type de Contrat'] == selected_contrat]
    else:
        df_filtered = df_result

    st.dataframe(df_filtered, use_container_width=True)

    # --- SECTION 3 : Module de vérification pour vol supplémentaire ---
    st.markdown("---")
    st.subheader("✈️ Vérification d'éligibilité pour un vol supplémentaire")
    st.info(f"Règles actives : Max 48h/semaine (cumul inclus) | Repos inter-jours >= 11h | Max 10h/jour.")
    
    col1, col2 = st.columns(2)
    with col1:
        date_vol = st.date_input("Date du vol supplémentaire")
    with col2:
        agent_selectionne = st.selectbox("Sélectionner un agent à tester :", df_result['Agent'].unique() if not df_result.empty else [])

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** ET au moins un **planning PDF** dans le menu de gauche.")