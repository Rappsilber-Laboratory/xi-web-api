import flask
from flask import request, jsonify
from flask_cors import CORS
import psycopg2  # todo - use sqlalchemy instead?
import os
from config import config
import json

app = flask.Flask(__name__)
cors = CORS(app)  # todo - not working?
app.config["DEBUG"] = True


@app.route('/get_data', methods=['GET'])
def get_data():
    uuid = request.args.get('uuid')
    # return json.dumps(get_data_object(uuid))
    return jsonify(get_data_object(uuid))


def get_data_object(uuid):
    """ Connect to the PostgreSQL database server """
    conn = None
    data = {}
    try:
        # read connection parameters
        params = config()

        # connect to the PostgreSQL server
        print('Connecting to the PostgreSQL database...')
        conn = psycopg2.connect(**params)

        # create a cursor
        cur = conn.cursor()

        data["resultset"], data["searches"] = get_resultset_search_metadata(cur, uuid)
        data["matches"], peptide_clause = get_matches(cur, uuid)
        data["peptides"], protein_clause = get_peptides(cur, peptide_clause)
        data["proteins"] = get_proteins(cur, protein_clause)

        print("finished")
        # close the communication with the PostgreSQL
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
            print('Database connection closed.')
        return data


def get_resultset_search_metadata(cur, uuid):
    sql = """
                SELECT rs.name, rs.note, rs.config, rs.main_score, rst.name,
                      s.id, s.name, s.config, s.note
                 FROM resultset as rs
                  LEFT JOIN resultsettype as rst on (rs.rstype_id = rst.id)
                  LEFT JOIN ResultSearch as result_search on (rs.id = result_search.resultset_id)
                  LEFT JOIN Search as s on (result_search.search_id = s.id)
                where rs.id = %s
                           """
    cur.execute(sql, [uuid])
    resultset_meta_cur = cur.fetchall()
    first_row = resultset_meta_cur[0]
    # todo resultset.config in db, column is text but value is json
    resultset_meta = {
        "name": first_row[0],
        "note": first_row[1],
        "config": json.loads(first_row[2]),
        "mainscore": first_row[3],
        "resultsettype": first_row[4]
    }
    searches = {}
    for search_row in resultset_meta_cur:
        search = {}
        search["id"] = search_row[5]
        search["name"] = search_row[6]
        search["config"] = json.loads(search_row[7])
        # search["note"] = search_row[8]
        searches[search["id"]] = search
    return resultset_meta, searches


def get_matches(cur, uuid):
    # todo - the join to matchedspectrum for cleavable crosslinker - needs a GROUP BY match_id?'
    sql = """select m.id, m.pep1_id, m.pep2_id, m.site1, m.site2, m.score, m.crosslinker_id,
                    m.search_id, m.calc_mass, m.assumed_prec_charge, m.assumed_prec_mz,
                    ms.spectrum_id
                from ResultMatch as rm
                    JOIN match as m on rm.match_id = m.id
                    JOIN matchedspectrum as ms ON rm.match_id = ms.match_id
                    where rm.resultset_id = %s AND m.site1 != -1
                   """
    # print(sql)
    cur.execute(sql, [uuid])
    matches = []
    search_peptide_ids = {}
    while True:
        match_rows = cur.fetchmany(5000)
        if not match_rows:
            break

        for match_row in match_rows:
            peptide1_id = match_row[1]
            peptide2_id = match_row[2]
            search_id = match_row[7]
            match = {
                "id": match_row[0],
                "pi1": peptide1_id,
                "pi2": peptide2_id,
                "s1": match_row[3] + 1,
                "s2": match_row[4] + 1,
                "sc": match_row[5],
                "cl": match_row[6],
                "si": search_id,
                "cm": match_row[8],
                "pc_c": match_row[9],
                "pc_mz": match_row[10],
                "sp_id": match_row[11]
            }
            peptide_ids = None
            if search_id in search_peptide_ids:
                peptide_ids = search_peptide_ids[search_id]
            else:
                peptide_ids = set()
                search_peptide_ids[search_id] = peptide_ids

            peptide_ids.add(peptide1_id)
            if peptide2_id:
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
        peptide_clause += "(mp.search_id = '" + str(search_id) + "' AND mp.id in ("
        # print("rs:" + str(k))
        first_pep_id = True
        for pep_id in v:
            # print("pep:" + str(pep_id))
            if first_pep_id:
                first_pep_id = False
            else:
                peptide_clause += ","
            peptide_clause += str(pep_id)
        peptide_clause += "))"
    peptide_clause += ")"

    return matches, peptide_clause


def get_peptides(cur, peptide_clause):
    sql = """select mp.id, (array_agg(mp.search_id))[1] as search_uuid,
                            (array_agg(mp.base_sequence))[1] as sequence,
                            array_agg(pp.protein_id) as proteins,
                            array_agg(pp.start + 1) as positions
                                from modifiedpeptide as mp
                                JOIN peptideposition as pp
                                ON mp.id = pp.mod_pep_id AND mp.search_id = pp.search_id
                            where """ + peptide_clause + """ GROUP BY mp.id
                           """
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
                "seq_mods": peptide_row[2],
                "prt": prots,
                "pos": peptide_row[4]
            }
            protein_ids = None
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
        protein_clause += "(search_id = '" + str(search_id) + "' AND id in ("
        first_prot_id = True
        for prot_id in v:
            if first_prot_id:
                first_prot_id = False
            else:
                protein_clause += ","
            protein_clause += str(prot_id)
        protein_clause += "))"

    return peptides, protein_clause


def get_proteins(cur, protein_clause):
    sql = """SELECT id, name, accession, sequence, search_id, is_decoy FROM protein
                            WHERE """ + protein_clause + """)
                            """
    # print(sql);
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
            "is_decoy": protein_row[5]
        }
        proteins.append(protein)
    return proteins


if __name__ == '__main__':
    app.run(host=os.getenv("app_host"), port="5001", debug=True)
