import struct

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql
import json
import re
from configparser import ConfigParser
import os
import logging.config

# logging.config.fileConfig('logging.ini')
logger = logging.getLogger(__name__)


def get_db_connection():
    config = os.environ.get('DB_CONFIG', 'database.ini')

    # https://www.postgresqltutorial.com/postgresql-python/connect/
    def parse_database_info(filename, section='postgresql'):
        # create a parser
        parser = ConfigParser()
        # read config file
        parser.read(filename)

        # get section, default to postgresql
        db = {}
        if parser.has_section(section):
            params = parser.items(section)
            for param in params:
                db[param[0]] = param[1]
        else:
            raise Exception('Section {0} not found in the {1} file'.format(section, filename))

        return db

    # read connection information
    db_info = parse_database_info(config)
    # logger.debug('Getting DB connection...')
    conn = psycopg2.connect(**db_info)
    return conn


def create_app():
    """
    Create the flask app.

    :return: flask app
    """
    app = Flask(__name__, static_url_path="",
                static_folder='../static', template_folder='../templates')

    # Load flask config, TODO: app.env is deprecated
    if app.env == 'development':
        app.config.from_object('xi_web_api.config.DevelopmentConfig')
    else:
        app.config.from_object('xi_web_api.config.ProductionConfig')
        try:
            app.config.from_envvar('XI2XIVIEWLOADER_SETTINGS')
        except (FileNotFoundError, RuntimeError):
            ...

    # add CORS header
    CORS(app)

    psycopg2.extras.register_uuid()

    from xi_web_api.pdbdev import bp as pdb_dev_bp
    app.register_blueprint(pdb_dev_bp)

    from xi2annotator import bp as xi2_bp
    app.register_blueprint(xi2_bp)

    @app.route('/', methods=['GET'])
    def index():
        conn = None
        ds_rows = []
        error = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            query = """SELECT project_id, identification_file_name FROM upload;"""
            logger.debug(query)
            cur.execute(query)
            ds_rows = cur.fetchall()
            logger.info("finished")
            cur.close()
        except (Exception, psycopg2.DatabaseError) as e:
            print(e)
            error = e
        finally:
            if conn is not None:
                conn.close()
                logger.debug('Database connection closed.')
            if error is not None:
                raise error
        return render_template("datasets.html", datasets=ds_rows)

    @app.route('/get_data', methods=['GET'])
    def get_data():
        """
        Get the data for the network visualisation.
        URLs have following structure:
        https: // www.ebi.ac.uk / pride / archive / xiview / network.html?project=PXD020453&file=Cullin_SDA_1pcFDR.mzid
        Users may provide only projects, meaning we need to have an aggregated  view.
        https: // www.ebi.ac.uk / pride / archive / xiview / network.html?project=PXD020453

        :return: json with the data
        """
        pxid = request.args.get('project')
        if pxid is None:
            return jsonify({"error": "No project id provided"}), 400
        elif not re.match(r'^[a-zA-Z0-9_]+$', pxid):
            return jsonify({"error": "Invalid project id"}), 400

        file = request.args.get('file')

        conn = None
        uuids = None
        try:
            # connect to the PostgreSQL server
            # logger.info('Connecting to the PostgreSQL database...')
            conn = get_db_connection()
            cur = conn.cursor()
            if file:
                filename_clean = re.sub(r'[^0-9a-zA-Z-]+', '-', file)
                query = """SELECT id FROM upload 
                        WHERE project_id = %s AND identification_file_name_clean = %s 
                        ORDER BY upload_time DESC LIMIT 1;"""
                # logger.debug(sql)
                cur.execute(query, [pxid, filename_clean])

                uuids = [cur.fetchone()[0]]
                if uuids is None:
                    return jsonify({"error": "No data found"}), 404
                # logger.info("finished")
                # close the communication with the PostgreSQL
                cur.close()
            else:
                query = """SELECT u.id
                            FROM upload u
                            where u.upload_time = 
                                (select max(upload_time) from upload 
                                where project_id = u.project_id 
                                and identification_file_name = u.identification_file_name )
                            and u.project_id = %s;"""
                # logger.debug(sql)
                cur.execute(query, [pxid])
                uuids = cur.fetchall()
                if uuids is None:
                    return jsonify({"error": "No data found"}), 404
                # logger.info("finished")
                # close the communication with the PostgreSQL
                cur.close()

        except (Exception, psycopg2.DatabaseError) as e:
            logger.error(e)
        finally:
            if conn is not None:
                conn.close()
                logger.debug('Database connection closed.')

        try:
            data_object = get_data_object(uuids)
        except psycopg2.DatabaseError as e:
            logger.error(e)
            return jsonify({"error": "Database error"}), 500

        return json.dumps(data_object)  # more efficient than jsonify as it doesn't pretty print

    @app.route('/get_peaklist', methods=['GET'])
    def get_peaklist():
        conn = None
        data = {}
        error = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            query = "SELECT intensity, mz FROM spectrum WHERE id = %s AND spectra_data_ref = %s AND upload_id = %s"
            cur.execute(query, [request.args.get('id'), request.args.get('sd_ref'), request.args.get('upload_id')])
            resultset = cur.fetchall()[0]
            data["intensity"] = struct.unpack('%sd' % (len(resultset[0]) // 8), resultset[0])
            data["mz"] = struct.unpack('%sd' % (len(resultset[1]) // 8), resultset[1])
            cur.close()
        except (Exception, psycopg2.DatabaseError) as e:
            # logger.error(error)
            error = e
        finally:
            if conn is not None:
                conn.close()
                # logger.debug('Database connection closed.')
            if error is not None:
                raise error
            return jsonify(data)

    @app.route('/network.html', methods=['GET'])
    def network():
        return app.send_static_file('network.html')

    return app


def get_data_object(ids):
    """ Connect to the PostgreSQL database server """
    conn = None
    data = {}
    error = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        data["metadata"] = get_results_metadata(cur, ids)
        data["matches"] = get_matches(cur, ids)
        data["peptides"] = get_peptides(cur, data["matches"])
        data["proteins"] = get_proteins(cur, data["peptides"])
        logger.info("finished")
        cur.close()
    except (Exception, psycopg2.DatabaseError) as e:
        error = e
    finally:
        if conn is not None:
            conn.close()
            logger.debug('Database connection closed.')
        if error is not None:
            raise error
        return data

def get_results_metadata(cur, ids):
    """ Get the metadata for the results """
    metadata = {}



    # get AnalysisCollection(s) for each id
    query = """SELECT ac.upload_id, 
                ac.spectrum_identification_list_ref, 
                ac.spectrum_identification_protocol_ref,
                ac.spectra_data_ref
            FROM analysiscollection ac
            WHERE ac.upload_id = ANY(%s);"""
    cur.execute(query, [ids])
    metadata["analysis_collections"] = cur.fetchall()

    # get SpectrumIdentificationProtocol(s) for each id
    query = """SELECT sip.id AS id,
                sip.upload_id,
                sip.frag_tol,
                sip.search_params,
                sip.analysis_software,
                sip.threshold
            FROM spectrumidentificationprotocol sip
            WHERE sip.upload_id = ANY(%s);"""
    cur.execute(query, [ids])
    metadata["spectrum_identification_protocols"] = cur.fetchall()

    return metadata


def get_matches(cur, ids):
    query = """SELECT si.id AS id, si.pep1_id AS pi1, si.pep2_id AS pi2,
                si.scores AS sc,
                cast (si.upload_id as text) AS si,
                si.calc_mz AS c_mz,
                si.charge_state AS pc_c,
                si.exp_mz AS pc_mz,
                si.spectrum_id AS sp,
                si.spectra_data_ref AS sd_ref,
                si.pass_threshold AS pass,
                si.rank AS r,
                si.sil_id AS sil                
            FROM spectrumidentification si 
            INNER JOIN modifiedpeptide mp1 ON si.pep1_id = mp1.id AND si.upload_id = mp1.upload_id 
            INNER JOIN modifiedpeptide mp2 ON si.pep2_id = mp2.id AND si.upload_id = mp2.upload_id
            WHERE si.upload_id = ANY(%s) 
            AND si.pass_threshold = TRUE 
            AND mp1.link_site1 > 0
            AND mp2.link_site1 > 0;"""
    # bit weird above works when link_site1 is a text column
    cur.execute(query, [ids])
    return cur.fetchall()


def get_peptides(cur, match_rows):
    search_peptide_ids = {}
    for match_row in match_rows:
        if match_row['si'] in search_peptide_ids:
            peptide_ids = search_peptide_ids[match_row['si']]
        else:
            peptide_ids = set()
            search_peptide_ids[match_row['si']] = peptide_ids
        peptide_ids.add(match_row['pi1'])
        if match_row['pi2'] is not None:
            peptide_ids.add(match_row['pi2'])

    subclauses = []
    for k, v in search_peptide_ids.items():
        pep_id_literals = []
        for pep_id in v:
            pep_id_literals.append(sql.Literal(pep_id))
        joined_pep_ids = sql.SQL(',').join(pep_id_literals)
        subclause = sql.SQL("(mp.upload_id = {} AND id IN ({}))").format(
            sql.Literal(k),
            joined_pep_ids
        )
        subclauses.append(subclause)
    peptide_clause = sql.SQL(" OR ").join(subclauses)

    query = sql.SQL("""SELECT mp.id, cast(mp.upload_id as text) AS u_id,
                mp.base_sequence AS base_seq,
                array_agg(pp.dbsequence_ref) AS prt,
                array_agg(pp.pep_start) AS pos,
                array_agg(pp.is_decoy) AS is_decoy,
                mp.link_site1 AS "linkSite",
                mp.mod_accessions as mod_accs,
                mp.mod_positions as mod_pos,
                mp.mod_monoiso_mass_deltas as mod_masses,
                mp.crosslinker_modmass as cl_modmass                     
                    FROM modifiedpeptide AS mp
                    JOIN peptideevidence AS pp
                    ON mp.id = pp.peptide_ref AND mp.upload_id = pp.upload_id
                WHERE {}
                GROUP BY mp.id, mp.upload_id, mp.base_sequence;""").format(
        peptide_clause
    )
    logger.debug(query.as_string(cur))
    cur.execute(query)
    return cur.fetchall()


def get_proteins(cur, peptide_rows):
    search_protein_ids = {}
    for peptide_row in peptide_rows:
        if peptide_row['u_id'] in search_protein_ids:
            protein_ids = search_protein_ids[peptide_row['u_id']]
        else:
            protein_ids = set()
            search_protein_ids[peptide_row['u_id']] = protein_ids
        for prot in peptide_row['prt']:
            protein_ids.add(prot)

    subclauses = []
    for k, v in search_protein_ids.items():
        literals = []
        for prot_id in v:
            literals.append(sql.Literal(prot_id))
        joined_literals = sql.SQL(",").join(literals)
        subclause = sql.SQL("(upload_id = {} AND id IN ({}))").format(
            sql.Literal(k),
            joined_literals
        )
        subclauses.append(subclause)

    protein_clause = sql.SQL(" OR ").join(subclauses)
    query = sql.SQL("""SELECT id, name, accession, sequence,
                     cast(upload_id as text) AS search_id, description FROM dbsequence WHERE ({});""").format(
        protein_clause
    )
    logger.debug(query.as_string(cur))
    cur.execute(query)
    return cur.fetchall()
