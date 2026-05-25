"""
dashboard.py — MaisonLum | Dashboard RFM interactif
----------------------------------------------------
Lance avec : python dashboard.py
Puis ouvre http://127.0.0.1:8050 dans ton navigateur
"""

import os
import mysql.connector
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output
from dotenv import load_dotenv

load_dotenv()


# -------------------------------------------------------
# CHARGEMENT DES DONNÉES
# -------------------------------------------------------

def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


def charger_dashboard_data():
    conn = get_connection()

    # données RFM + infos client
    rfm = pd.read_sql("""
        SELECT
            s.client_id,
            cl.nom,
            cl.pays,
            s.recence,
            s.frequence,
            s.montant_total,
            s.score_r,
            s.score_f,
            s.score_m,
            s.segment
        FROM segments_rfm s
        JOIN clients cl ON cl.id = s.client_id
    """, conn)

    # CA par mois pour le graphique temporel
    ca_mensuel = pd.read_sql("""
        SELECT
            DATE_FORMAT(c.date_commande, '%Y-%m') AS mois,
            ROUND(SUM(cp.quantite * cp.prix_unitaire), 2) AS ca
        FROM commandes c
        JOIN commandes_produits cp ON cp.commande_id = c.id
        GROUP BY mois
        ORDER BY mois
    """, conn)

    conn.close()
    return rfm, ca_mensuel


rfm, ca_mensuel = charger_dashboard_data()


# -------------------------------------------------------
# INITIALISATION DE L'APP
# -------------------------------------------------------

app = Dash(__name__)
app.title = "MaisonLum — Dashboard RFM"

segments_disponibles = ["Tous"] + sorted(rfm["segment"].unique().tolist())
pays_disponibles = ["Tous"] + sorted(rfm["pays"].unique().tolist())

couleurs_segments = {
    "Champion": "#2ecc71",
    "Fidèle":   "#3498db",
    "À risque": "#f39c12",
    "Perdu":    "#e74c3c"
}


# -------------------------------------------------------
# LAYOUT
# -------------------------------------------------------

app.layout = html.Div(style={"fontFamily": "Inter, sans-serif", "backgroundColor": "#f8f9fa", "minHeight": "100vh"}, children=[

    # header
    html.Div(style={"backgroundColor": "#1a1a2e", "padding": "24px 40px", "marginBottom": "30px"}, children=[
        html.H1("MaisonLum — Segmentation RFM", style={"color": "white", "margin": 0, "fontSize": "24px"}),
        html.P("Analyse comportementale des clients · Boutique e-commerce déco", style={"color": "#aaa", "margin": "4px 0 0 0", "fontSize": "14px"})
    ]),

    # filtres
    html.Div(style={"padding": "0 40px", "display": "flex", "gap": "20px", "marginBottom": "24px", "flexWrap": "wrap"}, children=[
        html.Div([
            html.Label("Segment", style={"fontWeight": "600", "fontSize": "13px", "marginBottom": "6px", "display": "block"}),
            dcc.Dropdown(
                id="filtre-segment",
                options=[{"label": s, "value": s} for s in segments_disponibles],
                value="Tous",
                clearable=False,
                style={"width": "220px"}
            )
        ]),
        html.Div([
            html.Label("Pays", style={"fontWeight": "600", "fontSize": "13px", "marginBottom": "6px", "display": "block"}),
            dcc.Dropdown(
                id="filtre-pays",
                options=[{"label": p, "value": p} for p in pays_disponibles],
                value="Tous",
                clearable=False,
                style={"width": "220px"}
            )
        ])
    ]),

    # KPIs
    html.Div(id="kpis", style={"padding": "0 40px", "display": "flex", "gap": "16px", "marginBottom": "28px", "flexWrap": "wrap"}),

    # graphiques ligne 1
    html.Div(style={"padding": "0 40px", "display": "flex", "gap": "20px", "marginBottom": "20px", "flexWrap": "wrap"}, children=[
        html.Div(dcc.Graph(id="graph-segments"), style={"flex": "1", "minWidth": "300px", "backgroundColor": "white", "borderRadius": "10px", "padding": "16px", "boxShadow": "0 1px 4px rgba(0,0,0,0.08)"}),
        html.Div(dcc.Graph(id="graph-ca-mensuel"), style={"flex": "2", "minWidth": "400px", "backgroundColor": "white", "borderRadius": "10px", "padding": "16px", "boxShadow": "0 1px 4px rgba(0,0,0,0.08)"})
    ]),

    # graphique ligne 2 — scatter RFM
    html.Div(style={"padding": "0 40px", "marginBottom": "40px"}, children=[
        html.Div(dcc.Graph(id="graph-scatter"), style={"backgroundColor": "white", "borderRadius": "10px", "padding": "16px", "boxShadow": "0 1px 4px rgba(0,0,0,0.08)"})
    ])
])


