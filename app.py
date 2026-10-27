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

st.title("🚨 SOS Remplacement - Assistant (Correction Priorité Travail & Cumul Heures)")
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
# 2. ANALYSE FINE DES PLANNINGS PDF
# ---------------------------------------------------------
MOTIFS_ABSENCE = [
    r'\bCP\b', r'\bCONG[EÉ]S?\b', 
    r'\bMALADIE\b', r'\bMAL\.?\b', 
    r'\bAT\b', r'\bACCIDENT\b', 
    r'\bSANS SOLDE\b', 
    r'\bMATERNIT[EÉ]\b', 
    r'\bD[EÉ]C[EÈ]S\b', 
    r'\bNAISSANCE\b', 
    r'\bMARIAGE\b', 
    r'\bMISE \u00c0 PIED\b', r'\bMISE A PIED\b'
]

planning_agents = {}
agent_types_contrat = {}

def noms_sont_compatibles(excel_name, pdf_name):
    e_words = set(excel_name.upper().split())
    p_words = set(pdf_name.upper().split())
    return len(e_words.intersection(p_words)) >= min(len(e_words), len(p_words))

def parse_date_safe(date_str):
    for fmt in ('%d/%m/%Y', '%d/%m/%y', '%d-%m-%Y', '%d/%m'):
        try:
            dt = datetime.strptime(date_str, fmt)
            if fmt == '%d/%m':
                dt = dt.replace(year=datetime.now().year)
            return dt
        except ValueError:
            continue
    return None

if fichiers_planning:
    for fichier in fichiers_planning:
        try:
            reader = pypdf.PdfReader(fichier)
            texte_complet = ""
            lines = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    texte_complet += t + "\n"
                    lines.extend(t.split('\n'))
            
            text_upper = texte_complet.upper()
            
            period_match = re.search(r'DU\s+([0-9]{2}/[0-9]{2}/[0-9]{4})\s+AU\s+([0-9]{2}/[0-9]{2}/[0-9]{4})', text_upper)
            pdf_start_dt, pdf_end_dt = None, None
            if period_match:
                pdf_start_dt = parse_date_safe(period_match.group(1))
                pdf_end_dt = parse_date_safe(period_match.group(2))
            
            agent_name_pdf = None
            for ex_agent in df_agents["Agent"].unique():
                if ex_agent.upper() in text_upper:
                    agent_name_pdf = ex_agent.upper()
                    break
            
            if not agent_name_pdf:
                continue
            
            if agent_name_pdf not in planning_agents:
                planning_agents[agent_name_pdf] = {}

            if "TEMPS PARTIEL" in text_upper:
                agent_types_contrat[agent_name_pdf] = "Temps partiel"
            elif "TEMPS PLEIN" in text_upper:
                agent_types_contrat[agent_name_pdf] = "Temps plein"
            elif "LISSÉ" in text_upper or "LISSE" in text_upper:
                agent_types_contrat[agent_name_pdf] = "Lissé"
            else:
                agent_types_contrat[agent_name_pdf] = "Temps plein"

            current_date = None
            for line in lines:
                line_up = line.upper()
                
                date_match = re.search(r'\b([0-9]{2}/[0-9]{2}(?:/[0-9]{2,4})?)\b', line)
                if date_match:
                    d_raw = date_match.group(1)
                    parsed_dt = parse_date_safe(d_raw)
                    if parsed_dt:
                        if pdf_start_dt and pdf_end_dt:
                            if not (pdf_start_dt <= parsed_dt <= pdf_end_dt):
                                current_date = None
                                continue
                        current_date = parsed_dt.strftime('%d/%m/%Y')
                
                if current_date:
                    is_absent = any(re.search(motif, line_up) for motif in MOTIFS_ABSENCE)
                    
                    # Extraction de TOUTES les paires d'heures présentes sur la ligne
                    hours_found = re.findall(r'\b([0-2]?[0-9][:H][0-5][0-9])\b', line)
                    intervalles = []
                    
                    if len(hours_found) >= 2:
                        for idx_h in range(0, len(hours_found) - 1, 2):
                            try:
                                h1 = hours_found[idx_h].replace('H', ':')
                                h2 = hours_found[idx_h+1].replace('H', ':')
                                dt_deb = datetime.strptime(f"{current_date} {h1}", '%d/%m/%Y %H:%M')
                                dt_fin = datetime.strptime(f"{current_date} {h2}", '%d/%m/%Y %H:%M')
                                if dt_fin <= dt_deb:
                                    dt_fin += timedelta(days=1)
                                
                                if (dt_fin - dt_deb).total_seconds() <= 16 * 3600:
                                    intervalles.append((dt_deb, dt_fin))
                            except Exception:
                                pass

                    # RÈGLE D'OR : Si on trouve des heures de travail, c'est TRAVAIL (prioritaire sur "REPOS")
                    has_repos = "REPOS" in line_up and len(intervalles) == 0

                    if is_absent:
                        planning_agents[agent_name_pdf][current_date] = {"statut": "ABSENT", "intervalles": []}
                    elif intervalles:
                        # Si le jour existait déjà en mode REPOS par erreur, on l'écrase par TRAVAIL avec tous ses intervalles cumulés
                        if current_date in planning_agents[agent_name_pdf] and planning_agents[agent_name_pdf][current_date]["statut"] == "REPOS":
                            planning_agents[agent_name_pdf][current_date]["intervalles"] = []
                        
                        if current_date not in planning_agents[agent_name_pdf] or planning_agents[agent_name_pdf][current_date]["statut"] != "TRAVAIL":
                            planning_agents[agent_name_pdf][current_date] = {"statut": "TRAVAIL", "intervalles": []}
                        
                        planning_agents[agent_name_pdf][current_date]["intervalles"].extend(intervalles)
                        
                    elif has_repos and current_date not in planning_agents[agent_name_pdf]:
                        planning_agents[agent_name_pdf][current_date] = {"statut": "REPOS", "intervalles": []}

        except Exception as e:
            pass

