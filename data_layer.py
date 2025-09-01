import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import urllib
import db_utils


class DataLayer:
    """
    Gestiona la conexión a la base de datos y la extracción de datos.
    Utiliza SQLAlchemy para ser compatible con múltiples motores de BD.
    """
    def __init__(self):
        self.engine = None
        self.connection_string = None
        self.connection_details = {}

    def connect(self, connection_details):
        """
        Establece la conexión usando un diccionario de detalles.
        Este es ahora el ÚNICO método para conectar.
        """
        self.connection_details = connection_details
        db_type = connection_details.get('db_type')
        
        try:
            if db_type == "SQL Server":
                driver = db_utils.get_latest_sql_driver().replace(' ', '+')
                server = connection_details.get('host')
                database = connection_details.get('database')
                
                if connection_details.get('use_win_auth'):
                    params = urllib.parse.quote_plus(
                        f"DRIVER={{{driver}}};"
                        f"SERVER={server};"
                        f"DATABASE={database};"
                        f"Trusted_Connection=yes;"
                        f"TrustServerCertificate=yes;"
                    )
                else:
                    user = connection_details.get('user')
                    password = connection_details.get('password')
                    params = urllib.parse.quote_plus(
                        f"DRIVER={{{driver}}};"
                        f"SERVER={server};"
                        f"DATABASE={database};"
                        f"UID={user};"
                        f"PWD={password};"
                        f"TrustServerCertificate=yes;"
                    )
                self.connection_string = f"mssql+pyodbc:///?odbc_connect={params}"

            elif db_type == "MySQL":
                user = connection_details.get('user')
                password = connection_details.get('password')
                host = connection_details.get('host')
                port = connection_details.get('port') or '3306'
                database = connection_details.get('database')
                self.connection_string = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"

            elif db_type == "SQLite":
                db_path = connection_details.get('db_path') # Asumimos que se pasará esta clave
                self.connection_string = f"sqlite:///{db_path}"

            else:
                return f"Error: Tipo de BD '{db_type}' no soportado."

            # Crear el motor y probar la conexión
            self.engine = create_engine(self.connection_string)
            with self.engine.connect():
                pass # Prueba de conexión exitosa
            return f"Conexión a {db_type} exitosa."

        except SQLAlchemyError as e:
            self.engine = None
            return f"Error de conexión SQLAlchemy: {e}"
        except Exception as e:
            self.engine = None
            return f"Error inesperado al conectar: {e}"

    def get_data(self, query):
        """
        Ejecuta una consulta SQL y devuelve los resultados en un DataFrame de Pandas.
        (Esta función no necesita cambios)
        """
        if not self.engine:
            print("Error: No hay conexión activa a la base de datos.")
            return None
        
        try:
            with self.engine.connect() as connection:
                df = pd.read_sql_query(sql=text(query), con=connection)
                return df
        except SQLAlchemyError as e:
            print(f"Error al ejecutar la consulta: {e}")
            return None
        except Exception as e:
            print(f"Un error inesperado ocurrió al obtener datos: {e}")
            return None

    def is_connected(self):
        """Verifica si el motor de la base de datos está inicializado."""
        return self.engine is not None