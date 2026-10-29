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
# SÉCURITÉ : SYSTÈME DE MOT DE PASSE
# ---------------------------------------------------------
MOT_DE_PASSE_CORRECT = "SOS2026"  # <--- Changez ce mot de passe ici

if "authentifie" not in st.session_state:
    st.session_state["authentifie"] = False

if not st.session_state["authentifie"]:
    st.title("🔒 Accès Sécurisé — Portail RH & Plannings")
    st.write("Ce portail contient des données confidentielles. Veuillez saisir le mot de passe d'accès.")
    
    mdp_saisi = st.text_input("Mot de passe :", type="password")
    
    if st.button("Se connecter"):
        if mdp_saisi == MOT_DE_PASSE_CORRECT:
            st.session_state["authentifie"] = True
            st.success("Accès autorisé.")
            st.rerun()
        else:
            st.error("Mot de passe incorrect. Accès refusé.")
            
    st.stop()

# ---------------------------------------------------------
# INTERFACE PRINCIPALE
# ---------------------------------------------------------
col_titre, col_deco = st.columns([4, 1])
with col_titre:
    st.title("🚨 SOS Remplacement — Portail de Gestion")
with col_deco:
    if st.button("🔒 Déconnexion"):
        st.session_state["authentifie"] = False
        st.rerun()

st.markdown("---")

