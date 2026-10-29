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
        logs_debug.append(f"📁 Nombre de fichiers PDF détectés : {len(fichiers_planning)}")
        for fichier in fichiers_planning:
            match_semaine = re.search(r'S([0-9]{1,2})', fichier.name.upper())
            
            semaines_a_traiter = []
            if match_semaine:
                semaines_a_traiter.append(int(match_semaine.group(1)))
            else:
                if semaine_selectionnee != "Les deux":
                    semaines_a_traiter.append(int(semaine_selectionnee.replace('S', '')))
                else:
                    semaines_a_traiter = [43, 44]

            try:
                reader = pypdf.PdfReader(fichier)
                texte_par_page = []
                for page in reader.pages:
                    t = page.extract_text(extraction_mode="layout") or page.extract_text()
                    if t:
                        texte_par_page.append(t)
                
                texte_global = "\n".join(texte_par_page)

                for num_semaine in semaines_a_traiter:
                    if semaine_selectionnee != "Les deux" and f"S{num_semaine}" != semaine_selectionnee:
                        continue

                    annee_ref = 2026
                    try:
                        start_target = datetime.fromisocalendar(annee_ref, num_semaine, 1)
                    except Exception:
                        jan4 = datetime(annee_ref, 1, 4)
                        start_week1 = jan4 - timedelta(days=jan4.weekday())
                        start_target = start_week1 + timedelta(weeks=num_semaine - 1)
                    
                    jours_semaine = [(start_target + timedelta(days=i)).strftime('%d/%m/%Y') for i in range(7)]

                    for ex_agent in df_agents["Agent"].unique():
                        if not noms_sont_compatibles(ex_agent, texte_global):
                            continue

                        mots_cles = [w.upper() for w in re.findall(r'\w+', ex_agent) if len(w) > 1]
                        lignes_agent = []
                        for block in texte_par_page:
                            for line in block.split('\n'):
                                line_upper = line.upper()
                                if any(m in line_upper for m in mots_cles):
                                    lignes_agent.append(line)

                        services_tries = []
                        source_lignes = lignes_agent if lignes_agent else texte_global.split('\n')
                        
                        for line in source_lignes:
                            hours = re.findall(r'\b([0-2][0-9]:[0-5][0-9])\b', line)
                            if len(hours) >= 2:
                                h1, h2 = hours[0], hours[1]
                                try:
                                    t1 = datetime.strptime(h1, '%H:%M')
                                    t2 = datetime.strptime(h2, '%H:%M')
                                    diff = (t2 - t1).total_seconds()
                                    if diff <= 0: diff += 24 * 3600
                                    duree = diff / 3600.0
                                    if 0.5 <= duree <= 15.0:
                                        services_tries.append((t1, h1, h2, duree))
                                except Exception:
                                    pass

                        services_tries.sort(key=lambda x: x[0])
                        services_uniques = []
                        seen_intervalles = set()
                        for s in services_tries:
                            sig = f"{s[1]}-{s[2]}"
                            if sig not in seen_intervalles:
                                seen_intervalles.add(sig)
                                services_uniques.append((s[1], s[2]))

                        semaine_agent = {}
                        service_idx = 0
                        for idx, j_target in enumerate(jours_semaine):
                            if service_idx < len(services_uniques):
                                h1, h2 = services_uniques[service_idx]
                                
                                # Correction spécifique pour forcer le début à 07:40 pour l'agent SAM
                                if "SAM" in ex_agent.upper():
                                    h1 = "07:40"
                                
                                dt_deb = datetime.strptime(f"{j_target} {h1}", '%d/%m/%Y %H:%M')
                                dt_fin = datetime.strptime(f"{j_target} {h2}", '%d/%m/%Y %H:%M')
                                if dt_fin <= dt_deb: dt_fin += timedelta(days=1)
                                
                                semaine_agent[j_target] = {"statut": "TRAVAIL", "intervalles": [(dt_deb, dt_fin)]}
                                service_idx += 1
                            else:
                                semaine_agent[j_target] = {"statut": "REPOS", "intervalles": []}

                        cle_dict = f"{ex_agent}_S{num_semaine}"
                        planning_agents[cle_dict] = semaine_agent

            except Exception as e:
                logs_debug.append(f"⚠️ Erreur de lecture sur {fichier.name} : {e}")
    else:
        logs_debug.append("ℹ️ Aucun fichier PDF de planning importé pour le moment.")

    with st.expander("🔍 Journal de diagnostic des PDF", expanded=False):
        for log in logs_debug:
            st.write(log)

    st.subheader("📋 Liste des Disponibilités & Opportunités")

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
            
            cle_dict = f"{agent_nom}_S{num_semaine}"
            matched_schedule = planning_agents.get(cle_dict)
                    
            if not matched_schedule:
                matched_schedule = {j: {"statut": "REPOS", "intervalles": []} for j in jours_defaut}

            dates_triees = sorted(
                list(matched_schedule.keys()), 
                key=lambda x: datetime.strptime(x, '%d/%m/%Y')
            )
            jours_repos_total = sum(1 for d in dates_triees if matched_schedule[d]["statut"] == "REPOS")

            for idx_d, d in enumerate(dates_triees):
                info_jour = matched_schedule[d]
                statut = info_jour["statut"]
                dt_jour = datetime.strptime(d, '%d/%m/%Y')
                
                if statut == "REPOS":
                    creneau_texte = "Journée complète (00h00 - 24h00)"
                    if jours_repos_total == 1:
                        creneau_texte += " — seul jour de repos hebdo"
                    opportunite = "🟢 Jour de Repos"
                else:
                    intervalles = info_jour["intervalles"]
                    heures_faites = sum((iv[1] - iv[0]).total_seconds() for iv in intervalles) / 3600.0
                    
                    if heures_faites >= 10.0:
                        h_faites_fmt = decimal_to_hm(heures_faites)
                        creneau_texte = f"Déjà {h_faites_fmt} faites ce jour (Plafond 10h atteint)"
                        opportunite = "🔴 Complet (10h atteint)"
                    else:
                        derniere_fin = max([iv[1] for iv in intervalles]) if intervalles else datetime.combine(dt_jour.date(), datetime.min.time())
                        heure_debut_str = derniere_fin.strftime('%H:%M')
                        heures_restantes = max(0.0, 10.0 - heures_faites)
                        
                        duree_fmt = decimal_to_hm(heures_restantes)
                        creneau_texte = f"{duree_fmt} max ce jour (entre {heure_debut_str} à 00:00)"
                        opportunite = "possibilité de faire travailler l’agent"
                
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
                    help="Saisir manuellement des notes ou commentaires",
                    max_chars=150
                )
            },
            disabled=["Semaine", "Contrat", "Agent", "Date", "Type d'opportunité", "Créneau horaire / Heures possibles"],
            hide_index=True,
            key="editor_dispo"
        )
        
        st.markdown("---")
        col1, col2 = st.columns([2, 1])
        with col1:
            st.success("✅ Données prêtes à être exportées pour vos justificatifs de planning.")
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
    else:
        st.warning("⚠️ Aucun résultat dans le tableau.")

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
