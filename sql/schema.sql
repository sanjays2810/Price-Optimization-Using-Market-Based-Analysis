-- MySQL schema for price_optimization_db (generated from the SQLAlchemy models)
-- The application creates all of this automatically on first start; run this file only if you prefer manual setup.
CREATE DATABASE IF NOT EXISTS price_optimization_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE price_optimization_db;

CREATE TABLE analysis_reports (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	dataset_id INTEGER, 
	report_type VARCHAR(50) NOT NULL, 
	file_format VARCHAR(10) NOT NULL, 
	file_name VARCHAR(255) NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
);

CREATE TABLE categories (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(100) NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE uploaded_datasets (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(150) NOT NULL, 
	filename VARCHAR(255) NOT NULL, 
	source VARCHAR(20) NOT NULL, 
	rows_raw INTEGER NOT NULL, 
	rows_clean INTEGER NOT NULL, 
	date_min DATE, 
	date_max DATE, 
	is_active BOOL NOT NULL, 
	validation_report TEXT, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
);

CREATE TABLE users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	username VARCHAR(50) NOT NULL, 
	full_name VARCHAR(100) NOT NULL, 
	email VARCHAR(120) NOT NULL, 
	`role` VARCHAR(30) NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (username)
);

CREATE TABLE products (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	dataset_id INTEGER NOT NULL, 
	category_id INTEGER NOT NULL, 
	product_code VARCHAR(60) NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_product_dataset_code UNIQUE (dataset_id, product_code), 
	FOREIGN KEY(dataset_id) REFERENCES uploaded_datasets (id) ON DELETE CASCADE, 
	FOREIGN KEY(category_id) REFERENCES categories (id)
);
CREATE INDEX ix_products_category_id ON products (category_id);
CREATE INDEX ix_products_dataset_id ON products (dataset_id);

CREATE TABLE competitor_prices (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	dataset_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	record_date DATE NOT NULL, 
	location VARCHAR(100), 
	competitor_price DOUBLE NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(dataset_id) REFERENCES uploaded_datasets (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);
CREATE INDEX ix_comp_ds_prod_date ON competitor_prices (dataset_id, product_id, record_date);

CREATE TABLE market_data (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	dataset_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	record_date DATE NOT NULL, 
	historical_price DOUBLE NOT NULL, 
	cost_price DOUBLE NOT NULL, 
	selling_price DOUBLE NOT NULL, 
	demand_qty DOUBLE NOT NULL, 
	supply_qty DOUBLE NOT NULL, 
	competitor_price DOUBLE NOT NULL, 
	sales_qty DOUBLE NOT NULL, 
	inventory DOUBLE NOT NULL, 
	season VARCHAR(40), 
	location VARCHAR(100), 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(dataset_id) REFERENCES uploaded_datasets (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);
CREATE INDEX ix_market_ds_prod_date ON market_data (dataset_id, product_id, record_date);

CREATE TABLE optimization_results (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	dataset_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	inputs TEXT, 
	result TEXT, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(dataset_id) REFERENCES uploaded_datasets (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);
CREATE INDEX ix_optimization_results_dataset_id ON optimization_results (dataset_id);
CREATE INDEX ix_optimization_results_product_id ON optimization_results (product_id);

CREATE TABLE prediction_results (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	dataset_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	algorithm VARCHAR(40) NOT NULL, 
	horizon_days INTEGER NOT NULL, 
	metrics TEXT, 
	forecast TEXT, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(dataset_id) REFERENCES uploaded_datasets (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);
CREATE INDEX ix_prediction_results_dataset_id ON prediction_results (dataset_id);
CREATE INDEX ix_prediction_results_product_id ON prediction_results (product_id);

CREATE TABLE sales_records (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	dataset_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	record_date DATE NOT NULL, 
	sales_qty DOUBLE NOT NULL, 
	revenue DOUBLE NOT NULL, 
	total_cost DOUBLE NOT NULL, 
	profit DOUBLE NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(dataset_id) REFERENCES uploaded_datasets (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);
CREATE INDEX ix_sales_ds_prod_date ON sales_records (dataset_id, product_id, record_date);
