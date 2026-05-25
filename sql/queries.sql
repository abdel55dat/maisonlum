USE ecommerce_rfm;

-- 1. CA par pays (jointure 3 tables)
SELECT cl.pays, COUNT(DISTINCT c.id) AS nb_commandes,
    COUNT(DISTINCT c.client_id) AS nb_clients,
    ROUND(SUM(cp.quantite * cp.prix_unitaire), 2) AS ca_total
FROM clients cl
JOIN commandes c ON c.client_id = cl.id
JOIN commandes_produits cp ON cp.commande_id = c.id
GROUP BY cl.pays ORDER BY ca_total DESC;

-- 2. Clients avec plus de 3 commandes (HAVING)
SELECT cl.nom, cl.email, cl.pays, COUNT(c.id) AS nb_commandes
FROM clients cl
JOIN commandes c ON c.client_id = cl.id
GROUP BY cl.id, cl.nom, cl.email, cl.pays
HAVING COUNT(c.id) > 3 ORDER BY nb_commandes DESC;

-- 3. Top 5 produits (LIMIT)
SELECT p.nom AS produit, p.categorie,
    SUM(cp.quantite) AS quantite_vendue,
    ROUND(SUM(cp.quantite * cp.prix_unitaire), 2) AS revenu_genere
FROM produits p
JOIN commandes_produits cp ON cp.produit_id = p.id
GROUP BY p.id, p.nom, p.categorie
ORDER BY quantite_vendue DESC LIMIT 5;

-- 4. Clients inactifs depuis plus d'un an
SELECT cl.nom, cl.email, cl.pays,
    MAX(c.date_commande) AS derniere_commande,
    DATEDIFF(CURDATE(), MAX(c.date_commande)) AS jours_inactif
FROM clients cl
JOIN commandes c ON c.client_id = cl.id
GROUP BY cl.id, cl.nom, cl.email, cl.pays
HAVING derniere_commande < DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
ORDER BY jours_inactif DESC;

-- 5. Panier moyen par client (CTE)
WITH commandes_montants AS (
    SELECT c.id AS commande_id, c.client_id, c.date_commande,
        SUM(cp.quantite * cp.prix_unitaire) AS montant
    FROM commandes c
    JOIN commandes_produits cp ON cp.commande_id = c.id
    GROUP BY c.id, c.client_id, c.date_commande
)
SELECT cl.nom, cl.pays, COUNT(cm.commande_id) AS nb_commandes,
    ROUND(SUM(cm.montant), 2) AS ca_total,
    ROUND(AVG(cm.montant), 2) AS panier_moyen
FROM clients cl
JOIN commandes_montants cm ON cm.client_id = cl.id
GROUP BY cl.id, cl.nom, cl.pays
HAVING panier_moyen > 80 ORDER BY panier_moyen DESC;