# ---------------------------------------------------------
# 3. GÉNÉRATION DU TABLEAU DES DISPONIBILITÉS
# ---------------------------------------------------------
st.subheader("📋 Liste des Disponibilités & Heures Complémentaires (Fiabilisée)")

if not df_agents.empty:
    tous_agents = df_agents[["Contrats", "Agent"]].drop_duplicates().to_dict(orient="records")
    tableau_resultats = []
    
    for item in tous_agents:
        contrat_nom = item["Contrats"]
        agent_nom = item["Agent"]
        
        matched_schedule = {}
        for pdf_name, schedule_dict in planning_agents.items():
            if noms_sont_compatibles(agent_nom, pdf_name):
                matched_schedule.update(schedule_dict)
                break
        
        if matched_schedule:
            dates_triees = sorted(
                [d for d in matched_schedule.keys() if parse_date_safe(d) is not None], 
                key=lambda x: parse_date_safe(x)
            )
            
            for i, d in enumerate(dates_triees):
                info_jour = matched_schedule[d]
                statut = info_jour["statut"]
                dt_jour = parse_date_safe(d)
                
                # CAS 1 : JOUR DE REPOS
                if statut == "REPOS":
                    creneau_texte = "Journée complète (00h00 - 24h00)"
                    
                    if i > 0:
                        veille_d = dates_triees[i-1]
                        info_veille = matched_schedule.get(veille_d, {})
                        intervalles_veille = info_veille.get("intervalles", [])
                        if intervalles_veille:
                            derniere_fin_veille = max([iv[1] for iv in intervalles_veille])
                            debut_autorise = derniere_fin_veille + timedelta(hours=11)
                            
                            if debut_autorise.date() == dt_jour.date():
                                heure_min_str = debut_autorise.strftime('%H:%M')
                                creneau_texte = f"Disponible à partir de {heure_min_str} (Repos 11h après fin à {derniere_fin_veille.strftime('%H:%M')})"
                            elif debut_autorise > dt_jour + timedelta(days=1):
                                continue
                    
                    tableau_resultats.append({
                        "Contrats": contrat_nom,
                        "Agent": agent_nom,
                        "Date": d,
                        "Type d'opportunité": "🟢 Jour de Repos",
                        "Créneau horaire / Heures possibles": creneau_texte,
                        "Dernier recours": ""
                    })

                # CAS 2 : JOUR TRAVAILLÉ (Heures complémentaires)
                elif statut == "TRAVAIL":
                    intervalles = info_jour["intervalles"]
                    if not intervalles:
                        continue 
                    
                    total_secondes_travail = sum([(iv[1] - iv[0]).total_seconds() for iv in intervalles])
                    heures_deja_travaillees = total_secondes_travail / 3600.0
                    
                    if heures_deja_travaillees >= 10.0:
                        continue
                    
                    heures_restantes_jour = 10.0 - heures_deja_travaillees
                    derniere_fin_ce_jour = max([iv[1] for iv in intervalles])
                    
                    fin_max_quota = derniere_fin_ce_jour + timedelta(hours=heures_restantes_jour)
                    
                    fin_max_lendemain = datetime.max
                    if i < len(dates_triees) - 1:
                        lendemain_d = dates_triees[i+1]
                        info_lendemain = matched_schedule.get(lendemain_d, {})
                        if info_lendemain.get("intervalles"):
                            premier_debut_lendemain = min([iv[0] for iv in info_lendemain["intervalles"]])
                            fin_max_lendemain = premier_debut_lendemain - timedelta(hours=11)
                    
                    fin_fenetre_max = min(fin_max_quota, fin_max_lendemain)
                    debut_fenetre = derniere_fin_ce_jour
                    duree_max_possible_h = (fin_fenetre_max - debut_fenetre).total_seconds() / 3600.0
                    
                    if debut_fenetre.hour >= 23 or debut_fenetre.hour < 5:
                        continue
                    
                    if duree_max_possible_h <= 0.25:
                        continue
                    
                    heure_debut_str = debut_fenetre.strftime('%H:%M')
                    dt_fin_potentielle = debut_fenetre + timedelta(hours=duree_max_possible_h)
                    heure_fin_str = dt_fin_potentielle.strftime('%H:%M')
                    
                    creneau_texte = f"De {heure_debut_str} à {heure_fin_str} ({round(duree_max_possible_h, 2)}h max, déjà {round(heures_deja_travaillees, 2)}h faites)"
                    
                    tableau_resultats.append({
                        "Contrats": contrat_nom,
                        "Agent": agent_nom,
                        "Date": d,
                        "Type d'opportunité": "🟡 Heures sup / Jour travaillé",
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
                    help="Saisir manuellement des notes ou affectations au quotidien",
                    max_chars=150,
                )
            },
            disabled=["Contrats", "Agent", "Date", "Type d'opportunité", "Créneau horaire / Heures possibles"],
            hide_index=True,
            use_container_width=True
        )
        
        st.info("💡 **Correction active :** Le cumul réel des heures de travail prime sur les faux statuts 'REPOS', et les limites du lendemain bloquent correctement les journées trop chargées (comme le 24/10).")
    else:
        st.warning("⚠️ Aucune disponibilité trouvée.")
else:
    st.warning("⚠️ Veuillez importer le fichier référentiel.")