import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO

# Configuration de la page
st.set_page_config(
    page_title="SOS Remplacement - Portails RH",
    page_icon="🔒",
    layout="wide"
)

# ---------------------------------------------------------
# SÉCURITÉ : GESTION DES UTILISATEURS & MOTS DE PASSE
# ---------------------------------------------------------
UTILISATEURS_AUTORISES = {
    "admin": {"mdp": "SOS2026", "role": "Administrateur unique"},
    "hinerava": {"mdp": "Hinerava2360", "role": "Planificatrice"},
    "hoania": {"mdp": "Hoania2581", "role": "Planificateur"}
}

if "authentifie" not in st.session_state:
    st.session_state["authentifie"] = False
if "utilisateur_connecte" not in st.session_state:
    st.session_state["utilisateur_connecte"] = ""
if "role_utilisateur" not in st.session_state:
    st.session_state["role_utilisateur"] = ""

if not st.session_state["authentifie"]:
    st.title("🔒 Accès Sécurisé — Portail RH & Plannings")
    st.write("Ce portail contient des données confidentielles. Veuillez vous identifier.")
    
    with st.form("form_connexion"):
        username_saisi = st.text_input("Identifiant :").strip().lower()
        password_saisi = st.text_input("Mot de passe :", type="password")
        submit_btn = st.form_submit_button("Se connecter")
        
        if submit_btn:
            if username_saisi in UTILISATEURS_AUTORISES and UTILISATEURS_AUTORISES[username_saisi]["mdp"] == password_saisi:
                st.session_state["authentifie"] = True
                st.session_state["utilisateur_connecte"] = username_saisi
                st.session_state["role_utilisateur"] = UTILISATEURS_AUTORISES[username_saisi]["role"]
                st.success(f"Connexion réussie. Bienvenue, {username_saisi.capitalize()} !")
                st.rerun()
            else:
                st.error("Identifiant ou mot de passe incorrect.")
                
    st.stop()

# ---------------------------------------------------------
# INTERFACE PRINCIPALE
# ---------------------------------------------------------
col_titre, col_deco = st.columns([4, 1])
with col_titre:
    st.title("🚨 SOS Remplacement — Portail de Gestion")
    st.caption(f"Connecté en tant que : **{st.session_state['utilisateur_connecte']}** ({st.session_state['role_utilisateur']})")
with col_deco:
    if st.button("🔒 Déconnexion"):
        st.session_state["authentifie"] = False
        st.rerun()

st.markdown("---")

# Création des onglets
tab_dispo, tab_cp, tab_maladies, tab_cp_fin, tab_maladies_fin = st.tabs([
    "📋 Disponibilités & Remplacements", 
    "🏖️ Congés Payés & Analyses", 
    "🏥 Maladies & Analyses",
    "🎄 CP Fêtes de Fin d'Année (5 ans)",
    "🎄 Maladies Fêtes de Fin d'Année (5 ans)"
])

