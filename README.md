# MaisonLum — Segmentation RFM clients

Projet réalisé dans le cadre du cours Algo & BDD — MSc2 Manager Data Marketing (INSEEC, 2026).

## Contexte et problématique

J'ai choisi de travailler sur une boutique e-commerce fictive spécialisée dans la décoration intérieure : MaisonLum.

> *Comment identifier les clients les plus précieux, détecter ceux qui commencent à se désengager, et adapter la stratégie marketing en conséquence ?*

## Structure du projet
## Schéma de la base de données

5 tables : clients, produits, commandes, commandes_produits (many-to-many), segments_rfm

## Installation

```bash
git clone https://github.com/abdel55dat/maisonlum.git
cd maisonlum
pip install -r requirements.txt
cp .env.example .env
python pipeline.py
python dashboard.py
```
