# --- Contenido de: db_utils.py ---

import json
import os
import pyodbc
from sqlalchemy.exc import SQLAlchemyError
import mysql.connector # Necesitaremos esta librería
import psycopg2 # Y esta también, por si en el futuro quieres añadir PostgreSQL

# Nombre del archivo para guardar la agenda de servidores
SERVERS_FILE = "analyzer_servers.json"

def load_servers():
    """Carga la agenda de servidores desde el archivo JSON."""
    if not os.path.exists(SERVERS_FILE):
        return {}
    try:
        with open(SERVERS_FILE, "r", encoding='utf-8') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return {}

def save_servers(servers_dict):
    """Guarda la agenda de servidores en el archivo JSON."""
    try:
        with open(SERVERS_FILE, "w", encoding='utf-8') as f:
            json.dump(servers_dict, f, indent=4)
    except IOError as e:
        print(f"Error al guardar la agenda de servidores: {e}")

def get_latest_sql_driver():
    """Busca el driver ODBC de SQL Server más reciente disponible."""
    try:
        drivers = pyodbc.drivers()
        if "ODBC Driver 18 for SQL Server" in drivers:
            return "ODBC Driver 18 for SQL Server"
        if "ODBC Driver 17 for SQL Server" in drivers:
            return "ODBC Driver 17 for SQL Server"
        sql_server_drivers = [d for d in drivers if "SQL Server" in d and "SQL Server Native Client 11.0" not in d]
        if sql_server_drivers:
            return sorted(sql_server_drivers, reverse=True)[0]
    except Exception as e:
        print("Error obteniendo drivers:", e)
    return "ODBC Driver 18 for SQL Server"

def get_server_connection(db_type, server, port, user, password, use_win_auth):
    """
    Establece una conexión a un servidor de base de datos sin especificar
    una base de datos inicial (necesario para listar las bases disponibles).
    """
    conn = None
    if db_type == "MySQL":
        conn = mysql.connector.connect(
            host=server, port=port,
            user=user, password=password,
            connection_timeout=10
        )
    elif db_type == "SQL Server":
        if port and port != "1433":
            server = f"{server},{port}"

        driver = get_latest_sql_driver()
        conn_str = f"DRIVER={{{driver}}};SERVER={server};DATABASE=master;TrustServerCertificate=yes;"

        if use_win_auth:
            conn_str += "Trusted_Connection=yes;"
        else:
            conn_str += f"UID={user};PWD={password};"
        
        conn = pyodbc.connect(conn_str, timeout=10)

    if conn is None:
        raise ConnectionError(f"No se pudo establecer conexión con el servidor de tipo {db_type}.")

    return conn

def list_databases(connection, db_type):
    """Devuelve una lista de todas las bases de datos en el servidor conectado."""
    cursor = connection.cursor()
    databases = []
    
    if db_type == "MySQL":
        cursor.execute("SHOW DATABASES;")
        system_dbs = ['information_schema', 'mysql', 'performance_schema', 'sys']
        databases = [row[0] for row in cursor.fetchall() if row[0] not in system_dbs]
    elif db_type == "SQL Server":
        cursor.execute("SELECT name FROM sys.databases WHERE database_id > 4 ORDER BY name;")
        databases = [row[0] for row in cursor.fetchall()]

    cursor.close()
    return sorted(databases)

def save_last_server(server_details):
    """Guarda los detalles del último servidor usado en un archivo de configuración."""
    try:
        # Usamos un nombre de archivo diferente para no mezclarlo con la agenda
        with open("analyzer_last_server.json", "w", encoding='utf-8') as f:
            json.dump(server_details, f, indent=4)
    except IOError as e:
        print(f"Error al guardar la última configuración del servidor: {e}")

def load_last_server():
    """Carga los detalles del último servidor usado. Devuelve None si no existe."""
    if not os.path.exists("analyzer_last_server.json"):
        return None
    try:
        with open("analyzer_last_server.json", "r", encoding='utf-8') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return None