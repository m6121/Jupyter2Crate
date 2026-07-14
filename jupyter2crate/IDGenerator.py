from rdflib import URIRef

class IDGenerator:
    def __init__(self, general_namespace, nb_namespace):
        self.general_namespace = general_namespace
        self.nb_namespace = nb_namespace

    def getDataset(self):
        return URIRef('./')

    def getNotebook(self, nb_file):
        nb_id = 'Notebook/%s' % (nb_file)

        return self.getFile(nb_id)

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