# -------------------------------------------------------
# CALLBACKS
# -------------------------------------------------------

@app.callback(
    Output("kpis", "children"),
    Output("graph-segments", "figure"),
    Output("graph-ca-mensuel", "figure"),
    Output("graph-scatter", "figure"),
    Input("filtre-segment", "value"),
    Input("filtre-pays", "value")
)
def mettre_a_jour(segment_selectionne, pays_selectionne):
    # filtrage du dataframe selon les dropdowns
    df = rfm.copy()

    if segment_selectionne != "Tous":
        df = df[df["segment"] == segment_selectionne]
    if pays_selectionne != "Tous":
        df = df[df["pays"] == pays_selectionne]

    # --- KPIs
    nb_clients   = len(df)
    ca_total     = df["montant_total"].sum()
    panier_moyen = (ca_total / df["frequence"].sum()) if df["frequence"].sum() > 0 else 0
    recence_moy  = df["recence"].mean() if len(df) > 0 else 0

    def kpi_card(titre, valeur, couleur="#1a1a2e"):
        return html.Div(style={
            "backgroundColor": "white", "borderRadius": "10px",
            "padding": "20px 24px", "flex": "1", "minWidth": "160px",
            "boxShadow": "0 1px 4px rgba(0,0,0,0.08)",
            "borderTop": f"4px solid {couleur}"
        }, children=[
            html.P(titre, style={"margin": 0, "fontSize": "12px", "color": "#888", "textTransform": "uppercase", "letterSpacing": "0.5px"}),
            html.H2(valeur, style={"margin": "8px 0 0 0", "fontSize": "26px", "color": "#1a1a2e"})
        ])

    kpis = [
        kpi_card("Clients", str(nb_clients), "#3498db"),
        kpi_card("CA total", f"{ca_total:,.0f} €", "#2ecc71"),
        kpi_card("Panier moyen", f"{panier_moyen:,.0f} €", "#f39c12"),
        kpi_card("Récence moy.", f"{recence_moy:.0f} j", "#e74c3c")
    ]

    # --- Graphique 1 : répartition des segments (donut)
    if len(df) > 0:
        seg_counts = df["segment"].value_counts().reset_index()
        seg_counts.columns = ["segment", "count"]
        fig_segments = px.pie(
            seg_counts, values="count", names="segment",
            hole=0.5,
            color="segment",
            color_discrete_map=couleurs_segments,
            title="Répartition par segment"
        )
        fig_segments.update_traces(textposition="outside", textinfo="percent+label")
        fig_segments.update_layout(showlegend=False, margin=dict(t=50, b=10, l=10, r=10), height=320)
    else:
        fig_segments = go.Figure()
        fig_segments.update_layout(title="Répartition par segment — aucune donnée")

    # --- Graphique 2 : CA mensuel (courbe)
    fig_ca = px.line(
        ca_mensuel, x="mois", y="ca",
        title="Chiffre d'affaires mensuel",
        markers=True,
        labels={"mois": "Mois", "ca": "CA (€)"},
        color_discrete_sequence=["#3498db"]
    )
    fig_ca.update_layout(margin=dict(t=50, b=30), height=320)
    fig_ca.update_xaxes(tickangle=45)

    # --- Graphique 3 : scatter Fréquence vs Montant coloré par segment
    if len(df) > 0:
        fig_scatter = px.scatter(
            df, x="frequence", y="montant_total",
            color="segment",
            color_discrete_map=couleurs_segments,
            hover_data=["nom", "pays", "recence"],
            size="montant_total",
            title="Fréquence vs Montant total — vue client",
            labels={"frequence": "Nombre de commandes", "montant_total": "CA total (€)"}
        )
        fig_scatter.update_layout(margin=dict(t=50, b=30), height=380)
    else:
        fig_scatter = go.Figure()
        fig_scatter.update_layout(title="Fréquence vs Montant — aucune donnée")

    return kpis, fig_segments, fig_ca, fig_scatter


# -------------------------------------------------------
# LANCEMENT
# -------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
