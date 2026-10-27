import streamlit as st
import pandas as pd
import pypdf
import re
from datetime import datetime, timedelta

# Configuration de la page
st.set_page_config(
    page_title="SOS Remplacement - Centralistes",
    page_icon="🚨",
    layout="wide"
)

st.title("🚨 SOS Remplacement - Assistant (Extraction Chirurgicale par Date)")
st.markdown("---")

# ---------------------------------------------------------
# 1. BARRE LATÉRALE : IMPORTATION DES FICHIERS
# ---------------------------------------------------------
st.sidebar.header("📁 Données de la Semaine")
uploaded_excel = st.sidebar.file_uploader("1. Fichier Référentiel Agents (.xlsx)", type=["xlsx", "xls"])
fichiers_planning = st.sidebar.file_uploader("2. Plannings PDF Comète (Multi-contrats)", type=["pdf"], accept_multiple_files=True)

def charger_referentiel(excel_file):
    try:
        df_raw = pd.read_excel(excel_file, header=None)
        df_raw[0] = df_raw[0].ffill()
        
        donnees_traitees = []
        site_actuel = ""
        
        for idx, row in df_raw.iterrows():
            val_col_a = str(row[0]).strip() if pd.notna(row[0]) else ""
            if val_col_a.upper() in ["SITES", "SITE", "NAN", "", "CONTRATS"]:
                continue
            site_actuel = val_col_a
            
            for col_idx in range(1, len(row)):
                agent_nom = str(row[col_idx]).strip() if pd.notna(row[col_idx]) else ""
                if agent_nom and agent_nom.upper() not in ["NAN", "NOM / PRENOM", "AGENT"]:
                    donnees_traitees.append({
                        "Contrats": site_actuel,
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

# ---------------------------------------------------------
# 2. ANALYSE PAR DÉCOUPAGE STRICT DES JOURS (ANTI-CUMUL)
# ---------------------------------------------------------
planning_agents = {}
logs_debug = []

def noms_sont_compatibles(excel_name, pdf_name):
    e_words = set(excel_name.upper().split())
    p_words = set(pdf_name.upper().split())
    return len(e_words.intersection(p_words)) >= min(len(e_words), len(p_words))

if fichiers_planning:
    for fichier in fichiers_planning:
        try:
            reader = pypdf.PdfReader(fichier)
            texte_complet = ""
            for page in reader.pages:
                try:
                    t = page.extract_text(extraction_mode="layout")
                except Exception:
                    t = page.extract_text()
                if t:
                    texte_complet += t + "\n"
            
            text_upper = texte_complet.upper()
            
            agent_name_pdf = None
            for ex_agent in df_agents["Agent"].unique():
                if ex_agent.upper() in text_upper:
                    agent_name_pdf = ex_agent.upper()
                    break
            
            if not agent_name_pdf:
                logs_debug.append(f"❌ Fichier `{fichier.name}` : Aucun agent du référentiel trouvé.")
                continue
            
            if agent_name_pdf not in planning_agents:
                planning_agents[agent_name_pdf] = {}

            # Déduction des 7 jours de la semaine via le nom du fichier (ex: S43, S44)
            match_semaine = re.search(r'S([0-9]{1,2})', fichier.name.upper())
            if match_semaine:
                num_semaine = int(match_semaine.group(1))
                jan4 = datetime(2026, 1, 4)
                start_week1 = jan4 - timedelta(days=jan4.weekday())
                start_target = start_week1 + timedelta(weeks=num_semaine - 1)
                jours_semaine = [(start_target + timedelta(days=i)).strftime('%d/%m/%Y'] for i in range(7)]
                
                semaine_agent = {j: {"statut": "REPOS", "intervalles": []} for j in jours_semaine}
                
                # Découpage du texte par date pour isoler chaque jour de la grille Comète
                # On repère les positions de chaque date (ex: "19/10", "20/10", etc.) dans le texte
                positions_dates = []
                for j_str in jours_semaine:
                    dt = datetime.strptime(j_str, '%d/%m/%Y')
                    short_d = dt.strftime('%d/%m')
                    pos = texte_complet.find(j_str)
                    if pos == -1:
                        pos = texte_complet.find(short_d)
                    positions_dates.append((j_str, pos))
                
                # S'il y a des positions valides, on découpe le texte par blocs de jours
                # Sinon on utilise une répartition séquentielle propre
                valid_blocks = [p[1] for p in positions_dates if p[1] != -1]
                
                if len(valid_blocks) >= 3:
                    # Découpage par tranches de texte entre chaque date
                    for idx, (j_str, pos) in enumerate(positions_dates):
                        if pos == -1:
                            continue
                        # Définition de la fin du bloc (début du jour suivant ou fin du texte)
                        next_pos = len(texte_complet)
                        for next_idx in range(idx + 1, len(positions_dates)):
                            if positions_dates[next_idx][1] != -1:
                                next_pos = positions_dates[next_idx][1]
                                break
                        
                        bloc_jour = texte_complet[pos:next_pos]
                        
                        # Extraction unique des paires d'heures dans ce bloc de jour
                        hours_in_block = re.findall(r'\b([0-2][0-9]:[0-5][0-9])\b', bloc_jour)
                        seen_pairs = set()
                        
                        i = 0
                        while i < len(hours_in_block) - 1:
                            h1 = hours_in_block[i]
                            h2 = hours_in_block[i+1]
                            pair_key = (h1, h2)
                            
                            if pair_key not in seen_pairs:
                                try:
                                    t1 = datetime.strptime(h1, '%H:%M')
                                    t2 = datetime.strptime(h2, '%H:%M')
                                    diff_sec = (t2 - t1).total_seconds()
                                    if diff_sec <= 0:
                                        diff_sec += 24 * 3600
                                    duree = diff_sec / 3600.0
                                    
                                    if 1.0 <= duree <= 14.0:
                                        seen_pairs.add(pair_key)
                                        dt_deb = datetime.strptime(f"{j_str} {h1}", '%d/%m/%Y %H:%M')
                                        dt_fin = datetime.strptime(f"{j_str} {h2}", '%d/%m/%Y %H:%M')
                                        if dt_fin <= dt_deb:
                                            dt_fin += timedelta(days=1)
                                        
                                        semaine_agent[j_str]["statut"] = "TRAVAIL"
                                        if (dt_deb, dt_fin) not in semaine_agent[j_str]["intervalles"]:
                                            semaine_agent[j_str]["intervalles"].append((dt_deb, dt_fin))
                                        i += 2
                                        continue
                                except Exception:
                                    pass
                            i += 1
                else:
                    # Fallback propre : extraction globale et filtrage strict des paires uniques
                    all_hours = re.findall(r'\b([0-2][0-9]:[0-5][0-9])\b', texte_complet)
                    unique_pairs = []
                    seen = set()
                    i = 0
                    while i < len(all_hours) - 1:
                        h1, h2 = all_hours[i], all_hours[i+1]
                        if (h1, h2) not in seen:
                            try:
                                t1, t2 = datetime.strptime(h1, '%H:%M'), datetime.strptime(h2, '%H:%M')
                                diff = (t2 - t1).total_seconds()
                                if diff <= 0: diff += 24 * 3600
                                if 1.0 <= (diff / 3600.0) <= 14.0:
                                    seen.add((h1, h2))
                                    unique_pairs.append((h1, h2))
                                    i += 2
                                    continue
                            except:
                                pass
                        i += 1
                    
                    # Répartition sur les jours ouvrés
                    for idx_p, (h1, h2) in enumerate(unique_pairs):
                        if idx_p < len(jours_semaine):
                            j_target = jours_semaine[idx_p]
                            dt_deb = datetime.strptime(f"{j_target} {h1}", '%d/%m/%Y %H:%M')
                            dt_fin = datetime.strptime(f"{j_target} {h2}", '%d/%m/%Y %H:%M')
                            if dt_fin <= dt_deb: dt_fin += timedelta(days=1)
                            semaine_agent[j_target]["statut"] = "TRAVAIL"
                            semaine_agent[j_target]["intervalles"].append((dt_deb, dt_fin))

                planning_agents[agent_name_pdf].update(semaine_agent)
                logs_debug.append(f"✅ Fichier `{fichier.name}` ({agent_name_pdf}) : Analysé et découpé par date avec succès.")
            else:
                logs_debug.append(f"⚠️ Fichier `{fichier.name}` : Semaine introuvable dans le nom.")

        except Exception as e:
            logs_debug.append(f"⚠️ Erreur lecture `{fichier.name}` : {e}")

with st.expander("🔍 Journal de diagnostic des PDF", expanded=False):
    for log in logs_debug:
        st.write(log)

# ---------------------------------------------------------
# 3. GÉNÉRATION DU TABLEAU ET CONTRÔLE RÉGLEMENTAIRE
# ---------------------------------------------------------
st.subheader("📋 Liste des Disponibilités & Opportunités (Contrôle Réglementaire)")

tableau_resultats = []
tous_agents = df_agents[["Contrats", "Agent"]].drop_duplicates().to_dict(orient="records")

for item in tous_agents:
    contrat_nom = item["Contrats"]
    agent_nom = item["Agent"]
    
    matched_schedule = {}
    for pdf_name, schedule_dict in planning_agents.items():
        if noms_sont_compatibles(agent_nom, pdf_name):
            matched_schedule.update(schedule_dict)
            break
    
    if matched_schedule:
        dates_triees = sorted(matched_schedule.keys(), key=lambda x: datetime.strptime(x, '%d/%m/%Y'))
        
        jours_repos_total = sum(1 for d in dates_triees if matched_schedule[d]["statut"] == "REPOS")
        
        if jours_repos_total < 1:
            st.warning(f"⚠️ **Alerte Réglementaire pour {agent_nom}** : Cet agent n'a aucun jour de repos répertorié cette semaine.")

        for idx_d, d in enumerate(dates_triees):
            info_jour = matched_schedule[d]
            statut = info_jour["statut"]
            dt_jour = datetime.strptime(d, '%d/%m/%Y')
            
            if statut == "REPOS":
                creneau_texte = "Journée complète (00h00 - 24h00)"
                opportunite = "🟢 Jour de Repos"
                
                if idx_d > 0:
                    veille_d = dates_triees[idx_d - 1]
                    info_veille = matched_schedule.get(veille_d, {})
                    intervalles_veille = info_veille.get("intervalles", [])
                    if intervalles_veille:
                        derniere_fin_veille = max([iv[1] for iv in intervalles_veille])
                        debut_autorise = derniere_fin_veille + timedelta(hours=11)
                        if debut_autorise.date() == dt_jour.date():
                            heure_min_str = debut_autorise.strftime('%H:%M')
                            dt_fin_max = min(debut_autorise + timedelta(hours=8), datetime.combine(dt_jour.date(), datetime.max.time()) - timedelta(hours=1))
                            creneau_texte = f"De {heure_min_str} à {dt_fin_max.strftime('%H:%M')} (Repos 11h respecté après fin à {derniere_fin_veille.strftime('%H:%M')})"
            else:
                intervalles = info_jour["intervalles"]
                heures_faites = sum([(iv[1] - iv[0]).total_seconds() for iv in intervalles]) / 3600.0
                
                if heures_faites >= 10.0:
                    creneau_texte = f"Déjà {round(heures_faites, 2)}h faites ce jour (Complet)"
                    opportunite = "🔴 Complet (10h atteint)"
                else:
                    derniere_fin = max([iv[1] for iv in intervalles])
                    heure_debut_str = derniere_fin.strftime('%H:%M')
                    heures_restantes = max(0.0, 10.0 - heures_faites)
                    dt_fin_pot = derniere_fin + timedelta(hours=heures_restantes)
                    creneau_texte = f"De {heure_debut_str} à {dt_fin_pot.strftime('%H:%M')} ({round(heures_restantes, 2)}h max, déjà {round(heures_faites, 2)}h faites)"
                    opportunite = "🟡 Heures sup / Jour travaillé"
            
            tableau_resultats.append({
                "Contrats": contrat_nom,
                "Agent": agent_nom,
                "Date": d,
                "Type d'opportunité": opportunite,
                "Créneau horaire / Heures possibles": creneau_texte,
                "Dernier recours": ""
            })

if tableau_resultats:
    df_table = pd.DataFrame(tableau_resultats)
    st.data_editor(
        df_table,
        column_config={
            "Dernier recours": st.column_config.TextColumn(
                "Dernier recours (Saisie quotidienne)",
                help="Saisir manuellement des notes",
                max_chars=150
            )
        },
        disabled=["Contrats", "Agent", "Date", "Type d'opportunité", "Créneau horaire / Heures possibles"],
        hide_index=True,
        use_container_width=True
    )
    st.success("✅ Tableau affiché avec succès !")
else:
    st.warning("⚠️ Aucun résultat dans le tableau. Vérifiez vos fichiers PDF importés.")