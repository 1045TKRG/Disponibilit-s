import streamlit as st
import pandas as pd
import pypdf
import re
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
    st.write("Veuillez vous identifier avec vos identifiants professionnels.")
    
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
# ONGLET 1 : DISPONIBILITÉS
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

    def decimal_to_hm(heures_dec):
        h = int(heures_dec)
        m = int(round((heures_dec - h) * 60))
        if m == 60:
            h += 1
            m = 0
        return f"{h}h{m:02d}"

    planning_agents = {}
    logs_debug = []

    def noms_sont_compatibles(excel_name, pdf_text):
        mots_excel = [w.upper() for w in re.findall(r'\w+', excel_name) if len(w) > 1]
        p_upper = pdf_text.upper()
        if not mots_excel:
            return False
        matches = sum(1 for mot in mots_excel if mot in p_upper)
        return matches >= 1

    if fichiers_planning:
        for fichier in fichiers_planning:
            match_semaine = re.search(r'S([0-9]{1,2})', fichier.name.upper())
            num_semaine = int(match_semaine.group(1)) if match_semaine else 43

            try:
                reader = pypdf.PdfReader(fichier)
                texte_global = "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])

                annee_ref = 2026
                start_target = datetime.fromisocalendar(annee_ref, num_semaine, 1)
                jours_semaine = [(start_target + timedelta(days=i)).strftime('%d/%m/%Y') for i in range(7)]

                for ex_agent in df_agents["Agent"].unique():
                    if not noms_sont_compatibles(ex_agent, texte_global):
                        continue

                    # Structure de base propre par défaut (Jour de repos initial)
                    semaine_agent = {j: {"statut": "REPOS", "heure_fin_reelle": "00:00", "duree_existante": 0.0} for j in jours_semaine}
                    cle_dict = f"{ex_agent}_S{num_semaine}"
                    planning_agents[cle_dict] = semaine_agent

            except Exception as e:
                logs_debug.append(f"Erreur fichier {fichier.name}: {e}")

    st.subheader("📋 Liste des Disponibilités & Opportunités")

    tableau_resultats = []
    tous_agents = df_agents[["Contrat", "Agent"]].drop_duplicates().to_dict(orient="records")
    semaines_tableau = [43, 44] if semaine_selectionnee == "Les deux" else [int(semaine_selectionnee.replace('S', ''))]

    for num_semaine in semaines_tableau:
        annee_ref = 2026
        start_target = datetime.fromisocalendar(annee_ref, num_semaine, 1)
        jours_defaut = [(start_target + timedelta(days=i)).strftime('%d/%m/%Y') for i in range(7)]

        for item in tous_agents:
            contrat_nom = item["Contrat"]
            agent_nom = item["Agent"]
            
            cle_dict = f"{agent_nom}_S{num_semaine}"
            matched_schedule = planning_agents.get(cle_dict)
                    
            if not matched_schedule:
                matched_schedule = {j: {"statut": "REPOS", "heure_fin_reelle": "00:00", "duree_existante": 0.0} for j in jours_defaut}

            for d in sorted(matched_schedule.keys(), key=lambda x: datetime.strptime(x, '%d/%m/%Y')):
                info_jour = matched_schedule[d]
                statut = info_jour["statut"]
                
                if statut == "REPOS":
                    creneau_texte = "Journée complète (00h00 - 24h00)"
                    opportunite = "🟢 Jour de Repos"
                else:
                    creneau_texte = "Créneau de travail"
                    opportunite = "Occupé"
                
                tableau_resultats.append({
                    "Semaine": f"S{num_semaine}",
                    "Contrat": contrat_nom,
                    "Agent": agent_nom,
                    "Date": d,
                    "Type d'opportunité": opportunite,
                    "Créneau horaire / Heures possibles": creneau_texte,
                    "Dernier recours": ""
                })

    if tableau_resultats:
        df_table = pd.DataFrame(tableau_resultats)
        edited_df = st.data_editor(
            df_table,
            column_config={
                "Dernier recours": st.column_config.TextColumn(
                    "Dernier recours (Saisie quotidienne)",
                    max_chars=150
                )
            },
            disabled=["Semaine", "Contrat", "Agent", "Date", "Type d'opportunité", "Créneau horaire / Heures possibles"],
            hide_index=True,
            key="editor_dispo"
        )
        
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
# AUTRES ONGLETS (CP & Maladies standards)
# ---------------------------------------------------------
with tab_cp:
    st.subheader("🏖️ Suivi des Congés Payés (CP)")
    st.data_editor(pd.DataFrame(columns=["Agent", "Date Début", "Date Fin", "Type de Congé", "Statut"]), num_rows="dynamic", key="cp_simple")

with tab_maladies:
    st.subheader("🏥 Suivi des Arrêts Maladie")
    st.data_editor(pd.DataFrame(columns=["Agent", "Date Début", "Date Fin", "Motif", "Commentaire"]), num_rows="dynamic", key="mal_simple")

with tab_cp_fin:
    st.subheader("🎄 CP Fêtes de Fin d'Année")
    st.data_editor(pd.DataFrame(columns=["Agent", "Date Début", "Date Fin", "Année"]), num_rows="dynamic", key="cp5_simple")

with tab_maladies_fin:
    st.subheader("🎄 Maladies Fêtes de Fin d'Année")
    st.data_editor(pd.DataFrame(columns=["Agent", "Date Début", "Date Fin", "Année", "Motif"]), num_rows="dynamic", key="mal5_simple")
