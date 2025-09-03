DROP TABLE IF EXISTS prices;
DROP TABLE IF EXISTS traders;
DROP TABLE IF EXISTS real_time_traders;
DROP TABLE IF EXISTS strategies;
DROP TABLE IF EXISTS real_time_strategies;
CREATE TABLE prices (
	init_timestamp DECIMAL(65,6),
	coin1 TINYTEXT,
	coin2 TINYTEXT,
	timer INT,
	prices LONGTEXT
);
CREATE TABLE traders (
	coin1 TINYTEXT,
	coin2 TINYTEXT,
	p_s_u FLOAT,
    e_p_u FLOAT,
    p_c_u FLOAT,
    p_s_d FLOAT,
    e_p_d FLOAT,
    p_c_d FLOAT,
	timer INT,
	last_timestamp FLOAT,
	initial_config LONGTEXT
);
CREATE TABLE real_time_traders (
	coin1 TINYTEXT,
	coin2 TINYTEXT,
	p_s_u FLOAT,
    e_p_u FLOAT,
    p_c_u FLOAT,
    p_s_d FLOAT,
    e_p_d FLOAT,
    p_c_d FLOAT,
	timer INT,
	last_timestamp FLOAT,
	initial_config LONGTEXT
);
CREATE TABLE strategies (
    name TINYTEXT,
	init_timestamp DECIMAL(65,6),
	coin1 TINYTEXT,
	coin2 TINYTEXT,
	timer INT,
	stop_loss FLOAT,
	trade_type CHAR(5),
	trade_timestamp DECIMAL(65,6),
	trade_prev_timestamp DECIMAL(65,6),
	trade_price FLOAT,
	trade_prev_price FLOAT,
	aprox_s FLOAT,
	aprox_r FLOAT,
	last_timestamp DECIMAL(65,6),
	pl FLOAT,
	leverage_s FLOAT,
	leverage_l FLOAT,
	l_s_no FLOAT,
	l_l_no FLOAT,
	l_s_ok FLOAT,
	l_l_ok FLOAT,
	zoom_s FLOAT,
	zoom_l FLOAT,
	far_price FLOAT,
	initial_config LONGTEXT,
	ready_to_use TINYINT,
	comp_initial_config LONGTEXT,
	comp_last_timestamp LONGTEXT,
	comp_prev_pl FLOAT,
	comp_pl FLOAT,
	prev_pl FLOAT,
	pl_c INT,
	derivatives LONGTEXT
);
CREATE TABLE real_time_strategies (
    name TINYTEXT,
	init_timestamp DECIMAL(65,6),
	coin1 TINYTEXT,
	coin2 TINYTEXT,
	timer INT,
	stop_loss FLOAT,
	trade_type CHAR(5),
	trade_timestamp DECIMAL(65,6),
	trade_prev_timestamp DECIMAL(65,6),
	trade_price FLOAT,
	trade_prev_price FLOAT,
	aprox_s FLOAT,
	aprox_r FLOAT,
	last_timestamp DECIMAL(65,6),
	pl FLOAT,
	leverage_s FLOAT,
	leverage_l FLOAT,
	l_s_no FLOAT,
	l_l_no FLOAT,
	l_s_ok FLOAT,
	l_l_ok FLOAT,
	zoom_s FLOAT,
	zoom_l FLOAT,
	far_price FLOAT,
	initial_config LONGTEXT,
	prev_pl FLOAT,
	pl_c INT,
	derivatives LONGTEXT
);
