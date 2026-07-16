from rdflib import URIRef

class IDGenerator:
    def __init__(self, general_namespace, nb_namespace):
        self.general_namespace = general_namespace
        self.nb_namespace = nb_namespace

    def getResearcher(self, researcher_key, researcher):
        if researcher.get('orcid'):
            return URIRef(researcher['orcid'])

        researcher_key = researcher_key.replace(' ', '_')
        researcher_key = researcher_key.replace('ä', 'ae')
        researcher_key = researcher_key.replace('ö', 'oe')
        researcher_key = researcher_key.replace('ü', 'ue')
        researcher_key = researcher_key.replace('ß', 'ss')
        researcher_id = 'researcher/%s' % (researcher_key)

        return URIRef(self.general_namespace[researcher_id])

    def getInstitution(self, institution_key, institution):
        if institution.get('ror'):
            return URIRef(institution.get('ror'))

        institution_id = 'institution/%s' % (institution_key)

        return URIRef(self.general_namespace[institution_id])

    def getDataset(self):
        return URIRef('./')

    def getNotebook(self, nb_file):
        return self.getFile(nb_file)

    def getNotebookActivity(self):
        return URIRef(self.nb_namespace['execution'])

    def getLicense(self, license_name):
        license_id = 'license/%s' % (license_name)

        return URIRef(self.general_namespace[license_id])

    def getFile(self, filepath):
        return URIRef(filepath.replace(' ', '%20'))

    def getOutputCell(self, cell_hash):
        cell_id = 'cell/%s' % (cell_hash)

        return URIRef(self.nb_namespace[cell_id])

