from xi_web_api.models.proteindetails import ProteinDetails


class DetailedView:

    def __init__(self, accession, title, description, pubmed_id, protein_details):
        self.accession = accession
        self.title = title
        self.description = description
        self.pubmed_id = pubmed_id
        self.protein_details = protein_details

    def add_protein_details(self, protein_details):
        if isinstance(protein_details, ProteinDetails):
            self.protein_details.append(protein_details)
        else:
            print("Invalid protein_details object. Please provide a protein_details instance.")

    def remove_protein_details(self, protein_details):
        if protein_details in self.protein_details:
            self.protein_details.remove(protein_details)
        else:
            print("Protein details not found in the Detailed View.")

    # def to_dict(self):
    #     return {
    #         'accession': self.accession,
    #         'title': self.title,
    #         'description': self.description,
    #         'pubmed_id': self.pubmed_id,
    #         'protein_details': self.protein_details
    #     }