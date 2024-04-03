import uuid

import pandas as pd
import pyodbc
import os
import ldap3
import logging
import json

from django.conf import settings
from ldap3.core.exceptions import LDAPException
from ldap3 import Server, Connection
from datetime import datetime

from app.models import Societe

today = datetime.today().strftime('%d-%m-%Y')

columns0 = ["FAMILLE", "INTITULE"]


def check_base(server, name, value, username, password):
    conn = None
    try:
        value_input = f"Driver={{ODBC Driver 17 for SQL Server}};Server={server};Database={value};UID={username};" \
                      f"PWD={password}"
        conn = pyodbc.connect(value_input)
        # conn.close()
        # print(f"Connected in {name} in {value_input}")
    except pyodbc.Error as e:
        # Si une erreur se produit lors de la connexion, ajoutez le serveur à la liste des bases sans accès
        print("===============================")
        print(f"Erreur de Connexion pour {name} ")
        print("===============================")
        write_log(f"Erreur de connexion : {str(e)}")
    except Exception as e:
        write_log(f"Erreur Exception : {str(e)}")
    return conn


def extract_from_path(path):
    segments = path.lstrip('/').split('/')

    if len(segments) >= 3:
        base = segments[0]
        query = segments[1]
        table = segments[2]

        return base, query, table
    else:
        return None


def get_sql_in_json(chemin_fichier):
    try:
        with open(chemin_fichier, 'r') as fichier:
            contenu_json = json.load(fichier)
            return contenu_json
    except FileNotFoundError:
        print(f"Le fichier {chemin_fichier} n'a pas été trouvé.")
    except json.JSONDecodeError as e:
        print(f"Erreur lors de la lecture du fichier JSON : {e}")
    except Exception as e:
        print(f"Une erreur s'est produite : {e}")


def get_sql(path):
    base, query, value = extract_from_path(path)

    file = os.path.join(settings.BASE_DIR, 'sql.json')
    contenu = get_sql_in_json(file)
    valeur = None
    if contenu is not None:
        try:
            valeur = contenu[base][query][value]
        except KeyError as e:
            print(f"La clé {e} n'a pas été trouvée dans le fichier JSON.")
        except TypeError as e:
            print(f"Erreur de type : {e}")

    return valeur


def get_all_filter(conn, societe, sql):
    code_choices = []
    try:
        cursor = conn.cursor()
        sql = str(sql).replace('<value>', societe.value)
        # print("===============================")
        # print(f"SQL : {sql} ")
        # print("===============================")
        cursor.execute(sql)

        # Récupération des résultats
        rows = cursor.fetchall()
        if rows:
            rows = [tuple(row) for row in rows]
            if all(isinstance(row, tuple) for row in rows):
                df = pd.DataFrame(rows, columns=['CODE', 'SOCIETE'])
                grouped_options = df.groupby('SOCIETE')['CODE'].apply(lambda x: list(zip(x, x))).reset_index()
                for _, group in grouped_options.iterrows():
                    code_choices.append((group['SOCIETE'], group['CODE']))
        cursor.close()
        conn.close()

    except pyodbc.Error as e:
        print("Erreur lors de la connexion à la base de données:", str(e))
        # write_log(str(e))
    except Exception as e:
        write_log(f"{str(e)}")
        pass
    return code_choices


# Définition de la fonction pour rechercher les attributs LDAP d'un utilisateur
def ldap_search_attributes(conn, username):
    # Spécification de la base de recherche LDAP et du filtre de recherche
    search_base = settings.DN_LDAP
    # search_filter = f"(&(sAMAccountName={username}))"
    search_filter = f"(&(sAMAccountName={username}))"
    try:
        # Recherche des attributs spécifiés pour l'utilisateur donné
        conn.search(search_base, search_filter, attributes=['mail', 'sn', 'givenName'])

        # Vérification si des résultats ont été trouvés
        if len(conn.entries) > 0:
            entry = conn.entries[0]
            # write_log(f"Utilisateur Trouver : {entry}", level=logging.INFO)

            # Extraction des attributs si présents dans l'entrée LDAP
            email = entry.mail[0] if 'mail' in entry else None
            lastname = entry.sn[0] if 'sn' in entry else None
            firstname = entry.givenname[0] if 'givenName' in entry else None

            # Retourne un dictionnaire avec les attributs trouvés
            return {
                'email': email,
                'lastname': lastname,
                'firstname': firstname
            }
    except LDAPException as e:
        # Utilisation d'un système de journalisation pour enregistrer les erreurs
        write_log(f"Erreur de recherche LDAP : {str(e)}")
        return False


# Définition de la fonction pour la connexion LDAP
def ldap_login_connection(username, password):
    # Construction du DN de l'utilisateur
    user = f"SMTP-GROUP\\{username}".strip()
    # write_log(f"DN: {user}", level=logging.INFO)
    try:
        # Création de l'objet de serveur LDAP
        server = Server(settings.SERVER_LDAP, get_info=ldap3.ALL)

        # Connexion au serveur LDAP avec l'utilisateur et le mot de passe fournis
        with Connection(
                server=server,
                user=user,
                password=password,
                authentication=ldap3.SIMPLE,
                client_strategy=ldap3.SYNC) as conn:

            # Vérification de la liaison réussie (authentification)
            if not conn.bind():
                write_log("Bind Error !", level=logging.ERROR)
                return False
            write_log("Bind Successfully !", level=logging.INFO)
            # Appel de la fonction de recherche d'attributs LDAP pour l'utilisateur
            return ldap_search_attributes(conn, username)

    except LDAPException as e:
        # Utilisation d'un système de journalisation pour enregistrer les erreurs
        write_log(f"Erreur de connexion LDAP : {str(e)}")
        return False


