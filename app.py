import streamlit as st
import pandas as pd
import pypdf
import re
from datetime import datetime, timedelta
from io import BytesIO

# Configuration de la page
st.set_page_config(
    page_title="SOS Remplacement - Centralistes",
    page_icon="🚨",
    layout="wide"
)

st.title("🚨 SOS Remplacement - Assistant (Conforme, Chronologique & Traçable)")
st.markdown("---")

# ---------------------------------------------------------
# 1. BARRE LATÉRALE : IMPORTATION DES FICHIERS
# ---------------------------------------------------------
st.sidebar.header("📁 Données de la Semaine")
uploaded_excel = st.sidebar.file_uploader(
    "1. Fichier Référentiel Agents (.xlsx)", 
    type=["xlsx", "xls"]
)
fichiers_planning = st.sidebar.file_uploader(
    "2. Plannings PDF Comète (Multi-contrats)", 
    type=["pdf"], 
    accept_multiple_files=True
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

semaine_selectionnee = st.sidebar.selectbox("3. Semaine à afficher en priorité", ["S43", "S44", "Les deux"])

def decimal_to_hm(heures_dec):
    h = int(heures_dec)
    m = int(round((heures_dec - h) * 60))
    if m == 60:
        h += 1
        m = 0
    return f"{h}h{m:02d}"

# ---------------------------------------------------------
# 2. ANALYSE CHRONOLOGIQUE ET MULTI-AGENTS DES PDF
# ---------------------------------------------------------
planning_agents = {}
logs_debug = []

def noms_sont_compatibles(excel_name, pdf_text):
    e_words = [w.upper() for w in re.findall(r'\w+', excel_name) if len(w) > 2]
    p_text_upper = pdf_text.upper()
    if not e_words:
        return excel_name.upper() in p_text_upper
    matches = sum(1 for word in e_words if word in p_text_upper)
    return matches >= min(len(e_words), 1)

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

with st.expander("🔍 Journal de diagnostic des PDF", expanded=False):
    for log in logs_debug:
        st.write(log)

# ---------------------------------------------------------
# 3. GÉNÉRATION DU TABLEAU (MÉTHODE ROBUSTE PAR JOUR)
# ---------------------------------------------------------
st.subheader("📋 Liste des Disponibilités & Opportunités (Contrôle Rigoureux)")

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
