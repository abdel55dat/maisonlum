USE ecommerce_rfm;

CREATE TABLE IF NOT EXISTS clients (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    pays VARCHAR(100) NOT NULL,
    ville VARCHAR(100),
    date_inscription DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS produits (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(150) NOT NULL,
    categorie VARCHAR(100) NOT NULL,
    prix DECIMAL(10, 2) NOT NULL,
    stock INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS commandes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    client_id INT NOT NULL,
    date_commande DATE NOT NULL,
    statut VARCHAR(50) DEFAULT 'livrée',
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

CREATE TABLE IF NOT EXISTS commandes_produits (
    commande_id INT NOT NULL,
    produit_id INT NOT NULL,
    quantite INT NOT NULL DEFAULT 1,
    prix_unitaire DECIMAL(10, 2) NOT NULL,
    PRIMARY KEY (commande_id, produit_id),
    FOREIGN KEY (commande_id) REFERENCES commandes(id),
    FOREIGN KEY (produit_id) REFERENCES produits(id)
);

CREATE TABLE IF NOT EXISTS segments_rfm (
    id INT AUTO_INCREMENT PRIMARY KEY,
    client_id INT NOT NULL UNIQUE,
    recence INT,
    frequence INT,
    montant_total DECIMAL(10, 2),
    score_r INT,
    score_f INT,
    score_m INT,
    segment VARCHAR(50),
    date_calcul DATE,
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

CREATE OR REPLACE VIEW vue_commandes_detail AS
SELECT c.id AS commande_id, cl.nom AS client_nom, cl.email, cl.pays,
    c.date_commande, SUM(cp.quantite * cp.prix_unitaire) AS montant_commande
FROM commandes c
JOIN clients cl ON cl.id = c.client_id
JOIN commandes_produits cp ON cp.commande_id = c.id
GROUP BY c.id, cl.nom, cl.email, cl.pays, c.date_commande;
