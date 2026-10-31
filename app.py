import streamlit as st
import pandas as pd
import pypdf
import re
import os
from datetime import datetime, timedelta
from io import BytesIO
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Configuration de la page
st.set_page_config(
    page_title="SOS Remplacement - Portails RH",
    page_icon="🔒",
    layout="wide"
)

# Dossier sécurisé pour stocker les fichiers administratifs partagés
DOSSIER_STOCKAGE = "fichiers_admin_stock"
os.makedirs(DOSSIER_STOCKAGE, exist_ok=True)

# ---------------------------------------------------------
# SÉCURITÉ : GESTION DES UTILISATEURS & DROITS
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
if "historique_connexions" not in st.session_state:
    st.session_state["historique_connexions"] = []

if "droits_ecriture" not in st.session_state:
    st.session_state["droits_ecriture"] = {
        "hinerava": True,
        "hoania": True
    }

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
                
                date_heure_actuelle = datetime.now().strftime("%d/%m/%Y à %H:%M:%S")
                st.session_state["historique_connexions"].append({
                    "Utilisateur": username_saisi.capitalize(),
                    "Rôle": UTILISATEURS_AUTORISES[username_saisi]["role"],
                    "Date et Heure": date_heure_actuelle
                })
                
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

# Fonction PDF officiel
def generer_pdf_officiel(dataframe_a_imprimer, titre_rapport):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1f4e78'),
        spaceAfter=15,
        alignment=1
    )
    
    elements.append(Paragraph(f"RAPPORT OFFICIEL — {titre_rapport.upper()}", title_style))
    elements.append(Paragraph(f"Généré le : {datetime.now().strftime('%d/%m/%Y à %H:%M')} par {st.session_state['utilisateur_connecte'].capitalize()} (Document validé)", styles['Normal']))
    elements.append(Spacer(1, 15))
    
    if not dataframe_a_imprimer.empty:
        data = [list(dataframe_a_imprimer.columns)]
        for _, row in dataframe_a_imprimer.iterrows():
            data.append([str(val) if pd.notna(val) else "" for val in row])
            
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4e78')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d3d3d3')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph("Aucune donnée à afficher.", styles['Normal']))
        
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

# Onglets dynamiques
if st.session_state["utilisateur_connecte"] == "admin":
    tab_dispo, tab_cp, tab_maladies, tab_cp_fin, tab_maladies_fin, tab_admin_secu = st.tabs([
        "📋 Disponibilités & Remplacements", 
        "🏖️ Congés Payés & Analyses", 
        "🏥 Maladies & Analyses",
        "🎄 CP Fêtes de Fin d'Année (5 ans)",
        "🎄 Maladies Fêtes de Fin d'Année (5 ans)",
        "🔐 Contrôle Admin & Documents"
    ])
else:
    tab_dispo, tab_cp, tab_maladies, tab_cp_fin, tab_maladies_fin = st.tabs([
        "📋 Disponibilités & Remplacements", 
        "🏖️ Congés Payés & Analyses", 
        "🏥 Maladies & Analyses",
        "🎄 CP Fêtes de Fin d'Année (5 ans)",
        "🎄 Maladies Fêtes de Fin d'Année (5 ans)"
    ])

user_actuel = st.session_state["utilisateur_connecte"]
mode_edition_active = True if user_actuel == "admin" else st.session_state["droits_ecriture"].get(user_actuel, True)

# ---------------------------------------------------------
# GESTION CENTRALISÉE DES FICHIERS STOCKÉS
# ---------------------------------------------------------
st.sidebar.header("📁 Référentiel & Plannings")
if user_actuel == "admin":
    st.sidebar.info("👤 Espace Admin : Vous seul pouvez ajouter ou supprimer les documents officiels.")
    
    admin_excel = st.sidebar.file_uploader("1. Fichier Référentiel (.xlsx)", type=["xlsx", "xls"], key="adm_excel")
    if admin_excel:
        chemin_excel = os.path.join(DOSSIER_STOCKAGE, "referentiel_agents.xlsx")
        with open(chemin_excel, "wb") as f:
            f.write(admin_excel.getbuffer())
        st.sidebar.success("✅ Référentiel mis à jour !")

    admin_pdfs = st.sidebar.file_uploader("2. Plannings PDF Comète", type=["pdf"], accept_multiple_files=True, key="adm_pdf")
    if admin_pdfs:
        for p in admin_pdfs:
            chemin_pdf = os.path.join(DOSSIER_STOCKAGE, p.name)
            with open(chemin_pdf, "wb") as f:
                f.write(p.getbuffer())
        st.sidebar.success("✅ Planning(s) PDF ajouté(s) !")

    # Option de suppression de fichiers
    fichiers_stockes = os.listdir(DOSSIER_STOCKAGE)
    if fichiers_stockes:
        st.sidebar.markdown("---")
        st.sidebar.subheader("🗑️ Supprimer un document")
        fichier_a_supprimer = st.sidebar.selectbox("Choisir le fichier à retirer", ["--- Choisir ---"] + fichiers_stockes)
        if fichier_a_supprimer != "--- Choisir ---":
            if st.sidebar.button("Supprimer ce fichier"):
                try:
                    os.remove(os.path.join(DOSSIER_STOCKAGE, fichier_a_supprimer))
                    st.sidebar.success(f"Fichier {fichier_a_supprimer} supprimé.")
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Erreur : {e}")
else:
    st.sidebar.success("🔒 Plannings officiels verrouillés. Consultation active de la semaine en cours.")

