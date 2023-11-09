class ProteinDetails:

    def __init__(self, proteins, peptides, spectra, cross_linking, pdb):
        self.proteins = proteins
        self.peptides = peptides
        self.spectra = spectra
        self.cross_linking = cross_linking
        self.pdb = pdb

    # def to_dict(self):
    #     return {
    #         'proteins': self.self.proteins,
    #         'peptides': self.self.peptides,
    #         'spectra': self.self.spectra,
    #         'cross_linking': self.self.cross_linking,
    #         'pdb': self.self.pdb
    #     }
