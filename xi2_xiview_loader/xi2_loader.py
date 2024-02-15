import json
import re
from time import time
from configparser import ConfigParser

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from flask import Flask, request
from flask_cors import CORS
import orjson


def create_app(config='database.ini'):
    """
    Create the flask app.

    :return: flask app
    """
    app = Flask(__name__, static_url_path="", static_folder='../static')
    CORS(app)

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

    @app.route('/get_data', methods=['GET'])
    async def get_data():
        uuid_param = request.args.get('uuid')  # uuid of search
        # quit if uuid contains char that isn't alphanumeric, underscore, dash, tilde, period
        if uuid_param is None or not re.match(r'^[a-zA-Z0-9.~_-]+$', uuid_param):
            return orjson.dumps({"error": "Invalid id(s)"}), 400

        if '.' in uuid_param:
            groups = uuid_param.split('.')
            uuid_dict = {s.split('~')[0]: s.split('~')[1] for s in groups}
            uuids = list(uuid_dict.keys())
        else:
            uuids = [uuid_param]
            uuid_dict = {}

        conn = None
        data = {}
        try:
            conn = psycopg2.connect(**db_info)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            data["sid"] = uuid_param
            data["searches"] = await get_resultset_search_metadata(cur, uuids, uuid_dict)
            data["primary_score"] = await get_primary_score(cur, uuids[0])
            data["matches"] = await get_matches(cur, uuids, data["primary_score"]["score_index"])
            data["peptides"] = await get_peptides(cur, data["matches"])
            data["proteins"] = await get_proteins(cur, data["peptides"])
            data["xiNETLayout"] = await get_layout(cur, uuid_param)
            cur.close()
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
        finally:
            if conn is not None:
                conn.close()
            return orjson.dumps(data)

    @app.route('/get_peaklist', methods=['GET'])
    async def get_peaklist():
        spectrum_uuid = request.args.get('uuid')
        conn = None
        data = {}
        try:
            conn = psycopg2.connect(**db_info)
            cur = conn.cursor()
            query = sql.SQL("SELECT intensity, mz FROM spectrumpeaks WHERE id = {}").format(sql.Literal(spectrum_uuid))
            cur.execute(query)
            data = cur.fetchall()[0]
            cur.close()
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
        finally:
            if conn is not None:
                conn.close()
                print('Database connection closed.')
            return orjson.dumps(data)

    @app.route('/save_layout', methods=['POST'])
    async def save_layout():
        uuid = request.form['sid']
        layout = request.form['layout']
        description = request.form['name']
        conn = None
        try:
            conn = psycopg2.connect(**db_info)
            cur = conn.cursor()
            query = sql.SQL("INSERT INTO layout (url_param, layout, description) VALUES ({}, {}, {})").format(
                sql.Literal(uuid), sql.Literal(layout), sql.Literal(description)
            )
            cur.execute(query)
            conn.commit()
            cur.close()
            return "Layout saved!"
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
        finally:
            if conn is not None:
                conn.close()

    @app.route('/load_layout', methods=['POST'])
    async def load_layout():
        # actually returns all different layouts available
        uuid = request.form['sid']
        conn = None
        try:
            conn = psycopg2.connect(**db_info)
            cur = conn.cursor()
            query = sql.SQL("""SELECT t1.layout AS layout, t1.description AS name FROM layout AS t1
                  WHERE t1.url_param = {} AND t1.time_saved IN
                  (SELECT max(t1.time_saved) FROM layout AS t1  WHERE t1.url_param = {} GROUP BY t1.description);"""
                            ).format(sql.Literal(uuid), sql.Literal(uuid))
            # sql = """SELECT t1.description, t1.layout FROM layout AS t1
            #     WHERE t1.resultset_id = %s ORDER BY t1.time_saved desc LIMIT 1"""
            cur.execute(query)
            layouts = cur.fetchall()
            data = {}
            # xinet_layout = {
            #     "name": data[0],
            #     "layout": data[1]
            # }
            for layout in layouts:
                data[str(layout[1])] = layout[0]
            cur.close()
            return orjson.dumps(data)
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
        finally:
            if conn is not None:
                conn.close()

    @app.route('/network.html', methods=['GET'])
    async def network():
        # uuid = request.args.get('uuid')
        return app.send_static_file('network.html')

    @app.route('/spectra.html', methods=['GET'])
    async def spectra():
        # uuid = request.args.get('uuid')
        return app.send_static_file('spectra.html')

    return app