def get_data(sql, conn, columns):
    df = None
    if sql is not None:
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()

                if rows:
                    rows = [tuple(row) for row in rows]
                    if all(isinstance(row, tuple) for row in rows):
                        df = pd.DataFrame(rows, columns=columns)
        except Exception as e:
            write_log(f"Erreur execute_sql {sql} : {str(e)}")
    return df


def chercher(df, value):
    result = 0
    if df is not None:  # Ajoutez cette vérification
        for index, row in df.iterrows():
            if row['FAMILLE'] == value:
                return row['VALUE']

    return result


def find_value_in_wheres(wheres, name, category_to_find):
    found_value = ''
    for item in wheres:
        if item["NAME"] == name:
            for value in item["VALUES"]:
                if value["CATEGORY"] == category_to_find:
                    found_value = value.get('VALUES')
                    break
            break
    return found_value


def execute(data, categories, value, intitule, debut, fin, conn, filtre):
    gest = [value, intitule]
    try:
        if categories in data:
            req = data[categories]
            # Accéder aux requêtes pour la catégorie spécifiée
            for key, sql in req.items():
                if sql is not None:
                    if sql == 1:
                        stock_int = float(gest[3]) + float(gest[4]) + float(gest[5]) + float(gest[6]) + float(
                            gest[7]) + float(gest[8]) + float(gest[9])
                    elif sql == 2:
                        stock_int = float(gest[11]) + float(gest[12]) + float(gest[13]) + float(gest[14]) + float(
                            gest[15]) + float(gest[16])
                    elif sql == 3:
                        stock_int = float(gest[2]) + float(gest[10]) + float(gest[17])
                    else:
                        # filtre = [int(value) for value in filtre]
                        # print("Filtre : ", filtre)
                        query = sql.replace('{debut}', debut).replace('{fin}', fin).replace('{in}', str(filtre))
                        df = get_data(query, conn=conn)
                        stock_int = chercher(df, value)
                    gest.append(stock_int)
                else:
                    gest.append(0)
    except Exception as e:
        write_log(str(e))
    return gest


def get_choix(conn):
    dl_num = "SELECT DE_NO, DE_INTITULE FROM F_DEPOT"

    resul = get_data(sql=dl_num, conn=conn, columns=['DE_NO', 'DE_INTITULE'])
    choices = []
    if resul is not None:
        choices = resul.to_dict(orient='records')
        # choices = [(item['DE_NO'], item['DE_INTITULE']) for item in resul]

    return choices


def get_all_famille(categories, debut, fin, conn, filtre):
    datas = []
    filter = filtre[0]
    try:
        with open('datas.json', 'r') as file:
            json_file = json.load(file)
            sql = json_file['FAMILLE']
            sql = sql.replace('{in}', str(filter))

            familles = get_data(sql=sql, conn=conn, columns=columns0)
            if familles is not None:
                for index, row in familles.iterrows():
                    value = row['FAMILLE']
                    intitule = row['INTITULE']
                    # print(intitule)
                    datas.append(
                        execute(json_file, categories, value, intitule, debut, fin, conn=conn, filtre=filtre))
                # print(f"Datas : {datas}")
                return [True, datas]
    except Exception as e:
        write_log(str(e))
    return [False, datas]


def format_number(number):
    try:
        return '{:,.2f}'.format(float(number))
    except ValueError:
        return number  # Handle non-numeric values gracefully


def get_cell_data(index, column, debut, fin, conn, filtre=None):
    try:
        with open('datas.json', 'r') as file:
            json_file = json.load(file)
            sql = json_file['COLUMNS'][f'{column}']
            query = str(sql).replace('{debut}', debut).replace('{fin}', fin). \
                replace('{val}', index).replace('{in}', str(filtre))

            famille_df = get_data(sql=query, conn=conn,
                                  columns=['do_piece', 'do_date', 'ar_ref', 'dl_design', 'dl_qte', 'dl_prixRU',
                                           'dl_prixTotal'], )

            # print(famille_df)

            # Check if famille_df is not None before converting to dict
            if famille_df is not None:
                # Convert DataFrame to list of dictionaries
                famille_list = famille_df.to_dict(orient='records')

                # Format the 'do_date' field in the list
                for entry in famille_list:
                    if 'do_date' in entry:
                        entry['do_date'] = entry['do_date'].strftime('%Y-%m-%d')

                    # Format numeric fields
                    for field in ['dl_qte', 'dl_prixRU', 'dl_prixTotal']:
                        if field in entry:
                            entry[field] = format_number(entry[field])

                return famille_list
            else:
                return []
    except Exception as e:
        write_log(f"Erreur select cell data: {str(e)}")
        return []


def write_log(logs, level=None):
    log_file = os.path.join('logs', f'{today}.log')

    logging.basicConfig(filename=log_file, encoding='utf-8', level=level,
                        format='%(asctime)s - %(name)s - %(levelname)s : %(message)s')

    logger = logging.getLogger(__name__)

    if level == logging.ERROR:
        logger.error(logs)
    elif level == logging.INFO:
        logger.info(logs)
    elif level == logging.CRITICAL:
        logger.critical(logs)
    else:
        logger.exception(logs)


def are_valid_uuids(values):
    if isinstance(values, list):
        uuids = []

        for value in values:
            try:
                uid = uuid.UUID(value)
                uuids.append(uid)
            except ValueError:
                return None

        return uuids
    else:
        try:
            uid = uuid.UUID(values)
            return uid
        except ValueError:
            return None
