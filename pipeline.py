"""
pipeline.py — MaisonLum | Segmentation RFM clients
---------------------------------------------------
Ce script fait trois choses dans l'ordre :
  1. Se connecte à la base MySQL et charge les données de commandes
  2. Appelle l'API REST Countries pour enrichir chaque client avec
     sa région mondiale et sa devise locale
  3. Calcule les scores RFM et écrit les résultats dans la table segments_rfm

À lancer depuis le terminal : python pipeline.py
"""

import os
import math
from datetime import date

import mysql.connector
import pandas as pd
import requests
from dotenv import load_dotenv

# --- chargement des variables d'environnement (.env)
load_dotenv()


# -------------------------------------------------------
# CONNEXION À LA BASE
# -------------------------------------------------------

def get_connection():
    """Retourne une connexion MySQL à partir des variables .env"""
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )
    return conn


# -------------------------------------------------------
# CHARGEMENT DES DONNÉES
# -------------------------------------------------------

def charger_donnees(conn):
    """
    Charge les commandes depuis MySQL et retourne un DataFrame pandas.
    On récupère client_id, pays, date de commande et montant total par commande.
    """
    query = """
        SELECT
            cl.id           AS client_id,
            cl.nom,
            cl.email,
            cl.pays,
            c.date_commande,
            SUM(cp.quantite * cp.prix_unitaire) AS montant
        FROM clients cl
        JOIN commandes c ON c.client_id = cl.id
        JOIN commandes_produits cp ON cp.commande_id = c.id
        GROUP BY cl.id, cl.nom, cl.email, cl.pays, c.id, c.date_commande
        ORDER BY cl.id, c.date_commande
    """
    df = pd.read_sql(query, conn)
    df["date_commande"] = pd.to_datetime(df["date_commande"])
    print(f"  → {len(df)} lignes de commandes chargées pour {df['client_id'].nunique()} clients")
    return df


# -------------------------------------------------------
# ENRICHISSEMENT API — REST Countries
# -------------------------------------------------------

def enrichir_pays(pays_list):
    """
    Appelle l'API REST Countries (gratuite, pas de clé) pour récupérer
    la région et la devise de chaque pays présent dans la base.

    Retourne un dict : { "France": {"region": "Europe", "devise": "EUR"}, ... }
    """
    enrichissement = {}

    # mapping maison pour les noms en français → nom anglais attendu par l'API
    traductions = {
        "France": "France", "Belgique": "Belgium", "Suisse": "Switzerland",
        "Luxembourg": "Luxembourg", "Espagne": "Spain", "Italie": "Italy",
        "Pays-Bas": "Netherlands", "Danemark": "Denmark", "Allemagne": "Germany",
        "Royaume-Uni": "United Kingdom"
    }

    print(f"  → Appel API REST Countries pour {len(pays_list)} pays...")

    for pays_fr in pays_list:
        pays_en = traductions.get(pays_fr, pays_fr)
        try:
            url = f"https://restcountries.com/v3.1/name/{pays_en}?fullText=true&fields=name,region,currencies"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                data = response.json()[0]
                region = data.get("region", "Inconnue")
                # les devises sont dans un dict, on prend la première clé
                devises = data.get("currencies", {})
                devise = list(devises.keys())[0] if devises else "N/A"
                enrichissement[pays_fr] = {"region": region, "devise": devise}
            else:
                enrichissement[pays_fr] = {"region": "Inconnue", "devise": "N/A"}

        except Exception as e:
            # on ne bloque pas tout le pipeline si un appel API rate
            print(f"    ⚠ Erreur pour {pays_fr} : {e}")
            enrichissement[pays_fr] = {"region": "Inconnue", "devise": "N/A"}

    return enrichissement


# -------------------------------------------------------
# CALCUL RFM
# -------------------------------------------------------