semaine_selectionnee = st.sidebar.selectbox("3. Semaine à afficher en priorité", ["S43", "S44", "Les deux"], key="semaine_dispo")

# ---------------------------------------------------------
# ONGLET 1 : DISPONIBILITÉS
# ---------------------------------------------------------
with tab_dispo:
    # Charger automatiquement depuis le dossier stocké partagé
    chemin_ref_local = os.path.join(DOSSIER_STOCKAGE, "referentiel_agents.xlsx")
    if not os.path.exists(chemin_ref_local):
        st.warning("⚠️ Aucun fichier Référentiel (.xlsx) n'a encore été inséré par l'administrateur.")
        st.stop()

    def charger_referentiel(chemin_fichier):
        try:
            df_raw = pd.read_excel(chemin_fichier, header=None)
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

    df_agents, erreur = charger_referentiel(chemin_ref_local)
    if erreur:
        st.error(f"⚠️ {erreur}")
        st.stop()

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

    # Récupérer tous les PDF du dossier stocké
    fichiers_pdf_stockes = [os.path.join(DOSSIER_STOCKAGE, f) for f in os.listdir(DOSSIER_STOCKAGE) if f.endswith(".pdf")]

    if fichiers_pdf_stockes:
        for chemin_pdf in fichiers_pdf_stockes:
            nom_fichier = os.path.basename(chemin_pdf)
            match_semaine = re.search(r'S([0-9]{1,2})', nom_fichier.upper())
            
            semaines_a_traiter = []
            if match_semaine:
                semaines_a_traiter.append(int(match_semaine.group(1)))
            else:
                if semaine_selectionnee != "Les deux":
                    semaines_a_traiter.append(int(semaine_selectionnee.replace('S', '')))
                else:
                    semaines_a_traiter = [43, 44]

            try:
                reader = pypdf.PdfReader(chemin_pdf)
                lignes_texte = []
                for page in reader.pages:
                    t = page.extract_text(extraction_mode="layout") or page.extract_text()
                    if t:
                        for l in t.split('\n'):
                            l_clean = l.strip()
                            if l_clean:
                                lignes_texte.append(l_clean)
                
                texte_global = "\n".join(lignes_texte)
                agents_trouves_dans_pdf = [ex for ex in df_agents["Agent"].unique() if noms_sont_compatibles(ex, texte_global)]
                
                logs_debug.append(f"📁 Fichier `{nom_fichier}` : {len(agents_trouves_dans_pdf)} agent(s) détecté(s).")

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
                        planning_agents[f"{agent_name}_S{num_semaine}"] = semaine_agent

            except Exception as e:
                logs_debug.append(f"⚠️ Erreur sur {nom_fichier} : {e}")

    with st.expander("🔍 Journal de diagnostic des PDF", expanded=False):
        for log in logs_debug:
            st.write(log)

    st.subheader("📋 Liste des Disponibilités & Opportunités")
    if not mode_edition_active:
        st.warning("🔒 **Mode Lecture Seule :** Vos droits de modification ont été verrouillés par l'administrateur.")

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

        dates_triees = sorted(matched_schedule.keys(), key=lambda x: datetime.strptime(x, '%d/%m/%Y'))
        jours_repos_total = sum(1 for d in dates_triees if matched_schedule[d]["statut"] == "REPOS")

        for d in dates_triees:
            info_jour = matched_schedule[d]
            statut = info_jour["statut"]
            dt_jour = datetime.strptime(d, '%d/%m/%Y')
            
            if statut == "REPOS":
                creneau_texte = "Journée complète (00h00 - 24h00)"
                if jours_repos_total == 1: creneau_texte += " — seul jour de repos hebdo"
                opportunite = "🟢 Jour de Repos"
            else:
                intervalles = info_jour["intervalles"]
                heures_faites = sum([(iv[1] - iv[0]).total_seconds() for iv in intervalles]) / 3600.0
                if heures_faites >= 10.0:
                    creneau_texte = f"Déjà {decimal_to_hm(heures_faites)} faites ce jour (Plafond 10h atteint)"
                    opportunite = "🔴 Complet (10h atteint)"
                else:
                    derniere_fin = max([iv[1] for iv in intervalles]) if intervalles else datetime.combine(dt_jour.date(), datetime.min.time())
                    heures_restantes = max(0.0, 10.0 - heures_faites)
                    creneau_texte = f"{decimal_to_hm(heures_restantes)} max ce jour (entre {derniere_fin.strftime('%H:%M')} à 00:00)"
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
                "Dernier recours": st.column_config.TextColumn("Dernier recours (Saisie quotidienne)", max_chars=150)
            },
            disabled=["Contrat", "Agent", "Date", "Type d'opportunité", "Créneau horaire / Heures possibles"],
            hide_index=True,
            key="editor_dispo"
        )
        
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.success("✅ Données synchronisées.")
        with col2:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                edited_df.to_excel(writer, index=False, sheet_name='Disponibilites')
            st.download_button("📥 Télécharger (Excel)", output.getvalue(), file_name=f"Rapport_{datetime.now().strftime('%Y-%m-%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with col3:
            pdf_bytes = generer_pdf_officiel(edited_df, "Disponibilités et Remplacements")
            st.download_button("🖨️ Imprimer (PDF Officiel)", pdf_bytes, file_name=f"Rapport_Officiel_{datetime.now().strftime('%Y-%m-%d')}.pdf", mime="application/pdf")

# ---------------------------------------------------------
# AUTRES ONGLETS (CP, Maladies, Fin d'année)
# ---------------------------------------------------------
with tab_cp:
    st.subheader("🏖️ Suivi des Congés Payés (CP)")
    edited_cp = st.data_editor(pd.DataFrame(columns=["Agent", "Date Début", "Date Fin", "Type de Congé", "Statut"]), num_rows="dynamic", hide_index=True, key="cp_s")
    if not edited_cp.empty:
        st.download_button("🖨️ Imprimer PDF CP", generer_pdf_officiel(edited_cp, "Congés Payés"), file_name="CP.pdf", mime="application/pdf")

with tab_maladies:
    st.subheader("🏥 Suivi des Arrêts Maladie")
    edited_mal = st.data_editor(pd.DataFrame(columns=["Agent", "Date Début", "Date Fin", "Motif", "Commentaire"]), num_rows="dynamic", hide_index=True, key="mal_s")
    if not edited_mal.empty:
        st.download_button("🖨️ Imprimer PDF Maladies", generer_pdf_officiel(edited_mal, "Maladies"), file_name="Maladies.pdf", mime="application/pdf")

with tab_cp_fin:
    st.subheader("🎄 CP Fêtes de Fin d'Année (5 ans)")
    st.data_editor(pd.DataFrame(columns=["Agent", "Date Début", "Date Fin", "Année", "Statut"]), num_rows="dynamic", hide_index=True, key="cp5_s")

with tab_maladies_fin:
    st.subheader("🎄 Maladies Fêtes de Fin d'Année (5 ans)")
    st.data_editor(pd.DataFrame(columns=["Agent", "Date Début", "Date Fin", "Année", "Motif"]), num_rows="dynamic", key="mal5_s")

# ---------------------------------------------------------
# ONGLET ADMIN : CONTRÔLE & DOCUMENTS
# ---------------------------------------------------------
if user_actuel == "admin":
    with tab_admin_secu:
        st.subheader("🔐 Panneau de Contrôle & Gestion des Documents")
        st.write("En tant qu'administrateur unique, vous gérez les fichiers permanents et les droits des planificateurs :")
        
        st.markdown("---")
        st.subheader("📂 Documents actuellement en mémoire sur le serveur :")
        fichiers_actuels = os.listdir(DOSSIER_STOCKAGE)
        if fichiers_actuels:
            for f in fichiers_actuels:
                st.write(f"- 📄 `{f}`")
        else:
            st.info("Aucun document stocké pour le moment.")

        st.markdown("---")
        st.subheader("⚙️ Droits d'écriture des Planificateurs :")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.session_state["droits_ecriture"]["hinerava"] = st.checkbox("Autoriser Hinerava à modifier", value=st.session_state["droits_ecriture"]["hinerava"])
        with col_d2:
            st.session_state["droits_ecriture"]["hoania"] = st.checkbox("Autoriser Hoania à modifier", value=st.session_state["droits_ecriture"]["hoania"])

        st.markdown("---")
        st.subheader("📜 Journal des Connexions")
        if st.session_state["historique_connexions"]:
            st.dataframe(pd.DataFrame(st.session_state["historique_connexions"]), hide_index=True, use_container_width=True)
        else:
            st.info("Aucune connexion enregistrée.")
