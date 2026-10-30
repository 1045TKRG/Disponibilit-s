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

    st.subheader("📋 Tableau de Suivi des Disponibilités & Remplacements")
    st.info("💡 Saisissez directement le statut, les horaires ou les notes de remplacement pour chaque agent jour par jour.")

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
                    "Statut / Disponibilité": "🟢 Jour de Repos / Disponible",
                    "Créneaux / Horaires de remplacement": ""
                })

    if tableau_resultats:
        df_table = pd.DataFrame(tableau_resultats)
        edited_df = st.data_editor(
            df_table,
            column_config={
                "Créneaux / Horaires de remplacement": st.column_config.TextColumn(
                    "Créneaux / Horaires de remplacement",
                    help="Saisir les horaires (ex: 07:40 - 00:00) ou commentaires",
                    max_chars=200
                ),
                "Statut / Disponibilité": st.column_config.SelectboxColumn(
                    "Statut / Disponibilité",
                    options=[
                        "🟢 Jour de Repos / Disponible", 
                        "🟡 Partiellement disponible", 
                        "🔴 Occupé / Travaillé", 
                        "Remplacé"
                    ],
                    required=True
                )
            },
            disabled=["Semaine", "Contrat", "Agent", "Date"],
            hide_index=True,
            key="editor_dispo_stable"
        )
        
        st.markdown("---")
        col1, col2 = st.columns([2, 1])
        with col1:
            st.success("✅ Tableau interactif prêt et stable pour la gestion de vos plannings.")
        with col2:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                edited_df.to_excel(writer, index=False, sheet_name='Disponibilites_Remplacements')
            processed_data = output.getvalue()
            
            st.download_button(
                label="📥 Télécharger le rapport (Excel)",
                data=processed_data,
                file_name=f"Rapport_Disponibilites_{datetime.now().strftime('%Y-%m-%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# ---------------------------------------------------------
# ONGLET 2 : CONGÉS PAYÉS & ANALYSES
# ---------------------------------------------------------
with tab_cp:
    st.subheader("🏖️ Suivi des Congés Payés (CP) & Tableau d'Analyse")
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        f_cp_excel = st.file_uploader("Importer un fichier Excel (CP)", type=["xlsx", "xls"], key="up_cp_excel")
    with col_up2:
        f_cp_pdf = st.file_uploader("Importer un fichier PDF (CP)", type=["pdf"], key="up_cp_pdf")
        
    data_cp_defaut = pd.DataFrame(columns=["Agent", "Date Début", "Date Fin", "Type de Congé", "Statut"])
    if f_cp_excel:
        try:
            data_cp_defaut = pd.read_excel(f_cp_excel)
        except Exception as e:
            st.error(f"Erreur : {e}")

    edited_cp = st.data_editor(
        data_cp_defaut,
        num_rows="dynamic",
        hide_index=True,
        key="editor_cp_interactif",
        column_config={
            "Statut": st.column_config.SelectboxColumn(
                "Statut",
                options=["Demandé", "Validé", "Refusé"],
                required=True
            )
        }
    )
    
    st.markdown("---")
    st.subheader("📊 Tableau d'Analyse — Congés Payés")
    if not edited_cp.empty and "Statut" in edited_cp.columns:
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Total Demandes CP", len(edited_cp))
        col_m2.metric("Congés Validés", len(edited_cp[edited_cp["Statut"] == "Validé"]))
        col_m3.metric("En attente", len(edited_cp[edited_cp["Statut"] == "Demandé"]))
        
        df_analyse_cp = edited_cp["Statut"].value_counts().reset_index()
        df_analyse_cp.columns = ["Statut", "Nombre"]
        st.dataframe(df_analyse_cp, hide_index=True)
        st.bar_chart(df_analyse_cp.set_index("Statut"))
    else:
        st.info("Ajoutez des données dans le tableau ci-dessus pour afficher l'analyse.")

    if not edited_cp.empty:
        output_cp = BytesIO()
        with pd.ExcelWriter(output_cp, engine='openpyxl') as writer:
            edited_cp.to_excel(writer, index=False, sheet_name='Conges_Payes')
        st.download_button(
            label="📥 Télécharger le suivi des CP (Excel)",
            data=output_cp.getvalue(),
            file_name=f"Suivi_Conges_Payes_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ---------------------------------------------------------
# ONGLET 3 : MALADIES & ANALYSES
# ---------------------------------------------------------
with tab_maladies:
    st.subheader("🏥 Suivi des Arrêts Maladie & Tableau d'Analyse")
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        f_mal_excel = st.file_uploader("Importer un fichier Excel (Maladies)", type=["xlsx", "xls"], key="up_mal_excel")
    with col_m2:
        f_mal_pdf = st.file_uploader("Importer un fichier PDF (Maladies / Justificatif)", type=["pdf"], key="up_mal_pdf")
        
    data_mal_defaut = pd.DataFrame(columns=["Agent", "Date Début", "Date Fin", "Motif / Justificatif", "Commentaire"])
    if f_mal_excel:
        try:
            data_mal_defaut = pd.read_excel(f_mal_excel)
        except Exception as e:
            st.error(f"Erreur : {e}")

    edited_maladies = st.data_editor(
        data_mal_defaut,
        num_rows="dynamic",
        hide_index=True,
        key="editor_maladies_interactif"
    )
    
    st.markdown("---")
    st.subheader("📊 Tableau d'Analyse — Maladies & Absences")
    if not edited_maladies.empty:
        st.metric("Total Arrêts / Absences enregistrés", len(edited_maladies))
        if "Agent" in edited_maladies.columns:
            df_analyse_mal = edited_maladies["Agent"].value_counts().reset_index()
            df_analyse_mal.columns = ["Agent", "Nombre d'arrêts"]
            st.dataframe(df_analyse_mal, hide_index=True)
            if not df_analyse_mal.empty and df_analyse_mal["Agent"].iloc[0] != "":
                st.bar_chart(df_analyse_mal.set_index("Agent"))
    else:
        st.info("Ajoutez des données dans le tableau ci-dessus pour afficher l'analyse.")

    if not edited_maladies.empty:
        output_mal = BytesIO()
        with pd.ExcelWriter(output_mal, engine='openpyxl') as writer:
            edited_maladies.to_excel(writer, index=False, sheet_name='Maladies_Absences')
        st.download_button(
            label="📥 Télécharger le suivi des Maladies (Excel)",
            data=output_mal.getvalue(),
            file_name=f"Suivi_Maladies_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ---------------------------------------------------------
# ONGLET 4 : CP FÊTES DE FIN D'ANNÉE (5 ANS & RÉCURRENCES)
# ---------------------------------------------------------
with tab_cp_fin:
    st.subheader("🎄 Analyse sur 5 ans — Congés Payés (Fêtes de Fin d'Année)")
    col_cf1, col_cf2 = st.columns(2)
    with col_cf1:
        f_cp5_excel = st.file_uploader("Importer historique Excel (CP 5 ans)", type=["xlsx", "xls"], key="up_cp5_excel")
    with col_cf2:
        f_cp5_pdf = st.file_uploader("Importer historique PDF (CP 5 ans)", type=["pdf"], key="up_cp5_pdf")

    data_cp5_defaut = pd.DataFrame(columns=["Agent", "Date Début", "Date Fin", "Année"])
    if f_cp5_excel:
        try:
            data_cp5_defaut = pd.read_excel(f_cp5_excel)
        except Exception as e:
            st.error(f"Erreur : {e}")

    edited_cp5 = st.data_editor(
        data_cp5_defaut,
        num_rows="dynamic",
        hide_index=True,
        key="editor_cp5_fetes"
    )

    st.markdown("---")
    st.subheader("🔍 Filtrage & Détection des Récurrences (24/25/31 Décembre & 1er Janvier)")
    if not edited_cp5.empty and "Date Début" in edited_cp5.columns and "Date Fin" in edited_cp5.columns:
        lignes_fetes = []
        for idx, row in edited_cp5.iterrows():
            d_deb_str = str(row.get("Date Début", ""))
            d_fin_str = str(row.get("Date Fin", ""))
            agent_nom = str(row.get("Agent", "Inconnu"))
            annee_val = str(row.get("Année", ""))

            try:
                dt_deb = pd.to_datetime(d_deb_str, dayfirst=True, errors='coerce')
                dt_fin = pd.to_datetime(d_fin_str, dayfirst=True, errors='coerce')

                if pd.notna(dt_deb) and pd.notna(dt_fin):
                    plage_dates = pd.date_range(start=dt_deb, end=dt_fin)
                    touche_fetes = any((dt.month == 12 and dt.day in [24, 25, 31]) or (dt.month == 1 and dt.day == 1) for dt in plage_dates)
                    
                    if touche_fetes:
                        annee_detectee = annee_val if annee_val else str(dt_deb.year)
                        lignes_fetes.append({"Agent": agent_nom, "Date Début": d_deb_str, "Date Fin": d_fin_str, "Année": annee_detectee})
            except Exception:
                pass

        df_fetes_cp = pd.DataFrame(lignes_fetes)
        if not df_fetes_cp.empty:
            st.success(f"🎯 {len(df_fetes_cp)} période(s) de congé identifiée(s) sur les fêtes de fin d'année !")
            st.dataframe(df_fetes_cp, hide_index=True)
            recurrence_cp = df_fetes_cp["Agent"].value_counts().reset_index()
            recurrence_cp.columns = ["Agent", "Nombre de Noëls / Nouvel An pris"]
            st.dataframe(recurrence_cp, hide_index=True)
            st.bar_chart(recurrence_cp.set_index("Agent"))
        else:
            st.info("Aucun congé ne correspond aux dates cibles (24, 25, 31 décembre ou 1er janvier).")
    else:
        st.info("Remplissez ou importez l'historique sur 5 ans pour lancer l'analyse des récurrences.")

# ---------------------------------------------------------
# ONGLET 5 : MALADIES FÊTES DE FIN D'ANNÉE (5 ANS & RÉCURRENCES)
# ---------------------------------------------------------
with tab_maladies_fin:
    st.subheader("🎄 Analyse sur 5 ans — Arrêts Maladie (Fêtes de Fin d'Année)")
    col_mf1, col_mf2 = st.columns(2)
    with col_mf1:
        f_mal5_excel = st.file_uploader("Importer historique Excel (Maladies 5 ans)", type=["xlsx", "xls"], key="up_mal5_excel")
    with col_mf2:
        f_mal5_pdf = st.file_uploader("Importer historique PDF (Maladies 5 ans)", type=["pdf"], key="up_mal5_pdf")

    data_mal5_defaut = pd.DataFrame(columns=["Agent", "Date Début", "Date Fin", "Année", "Motif"])
    if f_mal5_excel:
        try:
            data_mal5_defaut = pd.read_excel(f_mal5_excel)
        except Exception as e:
            st.error(f"Erreur : {e}")

    edited_mal5 = st.data_editor(
        data_mal5_defaut,
        num_rows="dynamic",
        hide_index=True,
        key="editor_mal5_fetes"
    )

    st.markdown("---")
    st.subheader("🔍 Filtrage & Détection des Récurrences (Maladies pendant les Fêtes)")
    if not edited_mal5.empty and "Date Début" in edited_mal5.columns and "Date Fin" in edited_mal5.columns:
        lignes_mal_fetes = []
        for idx, row in edited_mal5.iterrows():
            d_deb_str = str(row.get("Date Début", ""))
            d_fin_str = str(row.get("Date Fin", ""))
            agent_nom = str(row.get("Agent", "Inconnu"))
            annee_val = str(row.get("Année", ""))
            motif_val = str(row.get("Motif", ""))

            try:
                dt_deb = pd.to_datetime(d_deb_str, dayfirst=True, errors='coerce')
                dt_fin = pd.to_datetime(d_fin_str, dayfirst=True, errors='coerce')

                if pd.notna(dt_deb) and pd.notna(dt_fin):
                    plage_dates = pd.date_range(start=dt_deb, end=dt_fin)
                    touche_fetes = any((dt.month == 12 and dt.day in [24, 25, 31]) or (dt.month == 1 and dt.day == 1) for dt in plage_dates)
                    
                    if touche_fetes:
                        annee_detectee = annee_val if annee_val else str(dt_deb.year)
                        lignes_mal_fetes.append({"Agent": agent_nom, "Date Début": d_deb_str, "Date Fin": d_fin_str, "Année": annee_detectee, "Motif": motif_val})
            except Exception:
                pass

        df_fetes_mal = pd.DataFrame(lignes_mal_fetes)
        if not df_fetes_mal.empty:
            st.success(f"🎯 {len(df_fetes_mal)} arrêt(s) maladie identifié(s) pendant les fêtes !")
            st.dataframe(df_fetes_mal, hide_index=True)
            recurrence_mal = df_fetes_mal["Agent"].value_counts().reset_index()
            recurrence_mal.columns = ["Agent", "Nombre d'arrêts pendant les fêtes"]
            st.dataframe(recurrence_mal, hide_index=True)
            st.bar_chart(recurrence_mal.set_index("Agent"))
        else:
            st.info("Aucun arrêt maladie ne coïncide avec les fêtes de fin d'année.")
    else:
        st.info("Remplissez ou importez l'historique sur 5 ans pour lancer l'analyse.")