async def get_primary_score(cur, uuid):
    query = sql.SQL("""SELECT sn.name AS score_name, sn.score_id AS score_index, sn.higher_is_better AS higher_better
                    FROM scorename AS sn
                    WHERE sn.resultset_id = {} AND sn.primary_score = TRUE""").format(sql.Literal(uuid))
    cur.execute(query)
    return cur.fetchone()


async def get_resultset_search_metadata(cur, uuids, uuid_dict):
    query = sql.SQL("""
                SELECT rs.name AS rs_name, rs.note AS rs_note, rs.config AS rs_config, rs.main_score AS rs_main_score, 
                      rst.name AS resultset_type,
                      rs.id AS id, s.name AS s_name, s.config AS s_config, s.note AS s_note, s.id AS s_id
                 FROM resultset AS rs
                  LEFT JOIN resultsettype AS rst ON (rs.rstype_id = rst.id)
                  LEFT JOIN ResultSearch AS result_search ON (rs.id = result_search.resultset_id)
                  LEFT JOIN Search AS s ON (result_search.search_id = s.id)
                WHERE rs.id IN {uuids}
                           """).format(uuids=sql.Literal(tuple(uuids)))
    before = time()
    cur.execute(query)
    after = time()
    print(after - before)
    resultset_meta_cur = cur.fetchall()
    # mainscore = resultset_meta_cur[0]['rs_main_score'] #  taking first resultsets mainscore as overall main score
    resultsets = {}
    for rs_row in resultset_meta_cur:
        resultset_id = str(rs_row['id'])
        if resultset_id in uuid_dict:
            group = uuid_dict[resultset_id]
            rs_row['group'] = group
        rs_row['s_config'] = json.loads(rs_row['s_config'])
        resultsets[resultset_id] = rs_row
    return resultsets


async def get_matches(cur, uuids, main_score_index):
    # small heuristic to see if the score is between 0 and 1
    query_score = sql.SQL("""WITH score_idx AS (SELECT {score_idx} id)
SELECT max(score) FROM (
                        SELECT scores[score_idx.id + array_lower(scores,1)] as score from resultmatch, score_idx
                        WHERE resultset_id in ({uuids})
                        AND scores[score_idx.id + array_lower(scores,1)] != 'NaN' limit 1000) s;"""
                          ).format(score_idx=sql.Literal(main_score_index),
                                   uuids=sql.SQL(',').join([sql.Literal(uuid) for uuid in uuids]))
    cur.execute(query_score)
    max_score = cur.fetchone()
    if max_score['max'] < 1:
        score_factor = 100
    else:
        score_factor = 1

    # todo - the join to matchedspectrum for cleavable crosslinker - needs a GROUP BY match_id?'
    query = sql.SQL("""SELECT m.id AS id, m.pep1_id AS pi1, m.pep2_id AS pi2, 
                    CASE WHEN rm.site1 IS NOT NULL THEN rm.site1 ELSE m.site1 END AS s1, 
                    CASE WHEN rm.site2 IS NOT NULL THEN rm.site2 ELSE m.site2 END AS s2, 
                    rm.scores[{score_idx} + array_lower(rm.scores, 1) ] * {score_factor}  AS sc,
                     m.crosslinker_id AS cl,
                    m.search_id AS si, m.calc_mass AS cm, m.assumed_prec_charge AS pc_c, m.assumed_prec_mz AS pc_mz,
                    ms.spectrum_id AS sp, rm.resultset_id AS rs_id,
                    s.precursor_mz AS pc_mz, s.precursor_charge AS pc_c, s.precursor_intensity AS pc_i,
                    s.scan_number AS sn, s.scan_index AS sc_i,
                    s.retention_time AS rt, r.name AS run, s.peaklist_id AS plf
                FROM ResultMatch AS rm
                    JOIN match AS m ON rm.search_id = m.search_id AND rm.match_id = m.id
                    JOIN matchedspectrum as ms ON rm.match_id = ms.match_id
                    JOIN spectrum as s ON ms.spectrum_id = s.id
                    JOIN run as r ON s.run_id = r.id
                    WHERE rm.resultset_id IN {uuids}
                    AND m.site1 >0 AND m.site2 >0
                    AND rm.top_ranking = TRUE;""").format(
        score_factor=sql.Literal(score_factor), score_idx=sql.Literal(main_score_index), uuids=sql.Literal(tuple(uuids))
    )
    # print('Matches query:')
    # print(' '.join(sql.split()))
    before = time()
    cur.execute(query)
    after = time()
    print(after - before)
    return cur.fetchall()


