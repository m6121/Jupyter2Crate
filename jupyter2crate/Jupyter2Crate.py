import hashlib
import json
import locale
import os
import re
import shutil
import subprocess
import sys
import tempfile

import nbformat

from datetime import datetime
from pathlib import Path
from urllib import parse

from provbook.notebook_rdf.__main__ import app as provbook_rdf
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import FOAF, OWL, RDF, RDFS, XSD

from .IDGenerator import IDGenerator
from .Persons import persons, institutions

class NBNotFound(Exception):
    pass

class Jupyter2Crate:
    def __init__(self, logger, namespace_url, notebook_path):
        self.log = logger

        locale.setlocale( locale.LC_ALL, 'en_US.UTF-8' )

        self.tempfolder = tempfile.mkdtemp()
        self.nb_path = notebook_path
        if not os.path.isfile(self.nb_path):
            raise NBNotFound('Notebook not found under "%s"' % (self.nb_path))
        else:
            self.notebook = nbformat.read(self.nb_path, nbformat.NO_CONVERT)

        self.general_namespace = Namespace(namespace_url + '/')
        self.nb_namespace = Namespace('%s/%s/' % (namespace_url, os.path.basename(self.nb_path)))
        self.id_generator = IDGenerator(self.general_namespace, self.nb_namespace)
        self.nb_id = self.id_generator.getNotebook(os.path.basename(self.nb_path))

        self.graph = Graph(bind_namespaces='core')
        self.graph.bind('@base', self.nb_namespace)
        self.graph.bind('@vocab', 'https://w3id.org/ro/crate/1.2/context#')
        # self.graph.bind('elaine', 'https://eln-provenance.elaine.uni-rostock.de/ontology/0.1/')
        self.graph.bind('foaf', FOAF)
        self.graph.bind('gndo', 'https://d-nb.info/standards/elementset/gnd#')
        self.graph.bind('prov', 'http://www.w3.org/ns/prov#')
        self.graph.bind('obo', 'http://purl.obolibrary.org/obo/')
        self.graph.bind('repr', 'https://w3id.org/reproduceme#')
        self.graph.bind('p-plan', 'http://purl.org/net/p-plan/#')

    def _get_xsd_type_for_number(self, number):
        try:
            locale.atof(number)
        except ValueError:
            try:
                if locale.atoi(number) < 0:
                    raise(ValueError)
            except ValueError:
                self.log.error('Number is neither float nor int or negative int: %s' % (number))
                sys.exit(1)
            else:
                return(XSD.nonNegativeInteger)
        else:
            return(XSD.decimal)

    @staticmethod
    def create_folder_if_not_exists(folder, parents=False):
        pfolder = Path(folder)
        pfolder.mkdir(parents=parents, exist_ok=True)

    def write_files(self):
        self._write_notebook()

    def _write_notebook(self):
        filename = os.path.basename(self.nb_path)
        self.nb_path_target = os.path.join(self.tempfolder, filename)

        self.log.debug('Copying Jupyter Notebook file to "%s"' % (self.nb_path_target))
        shutil.copyfile(self.nb_path, self.nb_path_target)

    def _add_parameter_nodes(self, usage_node_id, value_specification, label, value, unit):
        par_node_id = BNode()
        self.graph.add((par_node_id, RDF.type, value_specification))
        self.graph.add((par_node_id, RDFS.label, label))
        self.graph.add((par_node_id, URIRef('prov:value'), value))
        self.graph.add((
            par_node_id,
            URIRef('http://purl.obolibrary.org/obo/IAO_0000039'), # has measurement unit label
            unit
        ))
        self.graph.add((
            usage_node_id,
            URIRef('http://purl.obolibrary.org/obo/OBI_0001938'), # has value specification
            par_node_id
        ))


    def create_model(self):
        self._call_provbook()
        self._model_nb()
        self._model_nb_cells()
        self._model_rocrate_base()

        return self.graph

    def _call_provbook(self):
        self.log.debug('Calling provbook for "%s"' % (self.nb_path_target))
        old_arguments = sys.argv[:]
        sys.argv = [
            'notebook_rdf',
            self.nb_path_target
        ]
        provbook_rdf()
        sys.argv = old_arguments

        # load provbook graph
        self.log.debug('Loading provbook graph')
        self.graph.parse(self.nb_path_target.replace('.ipynb', '.ttl'))

        # add to ro crate
        self.graph.add((
            self.id_generator.getDataset(),
            URIRef('hasPart'),
            self.id_generator.getFile(os.path.basename(self.nb_path_target.replace('.ipynb', '.ttl')))
        ))

    def _model_nb(self):
        self.graph.add((
            self.nb_id,
            RDF.type,
            URIRef('prov:Entity')
        ))
        self.graph.add((
            self.id_generator.getNotebookActivity(),
            RDF.type,
            URIRef('prov:Activity')
        ))
        self.graph.add((
            self.id_generator.getNotebookActivity(),
            RDF.type,
            URIRef('Action')
        ))
        self.graph.add((
            self.id_generator.getNotebookActivity(),
            RDF.type,
            URIRef('http://purl.obolibrary.org/obo/BFO_0000015')
        ))
        self.graph.add((
            self.id_generator.getNotebookActivity(),
            URIRef('prov:used'),
            self.nb_id
        ))
        self.graph.add((
            self.id_generator.getDataset(),
            URIRef('hasPart'),
            self.nb_id
        ))

        # map notebook to corresponding provbook node
        self.log.debug('Mapping notebook entity to provbook node')
        nb_name, _ = os.path.splitext(os.path.basename(self.nb_path))
        provbook_name = ''.join(c for c in nb_name if c.isalnum())
        self.graph.add((
            self.nb_id,
            URIRef('owl:sameAs'),
            URIRef('repr:%s' % (provbook_name))
        ))

        # map activity to corresponding provbook activities
        self.log.debug('Mapping notebook activity to provbook activities')
        nb_activity_query = """
            SELECT DISTINCT ?cellname
            WHERE {
                ?cellname rdf:type p-plan:Step .
            }
        """

        nb_activity_results = self.graph.query(nb_activity_query)
        for row in nb_activity_results:
            self.log.debug('Found provbook activity "%s"' % (row.cellname))
            self.graph.add((
                self.id_generator.getNotebookActivity(),
                URIRef('hasPart'),
                row.cellname
            ))


    def _model_input_parameters(self, parameter, usage_node_id):
        # FREQUENCY
        for frequency_search in re.finditer(r'[+-]?[,\.\d]+\s*(Hz|rpm|rps)', parameter):
            frequency = frequency_search.group()

            rps = None # variable indicating recalculation
            if re.search(r'Hz', frequency):
                frequency_unit = URIRef('http://purl.obolibrary.org/obo/UO_0000106') # hertz
            elif re.search(r'rpm', frequency):
                rps = True
                frequency_unit = URIRef('http://purl.obolibrary.org/obo/UO_0000092') # only turns per second available
            elif re.search(r'rps', frequency):
                rps = False
                frequency_unit = URIRef('http://purl.obolibrary.org/obo/UO_0000092') # turns per second
            else:
                self.log.error('frequency uses unknown unit: '+ frequency)
                sys.exit(1)

            frequency_number = re.match(r'[+-]?[,\.\d]+', frequency.strip()).group()
            self._add_parameter_nodes(
                usage_node_id,
                URIRef('http://purl.obolibrary.org/obo/OBI_0001931'),
                Literal(frequency),
                Literal(
                    locale.atof(frequency_number) / 60 if rps else frequency_number,
                    datatype=self._get_xsd_type_for_number(frequency_number)
                ),
                frequency_unit
            )

        # VOLTAGE
        for voltage_search in re.finditer(r'[+-]?[\.\d]+\s*V', parameter):
            voltage = voltage_search.group()

            voltage_number = re.match(r'[+-]?[\.\d]+', voltage.strip()).group()
            if re.search(r'V', voltage):
                self._add_parameter_nodes(
                    usage_node_id,
                    URIRef('http://purl.obolibrary.org/obo/OBI_0001931'),
                    Literal(voltage),
                    Literal(voltage_number, \
                        datatype=self._get_xsd_type_for_number(voltage_number)),
                    URIRef('http://purl.obolibrary.org/obo/UO_0000218') # V
                )
            else:
                self.log.error('Voltage uses unknown unit: '+ voltage)
                sys.exit(1)

    def _model_researcher(self, researcher_name):
        if persons.get(researcher_name):
            researcher = persons.get(researcher_name)
            organization = institutions.get(researcher['affiliation'])
            organization_id = self.id_generator.getInstitution(
                researcher['affiliation'],
                organization
            )
            researcher_id = self.id_generator.getResearcher(researcher_name, researcher)

            if (researcher_id, RDF.type, URIRef('prov:Person')) in self.graph:
                return researcher_id, organization_id

            if (organization_id, RDF.type, URIRef('prov:Organization')) not in self.graph:
                self.graph.add((organization_id, RDF.type, URIRef('prov:Organization')))
                self.graph.add((
                    organization_id,
                    URIRef('foaf:name'),
                    Literal(organization['name'], lang='en')
                ))

            self.graph.add((researcher_id, RDF.type, URIRef('prov:Person')))
            self.graph.add((
                researcher_id,
                URIRef('foaf:name'),
                Literal('%s %s' % (researcher['givenName'], researcher['familyName']), \
                    datatype=XSD.string)
            ))
            self.graph.add((
                researcher_id,
                URIRef('foaf:givenName'),
                Literal(researcher['givenName'], datatype=XSD.string)
            ))
            self.graph.add((
                researcher_id,
                URIRef('foaf:familyName'),
                Literal(researcher['familyName'], datatype=XSD.string)
            ))
            if researcher.get('email'):
                self.graph.add((
                    researcher_id,
                    URIRef('email'),
                    Literal(researcher['email'])
                ))
            self.graph.add((researcher_id, URIRef('gndo:affiliation'), organization_id))
        else:
            self.log.error('Could not find researcher name: "%s"' % (researcher_name))
            sys.exit(1)

        return researcher_id, organization_id

    def _model_nb_cells(self):
        self.log.debug('Modelling Jupyter Notebook "%s"' % (self.nb_path))

        for i, cell in enumerate(self.notebook.cells):
            if cell['cell_type'] != 'code':
                if i == 0:
                    # search for authors indicated by 'by' in the initial cell:
                    author_string = re.search(r'by ([ a-zA-Z0-9äöüß^$,]+)', cell['source'].partition('\n')[0])
                    if author_string:
                        self.log.debug('Found author string: "%s"' % (author_string.group(1)))
                        authors = re.split(r'[ ]*,[ ]*|[ ]*and[ ]*', author_string.group(1))
                        for author in authors:
                            self.log.debug('Found author: "%s"' % (author))
                            # remove affiliation
                            author = re.search(r'[ a-zA-Z0-9äöüß]+', author).group().lower()
                            researcher_id, _ = self._model_researcher(author)
                            self.graph.add((
                                self.id_generator.getNotebookActivity(),
                                URIRef('prov:wasAssociatedWith'),
                                researcher_id
                            ))
                else:
                    continue

            if cell['source'].startswith('#| prov:'):
                self.log.debug('Found cell with provenance information: "%s"' % (cell['source']))

                source_parts = cell['source'].partition('\n')
                prov_meta = json.loads(source_parts[0].replace('#| prov:', '').strip())
                self.log.debug('extracted provenance metadata: %s' % (prov_meta))


                if prov_meta['type'] == 'input-files' or prov_meta['type'] == 'output-files':

                    if prov_meta.get('parameters'):
                        usage_node_id = BNode()
                        self.graph.add((
                            self.id_generator.getNotebookActivity(),
                            URIRef('prov:qualifiedUsage'),
                            usage_node_id
                        ))
                        for par in prov_meta['parameters']:
                            self._model_input_parameters(par, usage_node_id)

                    self.log.debug('searching for input/output files...')
                    for part in source_parts:
                        for match in re.finditer(r'([#\s]*)"([-a-zA-Z0-9/_\.]+\.[a-z]+)"', part):
                            self.log.debug('...found input/output: %s' % (match.group(0)))

                            if '#' in match.group(1).strip():
                                self.log.debug('\t...input/output not relevant as commented')
                                continue

                            file_path = match.group(2).strip()
                            crate_file_path = re.sub(r'^/', '', file_path)
                            crate_file_path_abs = os.path.join(self.tempfolder, crate_file_path)
                            # copy file
                            Jupyter2Crate.create_folder_if_not_exists(os.path.dirname(crate_file_path_abs), parents=True)
                            shutil.copyfile(file_path, os.path.join(self.tempfolder, crate_file_path))

                            self.graph.add((
                                self.id_generator.getFile(crate_file_path),
                                RDF.type,
                                URIRef('prov:Entity')
                            ))

                            if prov_meta['type'] == 'input-files':
                                self.graph.add((
                                    self.id_generator.getNotebookActivity(),
                                    URIRef('prov:used'),
                                    self.id_generator.getFile(crate_file_path),
                                ))
                                if prov_meta.get('parameters'):
                                    self.graph.add((
                                        usage_node_id,
                                        URIRef('prov:entity'),
                                        self.id_generator.getFile(crate_file_path)
                                    ))

                            elif prov_meta['type'] == 'output-files':
                                self.graph.add((
                                    self.id_generator.getFile(crate_file_path),
                                    URIRef('prov:wasGeneratedBy'),
                                    self.id_generator.getNotebookActivity(),
                                ))

                            # independent of input/output context, add file to dataset
                            self.graph.add((
                                self.id_generator.getDataset(),
                                URIRef('hasPart'),
                                self.id_generator.getFile(crate_file_path)
                            ))

                elif prov_meta['type'] == 'output':
                    h = hashlib.sha256()
                    h.update(str(cell).encode())
                    cell_id = self.id_generator.getOutputCell(h.hexdigest())
                    self.graph.add((
                        cell_id,
                        URIRef('prov:wasGeneratedBy'),
                        self.id_generator.getNotebookActivity(),
                    ))
                    self.graph.add((cell_id, RDF.type, URIRef('prov:Entity')))
                    self.graph.add((cell_id, RDFS.label, Literal(str(cell['outputs']), datatype=XSD.string)))

                    # search corresponding provbook cell to link accordingly
                    self.log.debug('Map notebook output entity to provbook cell')
                    nb_output_query = """
                        SELECT DISTINCT ?outputname
                        WHERE {
                            ?cellname p-plan:hasOutputVar ?outputname .
                            ?cellname rdf:type p-plan:Step .
                            ?cellname p-plan:hasInputVar ?source .
                            ?source rdf:value \"\"\"%s\"\"\" .
                        }
                    """ % (cell['source'])
                    self.log.debug("Query: %s" % (nb_output_query))

                    nb_output_results = self.graph.query(nb_output_query)
                    for row in nb_output_results:
                        self.log.debug('Found provbook cell output "%s"' % (row.outputname))
                        self.graph.add((
                            cell_id,
                            URIRef('p-plan:correspondsToVariable'),
                            row.outputname
                        ))

    def _model_rocrate_base(self):
        graph_base = URIRef('ro-crate-metadata.json')
        self.graph_dir = self.id_generator.getDataset()
        self.graph.add((graph_base, RDF.type, URIRef('CreativeWork')))
        self.graph.add((
            graph_base,
            URIRef('conformsTo'),
            URIRef('https://w3id.org/ro/crate/1.2')
        ))
        self.graph.add((graph_base, URIRef('about'), self.graph_dir))

        self.graph.add((self.graph_dir, RDF.type, URIRef('Dataset')))
        # FIXME
        # self.graph.add((self.graph_dir, URIRef('creator'), self.researcher_id))
        # self.graph.add((
        #     self.graph_dir,
        #     URIRef('name'),
        #     Literal(self.exp['title'], lang='en')
        # ))
        # lastchange = datetime.strptime(self.exp['lastchange'], '%Y-%m-%d %H:%M:%S')
        # self.graph.add((
        #     self.graph_dir,
        #     URIRef('datePublished'),
        #     Literal(lastchange, datatype=XSD.dateTime)
        # ))

        # FIXME: adjust to corresponding license
        license_id = URIRef('https://creativecommons.org/licenses/by/4.0/')
        self.graph.add((self.graph_dir, URIRef('license'), license_id))
        self.graph.add((license_id, RDF.type, URIRef('CreativeWork')))
        self.graph.add((
            license_id,
            URIRef('name'),
            Literal('Attribution 4.0 International (CC BY 4.0)', lang='en')
        ))
        self.graph.add((license_id, URIRef('identifier'), license_id))
        self.graph.add((
            license_id,
            URIRef('description'),
            Literal('This work is licensed under a Creative Commons Attribution 4.0 International License.', lang='en')
        ))

    def write_crate(self, target_archive):
        self.graph.serialize(
            format='json-ld',
            auto_compact=True,
            destination=os.path.join(self.tempfolder, 'ro-crate-metadata.json')
        )
        shutil.make_archive(target_archive, 'zip', self.tempfolder)

    def __del__(self):
        if os.path.isdir(self.tempfolder):
            shutil.rmtree(self.tempfolder)