# Création des onglets
tab_dispo, tab_cp, tab_maladies = st.tabs([
    "📋 Disponibilités & Remplacements", 
    "🏖️ Congés Payés & Analyses", 
    "🏥 Maladies & Analyses"
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
        # Nettoyage ultra-souple pour matcher le nom peu importe l'ordre (ex: "Monique Lissé" vs "Lissé AH SAM Monique")
        mots_excel = [w.upper() for w in re.findall(r'\w+', excel_name) if len(w) > 1]
        p_upper = pdf_text.upper()
        if not mots_excel:
            return False
        # Si au moins un mot significatif (nom ou prénom) est présent dans le texte du PDF
        matches = sum(1 for mot in mots_excel if mot in p_upper)
        return matches >= 1

    if fichiers_planning:
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
                lignes_texte = []
                for page in reader.pages:
                    t = page.extract_text(extraction_mode="layout") or page.extract_text()
                    if t:
                        for l in t.split('\n'):
                            l_clean = l.strip()
                            if l_clean:
                                lignes_texte.append(l_clean)
                
                texte_global = "\n".join(lignes_texte)
                
                agents_trouves_dans_pdf = []
                for ex_agent in df_agents["Agent"].unique():
                    if noms_sont_compatibles(ex_agent, texte_global):
                        agents_trouves_dans_pdf.append(ex_agent)
                
                logs_debug.append(f"📁 Fichier `{fichier.name}` : {len(agents_trouves_dans_pdf)} agent(s) détecté(s).")

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
                    
                    services_tries = []
                    for line in lignes_texte:
                        if "TOTAL" in line.upper() or len(line) < 4:
                            continue
                        
                        hours = re.findall(r'\b([0-2][0-9]:[0-5][0-9])\b', line)
                        if len(hours) >= 2:
                            h1, h2 = hours[0], hours[1]
                            try:
                                t1 = datetime.strptime(h1, '%H:%M')
                                t2 = datetime.strptime(h2, '%H:%M')
                                diff = (t2 - t1).total_seconds()
                                if diff <= 0: diff += 24 * 3600
                                duree = diff / 3600.0
                                
                                if 1.0 <= duree <= 14.0:
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
                        if idx == 4:
                            semaine_agent[j_target] = {"statut": "REPOS", "intervalles": []}
                        else:
                            if service_idx < len(services_uniques):
                                h1, h2 = services_uniques[service_idx]
                                dt_deb = datetime.strptime(f"{j_target} {h1}", '%d/%m/%Y %H:%M')
                                dt_fin = datetime.strptime(f"{j_target} {h2}", '%d/%m/%Y %H:%M')
                                if dt_fin <= dt_deb: dt_fin += timedelta(days=1)
                                
                                semaine_agent[j_target] = {"statut": "TRAVAIL", "intervalles": [(dt_deb, dt_fin)]}
                                service_idx += 1
                            else:
                                semaine_agent[j_target] = {"statut": "REPOS", "intervalles": []}

                    for agent_name in agents_trouves_dans_pdf:
                        cle_dict = f"{agent_name}_S{num_semaine}"
                        planning_agents[cle_dict] = semaine_agent

            except Exception as e:
                logs_debug.append(f"⚠️ Erreur de lecture sur {fichier.name} : {e}")

    with st.expander("🔍 Journal de diagnostic des PDF", expanded=True):
        for log in logs_debug:
            st.write(log)

    st.subheader("📋 Liste des Disponibilités & Opportunités")

    tableau_resultats = []
    tous_agents = df_agents[["Contrat", "Agent"]].drop_duplicates().to_dict(orient="records")

    annee_ref = 2026
    start_target = datetime.fromisocalendar(annee_ref, 43, 1)
    jours_defaut = [(start_target + timedelta(days=i)).strftime('%d/%m/%Y') for i in range(7)]

    for item in tous_agents:
        contrat_nom = item["Contrat"]
        agent_nom = item["Agent"]
        
        matched_schedule = None
        for k, sched in planning_agents.items():
            nom_base = k.rsplit('_S', 1)[0]
            if noms_sont_compatibles(agent_nom, nom_base):
                matched_schedule = sched
                break
                
        if not matched_schedule:
            matched_schedule = {j: {"statut": "REPOS", "intervalles": []} for j in jours_defaut}

        dates_triees = sorted(
            matched_schedule.keys(), 
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
                heures_faites = sum([(iv[1] - iv[0]).total_seconds() for iv in intervalles]) / 3600.0
                
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
            disabled=["Contrat", "Agent", "Date", "Type d'opportunité", "Créneau horaire / Heures possibles"],
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
    st.write("Gérez vos congés et visualisez instantanément les analyses ci-dessous.")
    
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        f_cp_excel = st.file_uploader("Importer un fichier Excel (CP)", type=["xlsx", "xls"], key="up_cp_excel")
    with col_up2:
        f_cp_pdf = st.file_uploader("Importer un fichier PDF (CP)", type=["pdf"], key="up_cp_pdf")
        
    data_cp_defaut = pd.DataFrame(columns=["Agent", "Date Début", "Date Fin", "Type de Congé", "Statut"])
    
    if f_cp_excel:
        try:
            data_cp_defaut = pd.read_excel(f_cp_excel)
            st.success("Fichier Excel CP importé avec succès !")
        except Exception as e:
            st.error(f"Erreur de lecture Excel : {e}")
            
    elif f_cp_pdf:
        try:
            reader = pypdf.PdfReader(f_cp_pdf)
            for page in reader.pages:
                pass
            st.info("Fichier PDF lu. Vous pouvez compléter ou vérifier les informations dans le tableau.")
        except Exception as e:
            st.error(f"Erreur de lecture PDF : {e}")

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
        total_cp = len(edited_cp)
        valides_cp = len(edited_cp[edited_cp["Statut"] == "Validé"])
        demandes_cp = len(edited_cp[edited_cp["Statut"] == "Demandé"])
        
        col_m1.metric("Total Demandes CP", total_cp)
        col_m2.metric("Congés Validés", valides_cp)
        col_m3.metric("En attente", demandes_cp)
        
        st.write("##### Répartition par Statut :")
        if "Statut" in edited_cp.columns:
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
    st.write("Consultez et analysez les arrêts de travail de vos agents.")
    
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        f_mal_excel = st.file_uploader("Importer un fichier Excel (Maladies)", type=["xlsx", "xls"], key="up_mal_excel")
    with col_m2:
        f_mal_pdf = st.file_uploader("Importer un fichier PDF (Maladies / Justificatif)", type=["pdf"], key="up_mal_pdf")
        
    data_mal_defaut = pd.DataFrame(columns=["Agent", "Date Début", "Date Fin", "Motif / Justificatif", "Commentaire"])
    
    if f_mal_excel:
        try:
            data_mal_defaut = pd.read_excel(f_mal_excel)
            st.success("Fichier Excel Maladies importé avec succès !")
        except Exception as e:
            st.error(f"Erreur de lecture Excel : {e}")
            
    elif f_mal_pdf:
        try:
            reader = pypdf.PdfReader(f_mal_pdf)
            for page in reader.pages:
                pass
            st.info("Fichier PDF de justificatif lu. Vous pouvez l'ajouter dans le tableau.")
        except Exception as e:
            st.error(f"Erreur de lecture PDF : {e}")

    edited_maladies = st.data_editor(
        data_mal_defaut,
        num_rows="dynamic",
        hide_index=True,
        key="editor_maladies_interactif"
    )
    
    st.markdown("---")
    st.subheader("📊 Tableau d'Analyse — Maladies & Absences")
    
    if not edited_maladies.empty:
        total_maladies = len(edited_maladies)
        st.metric("Total Arrêts / Absences enregistrés", total_maladies)
        
        if "Agent" in edited_maladies.columns:
            st.write("##### Arrêts par Agent :")
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
