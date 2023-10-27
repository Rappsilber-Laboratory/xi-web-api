import struct

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import psycopg2  # todo - use sqlalchemy instead? LK: There's also flask_sqlalchemy
import json
import re
from configparser import ConfigParser
import os
import logging.config


logging.config.fileConfig('logging.ini')
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
    print('Connecting to the PostgreSQL database...')
    conn = psycopg2.connect(**db_info)
    return conn


def create_app():
    """
    Create the flask app.

    :return: flask app
    """
    app = Flask(__name__, static_url_path="",
                static_folder='../static', template_folder='../templates')

    # Load flask config
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

    from xi_web_api.pdbdev import bp as pdb_dev_bp
    app.register_blueprint(pdb_dev_bp)

    from xi2annotator import bp as xi2_bp
    app.register_blueprint(xi2_bp)


    @app.route('/', methods=['GET'])
    def index():
        datasets = get_datasets()
        return render_template("datasets.html", datasets=datasets)

    def get_datasets():
        """Get all datasets from the database."""
        conn = None
        ds_rows = []
        error = None
        try:
            # connect to the PostgreSQL server
            conn = get_db_connection()

            # create a cursor
            cur = conn.cursor()

            sql = """SELECT project_id, identification_file_name FROM upload;"""
            logger.debug(sql)
            cur.execute(sql)
            ds_rows = cur.fetchall()
            logger.info("finished")
            # close the communication with the PostgreSQL
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
            return ds_rows

    @app.route('/dataset', methods=['GET'])
    def dataset():
        pxid = request.args.get('pxid')
        dataset = get_dataset(pxid)
        return render_template("dataset.html", datasets=dataset)

    def get_dataset(pxid):
        """ Connect to the PostgreSQL database server """
        conn = None
        mzid_rows = []
        error = None
        try:
            # connect to the PostgreSQL server
            logger.info('Connecting to the PostgreSQL database...')
            conn = get_db_connection()

            # create a cursor
            cur = conn.cursor()

            sql = """SELECT identification_file_name, project_id, identification_file_name_clean FROM upload WHERE project_id = %s ORDER BY upload_time DESC LIMIT 1;"""
            logger.debug(sql)
            cur.execute(sql, [pxid])
            mzid_rows = cur.fetchall()
            logger.debug("finished")
            # close the communication with the PostgreSQL
            cur.close()
        except (Exception, psycopg2.DatabaseError) as e:
            logger.error(e)
            error = e
        finally:
            if conn is not None:
                conn.close()
                print('Database connection closed.')
            if error is not None:
                raise error
            return mzid_rows

    @app.route('/visualisations', methods=['GET'])
    def visualisations():
        pxid = request.args.get('pxid')
        dataset = get_dataset(pxid)
        datafile = {}
        if len(dataset) == 0:
            return json.dumps({})
        record = dataset[0] #  todo - return an array, not a single record - not changing now coz might break pride end
        datafile["filename"] = record[2]
        datafile["visualisation"] = "cross-linking"
        datafile["link"] = request.base_url[:request.base_url.rfind('/')] + "/network.html?project=" + record[1] + "&file=" + record[2]
        return json.dumps(datafile)

    @app.route('/get_data', methods=['GET'])
    def get_data():
        """
        Get the data for the network visualisation.
        URL for the future should have the following URL:
        https: // www.ebi.ac.uk / pride / archive / xiview / network.html?project=PXD020453&file=Cullin_SDA_1pcFDR.mzid
        Users may provide only projects, meaning we need to have an aggregated  view.
        https: // www.ebi.ac.uk / pride / archive / xiview / network.html?project=PXD020453

        :return:
        """
        pxid = request.args.get('project')
        if pxid is None:
            return jsonify({"error": "No project id provided"}), 400
        elif not re.match(r'^[a-zA-Z0-9]+$', pxid):
            return jsonify({"error": "Invalid id(s)"}), 400

        file = request.args.get('file')
        if file is None:
            return jsonify({"error": "No file name provided - aggregating for project not supported yet"}), 400
        filename_clean = re.sub(r'[^0-9a-zA-Z-]+', '-', file)

        conn = None
        uuid = None
        error = None
        try:
            # connect to the PostgreSQL server
            logger.info('Connecting to the PostgreSQL database...')
            conn = get_db_connection()

            # create a cursor
            cur = conn.cursor()

            sql = """SELECT id FROM upload WHERE project_id = %s AND identification_file_name_clean = %s ORDER BY upload_time DESC LIMIT 1;"""
            logger.debug(sql)
            cur.execute(sql, [pxid, filename_clean])
            mzid_id = cur.fetchone()
            if mzid_id is None:
                return jsonify({"error": "No data found"}), 404
            logger.info("finished")
            # close the communication with the PostgreSQL
            cur.close()
            uuid = mzid_id[0]
        except (Exception, psycopg2.DatabaseError) as e:
            logger.error(e)
            error = e
        finally:
            if conn is not None:
                conn.close()
                logger.debug('Database connection closed.')
            if error is not None:
                raise error

        try:
            data_object = get_data_object(uuid)
        except psycopg2.DatabaseError:
            return jsonify({"error": "Database error"}), 500
        # think this will be more efficient as it doesn't pretty print
        return json.dumps(data_object)
        # return jsonify(data_object)  # this is more readable for debugging

    @app.route('/get_peaklist', methods=['GET'])
    def get_peaklist():
        id = request.args.get('id')
        sd_ref = request.args.get('sd_ref')
        upload_id = request.args.get('upload_id')
        return jsonify(get_peaklist_object(id, sd_ref, upload_id))

    # following doesn't look very secure
    # @app.route('/save_layout', methods=['POST'])
    # def save_layout():
    #     uuid = request.form['uuid']
    #     layout = request.form['layout']
    #     description = request.form['name']
    #
    #     try:
    #         # connect to the PostgreSQL server
    #         print('Connecting to the PostgreSQL database...')
    #         conn = psycopg2.connect(**db_info)
    #
    #         # create a cursor
    #         cur = conn.cursor()
    #
    #         sql = "INSERT INTO layout (resultset_id, layout, description) VALUES (%s, %s, %s)"
    #
    #         cur.execute(sql, [uuid, layout, description])
    #         conn.commit()
    #
    #         print("finished")
    #         # close the communication with the PostgreSQL
    #         cur.close()
    #         return "Layout saved!"
    #     except (Exception, psycopg2.DatabaseError) as error:
    #         print(error)
    #         return "Database error:\n" + str(error)
    #     finally:
    #         if conn is not None:
    #             conn.close()
    #             print('Database connection closed.')
    #
    # @app.route('/load_layout', methods=['POST'])
    # def load_layout():
    #     # actually returns all different layouts available
    #     uuid = request.form['uuid']
    #
    #     try:
    #         # connect to the PostgreSQL server
    #         print('Connecting to the PostgreSQL database...')
    #         conn = psycopg2.connect(**db_info)
    #
    #         # create a cursor
    #         cur = conn.cursor()
    #
    #         sql = """SELECT t1.layout AS layout, t1.description AS name FROM layout AS t1
    #               WHERE t1.resultset_id = %s AND t1.time_saved IN
    #               (SELECT max(t1.time_saved) FROM layout AS t1
    #               WHERE t1.resultset_id = %s GROUP BY t1.description);"""
    #         # sql = """SELECT t1.description, t1.layout FROM layout AS t1
    #         #     WHERE t1.resultset_id = %s ORDER BY t1.time_saved desc LIMIT 1"""
    #         cur.execute(sql, [uuid, uuid])
    #         layouts = cur.fetchall()
    #         data = {}
    #         # xinet_layout = {
    #         #     "name": data[0],
    #         #     "layout": data[1]
    #         # }
    #         for layout in layouts:
    #             data[str(layout[1])] = layout[0]
    #
    #         print("finished")
    #         # close the communication with the PostgreSQL
    #         cur.close()
    #         return jsonify(data)
    #     except (Exception, psycopg2.DatabaseError) as error:
    #         print(error)
    #         return "Database error:\n" + str(error)
    #     finally:
    #         if conn is not None:
    #             conn.close()
    #             print('Database connection closed.')

    @app.route('/network.html', methods=['GET'])
    def network():
        return app.send_static_file('network.html')

    def get_data_object(uuid):
        """ Connect to the PostgreSQL database server """
        conn = None
        data = {}
        error = None
        try:
            # connect to the PostgreSQL server
            conn = get_db_connection()

            # create a cursor
            cur = conn.cursor()

            data["sid"] = uuid
            # data["resultset"], data["searches"] = get_resultset_search_metadata(cur, uuid)
            data["matches"], peptide_clause = get_matches(cur, uuid)
            # data["resultset"]["mainscore"])
            data["peptides"], protein_clause = get_peptides(cur, peptide_clause)
            data["proteins"] = get_proteins(cur, protein_clause)
            # data["xiNETLayout"] = get_layout(cur, uuid)

            logger.info("finished")
            # close the communication with the PostgreSQL
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

    def get_peaklist_object(spectrum_id, spectra_data_ref, upload_id):
        """ Connect to the PostgreSQL database server """
        conn = None
        data = {}
        error = None
        try:
            # connect to the PostgreSQL server
            conn = get_db_connection()

            # create a cursor
            cur = conn.cursor()

            sql = "SELECT intensity, mz FROM spectrum WHERE id = %s AND spectra_data_ref = %s AND upload_id = %s"

            cur.execute(sql, [spectrum_id, spectra_data_ref, upload_id])
            resultset = cur.fetchall()[0]
            data["intensity"] = struct.unpack('%sd' % (len(resultset[0]) // 8), resultset[0])
            data["mz"] = struct.unpack('%sd' % (len(resultset[1]) // 8), resultset[1])
            print("finished")
            # close the communication with the PostgreSQL
            cur.close()
        except (Exception, psycopg2.DatabaseError) as e:
            logger.error(error)
            error = e
        finally:
            if conn is not None:
                conn.close()
                logger.debug('Database connection closed.')
            if error is not None:
                raise error
            return data

    return app


def get_resultset_search_metadata(cur, uuid):
    sql = """
                SELECT rs.name, rs.note, rs.config, rs.main_score, rst.name,
                      s.id, s.name, s.config, s.note
                 FROM resultset AS rs
                  LEFT JOIN resultsettype AS rst ON (rs.rstype_id = rst.id)
                  LEFT JOIN ResultSearch AS result_search ON (rs.id = result_search.resultset_id)
                  LEFT JOIN Search AS s ON (result_search.search_id = s.id)
                WHERE rs.id = %s
                           """
    cur.execute(sql, [uuid])
    resultset_meta_cur = cur.fetchall()
    first_row = resultset_meta_cur[0]

    resultset_meta = {
        "name": first_row[0],
        "note": first_row[1],
        # "config": json.loads(first_row[2]),
        "config": first_row[2],
        "mainscore": first_row[3],
        "resultsettype": first_row[4]
    }
    searches = {}
    for search_row in resultset_meta_cur:
        search = {
            "id": search_row[5],
            "name": search_row[6],
            "config": json.loads(search_row[7]),
            # "note": search_row[8]
        }
        searches[search["id"]] = search
    return resultset_meta, searches


def get_matches(cur, uuid):
    # todo - the join to matchedspectrum for cleavable crosslinker - needs a GROUP BY match_id?'
    # sql = """SELECT m.id, m.pep1_id, m.pep2_id,
    #                 CASE WHEN rm.site1 IS NOT NULL THEN rm.site1 ELSE m.site1 END,
    #                 CASE WHEN rm.site2 IS NOT NULL THEN rm.site2 ELSE m.site2 END,
    #                 rm.scores[%s], m.crosslinker_id,
    #                 m.search_id, m.calc_mass, m.assumed_prec_charge, m.assumed_prec_mz,
    #                 ms.spectrum_id
    #             FROM ResultMatch AS rm
    #                 JOIN match AS m ON rm.match_id = m.id
    #                 JOIN matchedspectrum as ms ON rm.match_id = ms.match_id
    #                 WHERE rm.resultset_id = %s AND m.site1 >0 AND m.site2 >0
    #                 AND rm.top_ranking = TRUE;"""

    sql = """SELECT * FROM spectrumidentification si 
    INNER JOIN modifiedpeptide mp1 ON si.pep1_id = mp1.id AND si.upload_id = mp1.upload_id 
    INNER JOIN modifiedpeptide mp2 ON si.pep2_id = mp2.id AND si.upload_id = mp2.upload_id
    WHERE si.upload_id = %s 
    AND si.pass_threshold = TRUE 
    AND mp1.link_site1 > 0
    AND mp2.link_site1 > 0;"""
    # bit weid above works when link_site1 is a text column

    cur.execute(sql, [uuid])
    matches = []
    search_peptide_ids = {}
    while True:
        match_rows = cur.fetchmany(5000)
        if not match_rows:
            break

        for match_row in match_rows:
            peptide1_id = match_row[5]
            peptide2_id = match_row[6]
            search_id = match_row[1]
            match = {
                "id": match_row[0],
                "pi1": peptide1_id,
                "pi2": peptide2_id,
                # "s1": match_row[],
                # "s2": match_row[],
                "sc": match_row[10],  # scores
                # "cl": match_row[],
                "si": search_id,
                "cm": match_row[12],
                "pc_c": match_row[7],
                "pc_mz": match_row[11],  # experimental mz
                "sp": match_row[2],
                "sd_ref": match_row[3],  # spectra data ref
                "pass": match_row[8],  # pass threshold
                "r": match_row[9],  # rank
            }
            if search_id in search_peptide_ids:
                peptide_ids = search_peptide_ids[search_id]
            else:
                peptide_ids = set()
                search_peptide_ids[search_id] = peptide_ids

            peptide_ids.add(peptide1_id)
            if peptide2_id is not None:
                peptide_ids.add(peptide2_id)

            matches.append(match)

    # create sql clause that selects peptides by id and resultset
    # (search_id = a AND id in(x,y,z)) OR (search_id = b AND (...)) OR ...
    first_search = True
    peptide_clause = "("
    for k, v in search_peptide_ids.items():
        if first_search:
            first_search = False
        else:
            peptide_clause += " OR "
        # todo - looks like this should be protected against sql injection
        peptide_clause += "(mp.upload_id = '" + str(search_id) + "' AND mp.id IN ('"
        # print("rs:" + str(k))
        first_pep_id = True
        for pep_id in v:
            # print("pep:" + str(pep_id))
            if first_pep_id:
                first_pep_id = False
            else:
                peptide_clause += "','"
            peptide_clause += str(pep_id)
        peptide_clause += "'))"
    peptide_clause += ")"

    return matches, peptide_clause


def get_peptides(cur, peptide_clause):
    if peptide_clause != "()":
        sql = """SELECT mp.id, mp.upload_id AS search_uuid,
                    mp.base_sequence AS sequence,
                    array_agg(pp.dbsequence_ref) AS proteins,
                    array_agg(pp.pep_start) AS positions,
                    array_agg(pp.is_decoy) AS decoys,
                    mp.link_site1,
                    mp.mod_accessions as mod_accs,
                    mp.mod_positions as mod_pos,
                    mp.mod_monoiso_mass_deltas as mod_masses,
                    mp.crosslinker_modmass as crosslinker_modmass                     
                        FROM modifiedpeptide AS mp
                        JOIN peptideevidence AS pp
                        ON mp.id = pp.peptide_ref AND mp.upload_id = pp.upload_id
                    WHERE """ + peptide_clause + """
                    GROUP BY mp.id, mp.upload_id, mp.base_sequence;"""
        # print(sql);
        cur.execute(sql)
        peptides = []
        search_protein_ids = {}
        while True:
            peptide_rows = cur.fetchmany(5000)
            if not peptide_rows:
                break
            for peptide_row in peptide_rows:
                search_id = peptide_row[1]
                prots = peptide_row[3]
                peptide = {
                    "id": peptide_row[0],
                    "u_id": peptide_row[1],
                    "base_seq": peptide_row[2],
                    "prt": prots,
                    "pos": peptide_row[4],
                    "is_decoy": peptide_row[5],
                    "linkSite": peptide_row[6],
                    "mod_accs": peptide_row[7],
                    "mod_pos": peptide_row[8],
                    "mod_masses": peptide_row[9],
                    "cl_modmass": peptide_row[10],
                }
                if search_id in search_protein_ids:
                    protein_ids = search_protein_ids[search_id]
                else:
                    protein_ids = set()
                    search_protein_ids[search_id] = protein_ids

                for prot in prots:
                    protein_ids.add(prot)

                peptides.append(peptide)

        # create sql clause that selects proteins by id and resultset
        # (search_id = a AND id in(x,y,z)) OR (search_id = b AND (...)) OR ...
        first_search = True
        protein_clause = "("
        for k, v in search_protein_ids.items():
            if first_search:
                first_search = False
            else:
                protein_clause += " OR "
            protein_clause += "(upload_id = '" + str(search_id) + "' AND id IN ('"
            first_prot_id = True
            for prot_id in v:
                if first_prot_id:
                    first_prot_id = False
                else:
                    protein_clause += "','"
                protein_clause += str(prot_id)
            protein_clause += "'))"
        protein_clause += ")"
        return peptides, protein_clause


def get_proteins(cur, protein_clause):
    if protein_clause != "()":
        sql = """SELECT id, name, accession, sequence, upload_id, description
                    FROM dbsequence WHERE """ + protein_clause + """;"""
        logger.debug(sql)
        cur.execute(sql)
        protein_rows = cur.fetchall()
        proteins = []
        for protein_row in protein_rows:
            protein = {
                "id": protein_row[0],
                "name": protein_row[1],
                "accession": protein_row[2],
                "sequence": protein_row[3],
                "search_id": protein_row[4],
                "description": protein_row[5]
            }
            proteins.append(protein)
        return proteins


def get_layout(cur, uuid):
    sql = """SELECT t1.description, t1.layout FROM layout AS t1
        WHERE t1.resultset_id = %s ORDER BY t1.time_saved DESC LIMIT 1"""
    cur.execute(sql, [uuid])
    data = cur.fetchall()
    if data:
        xinet_layout = {
            "name": data[0][0],
            "layout": data[0][1]
        }
        return xinet_layout