async def get_peptides(cur, match_rows):
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
        subclause = sql.SQL("(mp.search_id = {} AND mp.id IN ({}))").format(
            sql.Literal(k),
            joined_pep_ids
        )
        subclauses.append(subclause)
    peptide_clause = sql.SQL(" OR ").join(subclauses)

    query = sql.SQL("""SELECT mp.id, mp.search_id AS search_id,
                                mp.sequence AS seq_mods,
                                mp.modification_ids AS mod_ids,
                                mp.modification_position AS mod_pos,
                                array_agg(p.accession) AS prt,
                                array_agg(pp.start) AS pos
                                    FROM modifiedpeptide AS mp
                                    JOIN peptideposition AS pp
                                    ON mp.id = pp.mod_pep_id AND mp.search_id = pp.search_id
                                    JOIN protein AS p
                                    ON pp.protein_id = p.id AND pp.search_id = p.search_id
                WHERE {}
                GROUP BY mp.id, mp.search_id, mp.sequence;""").format(
        peptide_clause
    )
    print("peptides query:\n", query.as_string(cur))
    cur.execute(query)
    return cur.fetchall()


async def get_proteins(cur, peptide_rows):
    search_protein_ids = {}
    for peptide_row in peptide_rows:
        if peptide_row['search_id'] in search_protein_ids:
            protein_ids = search_protein_ids[peptide_row['search_id']]
        else:
            protein_ids = set()
            search_protein_ids[peptide_row['search_id']] = protein_ids
        for prot in peptide_row['prt']:
            protein_ids.add(prot)

    subclauses = []
    for k, v in search_protein_ids.items():
        literals = []
        for prot_id in v:
            literals.append(sql.Literal(prot_id))
        joined_literals = sql.SQL(",").join(literals)
        subclause = sql.SQL("(search_id = {} AND accession IN ({}))").format(
            sql.Literal(k),
            joined_literals
        )
        subclauses.append(subclause)

    protein_clause = sql.SQL(" OR ").join(subclauses)
    query = sql.SQL("""SELECT accession AS id, name, accession, sequence,
                     search_id, is_decoy FROM protein WHERE ({});""").format(
        protein_clause
    )
    # logger.debug(query.as_string(cur))
    cur.execute(query)
    return cur.fetchall()


async def get_layout(cur, uuid):
    query = sql.SQL("""SELECT t1.description AS name, t1.layout FROM layout AS t1 
        WHERE t1.url_param = {} ORDER BY t1.time_saved DESC LIMIT 1""").format(
        sql.Literal(uuid)
    )
    cur.execute(query)
    data = cur.fetchall()
    if data:
        xinet_layout = {
            "name": data[0]['name'],
            "layout": data[0]['t1']
        }
        return xinet_layout
