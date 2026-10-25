import streamlit as st
import pandas as pd
import pypdf
import re

st.set_page_config(page_title="Disponibilités Agents - Plages Libres", layout="wide")

st.title("🛡️ Table des Disponibilités Globales et Plages Libres")
st.markdown("Vue directe des jours de repos et des heures disponibles par jour pour chaque agent.")

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
            
            # Extraction des créneaux de travail
            horaires = re.findall(r'([0-9]{2}[h:][0-9]{2})\s*(?:-|à)\s*([0-9]{2}[h:][0-9]{2})', text)
            
            # Calcul direct des plages DE DISPONIBILITÉ (et non de service)
            if not horaires:
                dispo_detail = "🟢 LIBRE 24H/24 (Journée complète disponible)"
            else:
                plages_libres = []
                for idx, (debut, fin) in enumerate(horaires):
                    # Inversion des heures pour donner les créneaux libres
                    plages_libres.append(f"Disponible jusqu'à {debut} et à partir de {fin}")
                dispo_detail = " | ".join(plages_libres)

            agents_data.append({
                'Agent': agent_name,
                'Type de Contrat': type_contrat,
                'Disponibilités & Plages Libres': dispo_detail
            })

    df_result = pd.DataFrame(agents_data)

    st.success(f"Analyse réussie pour {len(df_result)} agents.")

    # --- SECTION 2 : Affichage du tableau nettoyé ---
    st.subheader("📋 Tableau Synthétique des Disponibilités")
    
    selected_contrat = st.selectbox("Filtrer par type de contrat :", ["Tous"] + list(df_contrats['Contrats'].dropna().unique()))
    
    if selected_contrat != "Tous":
        df_filtered = df_result[df_result['Type de Contrat'] == selected_contrat]
    else:
        df_filtered = df_result

    # Affichage du tableau sans colonne de source/fichier
    st.dataframe(df_filtered, use_container_width=True)

else:
    st.warning("⚠️ Veuillez importer votre fichier **contrats.xlsx** et vos **PDF de planning** dans le menu de gauche.")