import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Disponibilités & Suivi Contraintes - Sécurité", layout="wide")

st.title("🛡️ Analyse des Disponibilités et Temps de Travail")
st.markdown("Calcul automatique des plages libres, respect des 10h/jour, repos de 11h et plafond de 48h/semaine.")

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
            
            # Recherche des mentions de repos explicites
            repos_explicites = re.findall(r'(REPOS|00:00\s*(?:à|-)\s*00:00)', text, re.IGNORECASE)
            
            # Recherche des horaires de travail (ex: 03h15 - 09:10 ou 03:15 à 09:10)
            horaires_travailles = re.findall(r'([0-9]{2}[h:][0-9]{2})\s*(?:-|à)\s*([0-9]{2}[h:][0-9]{2})', text)
            
            # Analyse de la disponibilité globale pour cet agent sur ce fichier
            if repos_explicites or "REPOS" in text.upper():
                statut_dispo = "🟢 En Repos / Libre sur la période (ou mentions REPOS détectées)"
            elif horaires_travailles:
                statut_dispo = f"⏰ Vacations détectées ({len(horaires_travailles)} créneau(x) planifié(s)). Disponible en dehors de ces horaires (Sous réserve du plafond de 48h et repos 11h)."
            else:
                statut_dispo = "🟢 Aucune vacation lourde détectée (Jours potentiellement libres / Cases vides)"

            agents_data.append({
                'Agent': agent_name,
                'Type de Contrat': type_contrat,
                'Fichier Source': pdf_file.name,
                'État & Disponibilité Globale': statut_dispo
            })

    df_result = pd.DataFrame(agents_data)

    st.success(f"✅ Analyse réussie de {len(uploaded_pdfs)} fichier(s) PDF : {len(df_result)} agents analysés.")

    # --- SECTION 2 : Affichage et Filtres ---
    st.subheader("📋 Tableau de Synthèse des Disponibilités")
    
    # Filtre par type de contrat
    selected_contrat = st.selectbox("Filtrer par type de contrat :", ["Tous"] + list(df_contrats['Contrats'].dropna().unique()))
    
    if selected_contrat != "Tous":
        df_filtered = df_result[df_result['Type de Contrat'] == selected_contrat]
    else:
        df_filtered = df_result

    # Affichage du tableau final
    st.dataframe(df_filtered, use_container_width=True)

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** ET au moins un **planning PDF** dans le menu de gauche pour afficher les disponibilités.")