def calculer_rfm(df):
    """
    Calcule les métriques RFM pour chaque client :
      - Récence  : nombre de jours depuis le dernier achat
      - Fréquence : nombre total de commandes
      - Montant  : chiffre d'affaires total généré

    Puis attribue un score de 1 à 4 pour chacune des 3 dimensions,
    et définit un segment lisible (Champion, Fidèle, À risque, Perdu).
    """
    aujourd_hui = pd.Timestamp(date.today())

    rfm = df.groupby(["client_id", "nom", "email", "pays"]).agg(
        derniere_commande=("date_commande", "max"),
        frequence=("date_commande", "count"),
        montant_total=("montant", "sum")
    ).reset_index()

    rfm["recence"] = (aujourd_hui - rfm["derniere_commande"]).dt.days

    # scores sur 4 niveaux avec pd.qcut (quartiles)
    # Récence : plus c'est petit (récent), meilleur le score → ordre inversé
    rfm["score_r"] = pd.qcut(rfm["recence"], q=4, labels=[4, 3, 2, 1]).astype(int)
    rfm["score_f"] = pd.qcut(rfm["frequence"].rank(method="first"), q=4, labels=[1, 2, 3, 4]).astype(int)
    rfm["score_m"] = pd.qcut(rfm["montant_total"].rank(method="first"), q=4, labels=[1, 2, 3, 4]).astype(int)

    rfm["score_total"] = rfm["score_r"] + rfm["score_f"] + rfm["score_m"]

    # segmentation lisible
    def attribuer_segment(row):
        if row["score_total"] >= 10:
            return "Champion"
        elif row["score_total"] >= 7:
            return "Fidèle"
        elif row["score_total"] >= 5:
            return "À risque"
        else:
            return "Perdu"

    rfm["segment"] = rfm.apply(attribuer_segment, axis=1)

    print(f"  → RFM calculé pour {len(rfm)} clients")
    print(rfm["segment"].value_counts().to_string())

    return rfm


# -------------------------------------------------------
# ÉCRITURE EN BASE
# -------------------------------------------------------

def ecrire_segments(conn, rfm, enrichissement):
    """
    Vide la table segments_rfm et réinsère les résultats frais.
    On fait un TRUNCATE + INSERT pour éviter les doublons à chaque run.
    """
    cursor = conn.cursor()
    cursor.execute("TRUNCATE TABLE segments_rfm")

    insert_query = """
        INSERT INTO segments_rfm
            (client_id, recence, frequence, montant_total,
             score_r, score_f, score_m, segment, date_calcul)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    lignes = []
    for _, row in rfm.iterrows():
        lignes.append((
            int(row["client_id"]),
            int(row["recence"]),
            int(row["frequence"]),
            float(round(row["montant_total"], 2)),
            int(row["score_r"]),
            int(row["score_f"]),
            int(row["score_m"]),
            row["segment"],
            date.today()
        ))

    cursor.executemany(insert_query, lignes)
    conn.commit()
    cursor.close()

    print(f"  → {len(lignes)} segments écrits dans la table segments_rfm")


# -------------------------------------------------------
# MAIN
# -------------------------------------------------------

if __name__ == "__main__":
    print("\n=== Pipeline MaisonLum — Segmentation RFM ===\n")

    conn = get_connection()
    print("✓ Connexion MySQL OK")

    print("\n[1/4] Chargement des données...")
    df = charger_donnees(conn)

    print("\n[2/4] Enrichissement API REST Countries...")
    pays_uniques = df["pays"].unique().tolist()
    enrichissement = enrichir_pays(pays_uniques)
    for pays, infos in enrichissement.items():
        print(f"    {pays} → {infos['region']} | {infos['devise']}")

    print("\n[3/4] Calcul RFM...")
    rfm = calculer_rfm(df)

    print("\n[4/4] Écriture des résultats en base...")
    ecrire_segments(conn, rfm, enrichissement)

    conn.close()
    print("\n✓ Pipeline terminé avec succès.\n")
