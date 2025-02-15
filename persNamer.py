#!/usr/bin/env python3
import sys
import requests
import unicodedata
import re
from rdflib import Graph, URIRef, RDFS, Namespace
from rdflib.exceptions import ParserError
from lxml import etree

def generate_xml_id(full_name, viaf):
    """
    Given a full name (e.g., "Charles deTéligny"), returns an XML id in the format:
      pers-[familyname]-[givenname initial]
    If full_name is empty, falls back to using the VIAF number.
    """
    if not full_name or full_name.strip() == "":
        return f"pers-viaf-{viaf}"
    tokens = full_name.split()
    if len(tokens) >= 2:
        given = tokens[0]
        family = tokens[-1]
    else:
        # Fallback: use the full name as family and first character as given
        family = full_name
        given = full_name[0]
    # Normalize: remove diacritics and non-alphanumeric characters
    family_ascii = unicodedata.normalize('NFKD', family)
    family_ascii = ''.join(c for c in family_ascii if not unicodedata.combining(c))
    family_ascii = re.sub(r'[^a-zA-Z0-9]', '', family_ascii).lower()
    given_initial = given[0].lower() if given else ''
    return f"pers-{family_ascii}-{given_initial}"

def fetch_viaf_rdf(viaf):
    """
    Fetches the RDF representation of a VIAF record using HTTP content negotiation,
    requesting RDF/XML.
    """
    print("Starting to fetch VIAF record (RDF)...")
    url = f"https://viaf.org/viaf/{viaf}"
    print(f"Fetching data from URL: {url}")
    headers = {
        "Accept": "application/rdf+xml",  # Request RDF/XML
        "User-Agent": "persNamer/1.0 (verbose mode)"
    }
    try:
        response = requests.get(url, headers=headers, allow_redirects=True)
        response.raise_for_status()
        print("Successfully fetched VIAF RDF data.")
        return response.content  # Return raw bytes
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error while fetching VIAF record: {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Network error while fetching VIAF record: {e}")
        sys.exit(1)

def parse_viaf_rdf(rdf_bytes, viaf):
    """
    Parses the RDF (forcing format='xml') to extract a preferred name, birth date, and death date.
    Tries several possible subject URIs and checks additional name properties.
    """
    print("Parsing RDF data with rdflib, forcing format='xml'...")
    g = Graph()
    try:
        g.parse(data=rdf_bytes, format="xml")
    except ParserError as e:
        print("RDF/XML parser error. The data might be malformed RDF or HTML.")
        print("Raw response (truncated):")
        print(rdf_bytes[:2000])
        sys.exit(f"Exiting due to parser error: {e}")

    # Define namespaces
    VIAF = Namespace("http://viaf.org/ontology/1.1#")
    SCHEMA = Namespace("http://schema.org/")
    MADS = Namespace("http://www.loc.gov/mads/rdf/v1#")
    SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

    name = None
    birth = None
    death = None

    # Try several possible subject URIs
    subjects = [
        URIRef(f"http://viaf.org/viaf/{viaf}/"),
        URIRef(f"http://viaf.org/viaf/{viaf}"),
        URIRef(f"https://viaf.org/viaf/{viaf}/"),
        URIRef(f"https://viaf.org/viaf/{viaf}")
    ]

    def extract_from_subject(subj):
        nonlocal name, birth, death
        for p, o in g.predicate_objects(subj):
            # Look for name using several possible properties
            if p in (RDFS.label, SCHEMA.name, VIAF.mainHead, MADS.authoritativeLabel, SKOS.prefLabel):
                if o and str(o).strip():
                    name = str(o).strip()
            # Look for birth date
            elif p in (VIAF.birthDate, SCHEMA.birthDate):
                birth = str(o).strip()
            # Look for death date
            elif p in (VIAF.deathDate, SCHEMA.deathDate):
                death = str(o).strip()

    for subj in subjects:
        extract_from_subject(subj)
        if name or birth or death:
            break

    return name, birth, death

def create_person_entry(viaf, name, birth, death):
    """
    Builds a TEI <person> element:
      - xml:id is generated from the name in the format "pers-[familyname]-[givenname initial]"
      - Contains a plain <persName> (without a ref attribute) for the authority file.
      - Optionally includes <birth> and <death> if data is present.
      - Includes <idno type="VIAF"> with the VIAF number.
    """
    print("Creating TEI XML entry for the authority file...")
    NS_XML = "http://www.w3.org/XML/1998/namespace"
    xml_id = generate_xml_id(name, viaf) if name and name.strip() else f"pers-viaf-{viaf}"
    person = etree.Element('person', {f'{{{NS_XML}}}id': xml_id})

    persName = etree.SubElement(person, 'persName')
    persName.text = name if name else "Unknown Name"

    if birth:
        birth_el = etree.SubElement(person, 'birth')
        birth_el.text = birth
    if death:
        death_el = etree.SubElement(person, 'death')
        death_el.text = death

    idno = etree.SubElement(person, 'idno', attrib={'type': 'VIAF'})
    idno.text = viaf

    print("TEI entry created successfully.")
    return person

def create_annotation_tag(xml_id, name):
    """
    Creates a separate annotation tag that can be used in the TEI text.
    The tag is <persName ref="#{xml_id}">Name</persName>
    """
    annotation = etree.Element('persName', attrib={"ref": f"#{xml_id}"})
    annotation.text = name if name else "Unknown Name"
    return annotation

def main():
    if len(sys.argv) != 2:
        print("Usage: persNamer.py <VIAF number>")
        sys.exit(1)
    viaf = sys.argv[1]
    print(f"Processing VIAF number: {viaf}")

    rdf_bytes = fetch_viaf_rdf(viaf)
    name, birth, death = parse_viaf_rdf(rdf_bytes, viaf)

    print(f"Name found: {name if name else '(none)'}")
    print(f"Birth date found: {birth if birth else '(none)'}")
    print(f"Death date found: {death if death else '(none)'}")
    print("Creating TEI XML entry for the authority file...")

    person_entry = create_person_entry(viaf, name, birth, death)
    xml_id = person_entry.get("{http://www.w3.org/XML/1998/namespace}id")

    # Create the annotation tag for use in the TEI text file.
    annotation_tag = create_annotation_tag(xml_id, name)

    # Add spacing between verbose messages and final outputs
    print("\n" * 3)
    print("Final Authority XML entry:")
    authority_xml = etree.tostring(person_entry, pretty_print=True, encoding='unicode')
    print(authority_xml)

    print("\nFinal Annotation tag for TEI text (to be used separately):")
    annotation_xml = etree.tostring(annotation_tag, pretty_print=True, encoding='unicode')
    print(annotation_xml)

if __name__ == '__main__':
    main()
