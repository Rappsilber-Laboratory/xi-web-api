from xi2_xiview_loader.pdbdev import bp
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import jsonify
from xi2_xiview_loader import get_db_connection


@bp.route('/projects/<project_id>/sequences', methods=['GET'])
def sequences(project_id):
    """
    Get all sequences belonging to a project.

    :param project_id: identifier of a project, for ProteomeXchange projects this is the PXD****** accession
    :return: JSON object with all dbref id, mzIdentML file it came from and sequences
    """
    conn = None
    mzid_rows = []
    try:
        # connect to the PostgreSQL server and create a cursor
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        sql = """SELECT s.id, u.identification_file_name, s.sequence   
                    FROM upload AS u 
                    JOIN dbsequence AS s ON u.id = s.upload_id 
                 WHERE u.project_id = %s;"""

        print(sql)
        cur.execute(sql, [project_id])
        mzid_rows = cur.fetchall()

        print("finished")
        # close the communication with the PostgreSQL
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
            print('Database connection closed.')
        return jsonify(mzid_rows)


@bp.route('/projects/<project_id>/residue-pairs/psm-level', methods=['GET'])
def get_psm_level_residue_pairs(project_id):
    """
    Get all residue pairs (based on PSM level data) belonging to a project.

    There will be multiple entries for identifications with positional uncertainty of peptide in protein sequences.
    :param project_id: identifier of a project, for ProteomeXchange projects this is the PXD****** accession
    :return:
    """
    conn = None
    mzid_rows = []
    try:
        # connect to the PostgreSQL server and create a cursor
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        sql = """SELECT si.id, u.identification_file_name,
si.pep1_id, pe1.dbsequence_ref as pep1_prot_id, (pe1.pep_start + mp1.link_site1 - 1) as abspos1,
si.pep2_id, pe2.dbsequence_ref as pep2_prot_id, (pe2.pep_start + mp2.link_site1 - 1) as abspos2 FROM  
spectrumidentification si INNER JOIN 
modifiedpeptide mp1 ON si.pep1_id = mp1.id AND si.upload_id = mp1.upload_id INNER JOIN 
peptideevidence pe1 ON mp1.id = pe1.peptide_ref AND mp1.upload_id = pe1.upload_id INNER JOIN 
modifiedpeptide mp2 ON si.pep2_id = mp2.id AND si.upload_id = mp2.upload_id INNER JOIN 
peptideevidence pe2 ON mp2.id = pe2.peptide_ref AND mp2.upload_id = pe2.upload_id INNER JOIN 
upload u on u.id = si.upload_id
where u.project_id = %s and mp1.link_site1 is not null and mp2.link_site1 is not null;"""

        print(sql)
        cur.execute(sql, [project_id])
        mzid_rows = cur.fetchall()

        print("finished")
        # close the communication with the PostgreSQL
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
            print('Database connection closed.')
        return jsonify(mzid_rows)


@bp.route('/projects/<project_id>/residue-pairs/reported', methods=['GET'])
def get_reported_residue_pairs(project_id):
    """
    Get all residue-pairs reported for a project from the ProteinDetectionList element(s).

    :param project_id: identifier of a project, for ProteomeXchange projects this is the PXD****** accession
    :return:
    """
    return "Not Implemented"


@bp.route('/projects/<project_id>/reported-thresholds', methods=['GET'])
def get_reported_thresholds(project_id):
    """
    Get all reported thresholds for a project.

    :param project_id: identifier of a project, for ProteomeXchange projects this is the PXD****** accession
    :return:
    """
    return "Not Implemented"