# ---------------------------------------------------------
# ONGLET 1 : DISPONIBILITÉS (TABLEAU INTERACTIF RAPIDE)
# ---------------------------------------------------------
with tab_dispo:
    st.sidebar.header("📁 Données de la Semaine (Dispo)")
    uploaded_excel = st.sidebar.file_uploader(
        "1. Fichier Référentiel Agents (.xlsx)", 
        type=["xlsx", "xls"],
        key="excel_dispo"
    )
    fichiers_planning = st.sidebar.file_uploader(
        "2. Plannings PDF Comète (Multi-contrats)", 
        type=["pdf"], 
        accept_multiple_files=True,
        key="pdf_dispo"
    )

    def charger_referentiel(excel_file):
        try:
            df_raw = pd.read_excel(excel_file, header=None)
            df_raw[0] = df_raw[0].ffill()
            
            donnees_traitees = []
            site_actuel = ""
            
            for idx, row in df_raw.iterrows():
                val_col_a = str(row[0]).strip() if pd.notna(row[0]) else ""
                if val_col_a.upper() in ["SITES", "SITE", "NAN", "", "CONTRATS", "CONTRAT"]:
                    continue
                site_actuel = val_col_a
                
                for col_idx in range(1, len(row)):
                    agent_nom = str(row[col_idx]).strip() if pd.notna(row[col_idx]) else ""
                    if agent_nom and agent_nom.upper() not in ["NAN", "NOM / PRENOM", "AGENT"]:
                        donnees_traitees.append({
                            "Contrat": site_actuel,
                            "Agent": agent_nom
                        })
            return pd.DataFrame(donnees_traitees), None
        except Exception as e:
            return None, f"Erreur Excel : {e}"

    if not uploaded_excel:
        st.warning("⚠️ Veuillez importer le fichier **referentiel_agents.xlsx** dans le menu de gauche pour démarrer.")
        st.stop()

    df_agents, erreur = charger_referentiel(uploaded_excel)
    if erreur:
        st.error(f"⚠️ {erreur}")
        st.stop()

    semaine_selectionnee = st.sidebar.selectbox("3. Semaine à afficher en priorité", ["S43", "S44", "Les deux"], key="semaine_dispo")

    st.subheader("📋 Tableau de Suivi des Disponibilités & Remplacements")
    st.info("💡 **Mode Rapide :** Référentiel chargé avec succès. Ajustez directement les statuts ou horaires si besoin dans le tableau ci-dessous, puis téléchargez votre rapport.")

    tableau_resultats = []
    tous_agents = df_agents[["Contrat", "Agent"]].drop_duplicates().to_dict(orient="records")
    semaines_tableau = [43, 44] if semaine_selectionnee == "Les deux" else [int(semaine_selectionnee.replace('S', ''))]

    for num_semaine in semaines_tableau:
        annee_ref = 2026
        try:
            start_target = datetime.fromisocalendar(annee_ref, num_semaine, 1)
        except Exception:
            jan4 = datetime(annee_ref, 1, 4)
            start_week1 = jan4 - timedelta(days=jan4.weekday())
            start_target = start_week1 + timedelta(weeks=num_semaine - 1)
        
        jours_defaut = [(start_target + timedelta(days=i)).strftime('%d/%m/%Y') for i in range(7)]

        for item in tous_agents:
            contrat_nom = item["Contrat"]
            agent_nom = item["Agent"]
            
            for d in jours_defaut:
                tableau_resultats.append({
                    "Semaine": f"S{num_semaine}",
                    "Contrat": contrat_nom,
                    "Agent": agent_nom,
                    "Date": d,
                    "Statut / Disponibilité": "🟢 Jour de Repos",
                    "Créneaux / Horaires de remplacement": "Journée complète (00h00 - 24h00)",
                    "Dernier recours": ""
                })

    if tableau_resultats:
        df_table = pd.DataFrame(tableau_resultats)
        edited_df = st.data_editor(
            df_table,
            column_config={
                "Statut / Disponibilité": st.column_config.SelectboxColumn(
                    "Statut / Disponibilité",
                    options=["🟢 Jour de Repos", "🟡 Partiellement disponible", "🔴 Occupé / Travaillé", "Remplacé"],
                    required=True
                ),
                "Créneaux / Horaires de remplacement": st.column_config.TextColumn(
                    "Créneaux / Horaires de remplacement",
                    max_chars=150
                ),
                "Dernier recours": st.column_config.TextColumn(
                    "Dernier recours",
                    max_chars=150
                )
            },
            disabled=["Semaine", "Contrat", "Agent", "Date"],
            hide_index=True,
            key="editor_dispo_rapide"
        )
        
        st.markdown("---")
        col1, col2 = st.columns([2, 1])
        with col1:
            st.success("✅ Saisie rapide opérationnelle.")
        with col2:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                edited_df.to_excel(writer, index=False, sheet_name='Disponibilites_Remplacements')
            
            st.download_button(
                label="📥 Télécharger le rapport (Excel)",
                data=output.getvalue(),
                file_name=f"Rapport_Disponibilites_{datetime.now().strftime('%Y-%m-%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# ---------------------------------------------------------
# AUTRES ONGLETS
# ---------------------------------------------------------
with tab_cp:
    st.subheader("🏖️ Suivi des Congés Payés (CP)")
    st.data_editor(pd.DataFrame(columns=["Agent", "Date Début", "Date Fin", "Type de Congé", "Statut"]), num_rows="dynamic", key="cp_simple")

with tab_maladies:
    st.subheader("🏥 Suivi des Arrêts Maladie")
    st.data_editor(pd.DataFrame(columns=["Agent", "Date Début", "Date Fin", "Motif", "Commentaire"]), num_rows="dynamic", key="mal_simple")

with tab_cp_fin:
    st.subheader("🎄 CP Fêtes de Fin d'Année (5 ans)")
    st.data_editor(pd.DataFrame(columns=["Agent", "Date Début", "Date Fin", "Année"]), num_rows="dynamic", key="cp5_simple")

with tab_maladies_fin:
    st.subheader("🎄 Maladies Fêtes de Fin d'Année (5 ans)")
    st.data_editor(pd.DataFrame(columns=["Agent", "Date Début", "Date Fin", "Année", "Motif"]), num_rows="dynamic", key="mal5_simple")
