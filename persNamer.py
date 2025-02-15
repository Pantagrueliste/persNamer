#!/usr/bin/env python3
import sys
import requests
import unicodedata
import re
from rdflib import Graph, URIRef, RDFS, Namespace
from rdflib.exceptions import ParserError
from lxml import etree

def fix_name_spacing(name):
    """
    Inserts a space between a lowercase letter and an uppercase letter
    if not already present.
    Example: "Gian GaleazzoSanseverino" -> "Gian Galeazzo Sanseverino"
    """
    return re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', name)

def generate_xml_id(full_name, viaf):
    """
    Given a full name (e.g., "Gian Galeazzo Sanseverino"), returns an XML id in the format:
      pers-[familyname]-[givenname initial]
    If full_name is empty, falls back to using the VIAF number.
    """
    if not full_name or full_name.strip() == "":
        return f"pers-viaf-{viaf}"
    # Ensure proper spacing.
    fixed_name = fix_name_spacing(full_name)
    tokens = fixed_name.split()
    if len(tokens) >= 2:
        given = tokens[0]
        family = tokens[-1]
    else:
        family = fixed_name
        given = fixed_name[0]
    # Normalize: remove diacritics and non-alphanumerics.
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
        "Accept": "application/rdf+xml",
        "User-Agent": "persNamer/1.0 (verbose mode)"
    }
    try:
        response = requests.get(url, headers=headers, allow_redirects=True)
        response.raise_for_status()
        print("Successfully fetched VIAF RDF data.")
        return response.content
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error while fetching VIAF record: {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Network error while fetching VIAF record: {e}")
        sys.exit(1)

def parse_viaf_rdf(rdf_bytes, viaf):
    """
    Parses the RDF (forcing format='xml') to extract:
      - a preferred name,
      - birth date,
      - death date,
    and collects all unique birth/death dates.
    
    Returns a tuple: (name, birth, death, warning)
    where warning is a string describing multiple date values if found.
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

    VIAF = Namespace("http://viaf.org/ontology/1.1#")
    SCHEMA = Namespace("http://schema.org/")
    MADS = Namespace("http://www.loc.gov/mads/rdf/v1#")
    SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

    name = None
    birth_set = set()
    death_set = set()

    subjects = [
        URIRef(f"http://viaf.org/viaf/{viaf}/"),
        URIRef(f"http://viaf.org/viaf/{viaf}"),
        URIRef(f"https://viaf.org/viaf/{viaf}/"),
        URIRef(f"https://viaf.org/viaf/{viaf}")
    ]

    def extract_from_subject(subj):
        nonlocal name
        for p, o in g.predicate_objects(subj):
            if p in (RDFS.label, SCHEMA.name, VIAF.mainHead, MADS.authoritativeLabel, SKOS.prefLabel):
                if o and str(o).strip():
                    name = str(o).strip()
            elif p in (VIAF.birthDate, SCHEMA.birthDate):
                val = str(o).strip()
                if val:
                    birth_set.add(val)
            elif p in (VIAF.deathDate, SCHEMA.deathDate):
                val = str(o).strip()
                if val:
                    death_set.add(val)

    for subj in subjects:
        extract_from_subject(subj)
        if name or birth_set or death_set:
            break

    birth = sorted(birth_set)[0] if birth_set else None
    death = sorted(death_set)[0] if death_set else None
    # Fix dates (if death date has a day of "00", return only the year).
    def fix_date(date_str):
        m = re.match(r'^(\d{4})-(\d{2})-00$', date_str)
        if m:
            return m.group(1)
        return date_str

    if birth:
        birth = fix_date(birth)
    if death:
        death = fix_date(death)

    warning_parts = []
    if len(birth_set) > 1:
        warning_parts.append("Multiple birth dates: " + "; ".join(sorted(birth_set)))
    if len(death_set) > 1:
        warning_parts.append("Multiple death dates: " + "; ".join(sorted(death_set)))
    warning = " ".join(warning_parts) if warning_parts else None

    # Also, fix the name spacing.
    if name:
        name = fix_name_spacing(name)

    return name, birth, death, warning

def create_person_entry(viaf, name, birth, death, warning_note=None):
    """
    Builds a TEI <person> element:
      <person xml:id="...">
        <persName>name</persName>
        <birth>birth</birth>   (if available)
        <death>death</death>   (if available)
        <idno type="VIAF">viaf</idno>
        <note type="warning">warning_note</note>  (if provided)
      </person>
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

    if warning_note:
        note = etree.SubElement(person, 'note', attrib={'type': 'warning'})
        note.text = warning_note

    print("TEI entry created successfully.")
    return person

def create_annotation_tag(xml_id, name):
    """
    Creates a separate annotation tag for the TEI text.
    The tag is <persName ref="#{xml_id}">name</persName>.
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
    name, birth, death, warning = parse_viaf_rdf(rdf_bytes, viaf)

    print(f"Name found: {name if name else '(none)'}")
    print(f"Birth date found: {birth if birth else '(none)'}")
    print(f"Death date found: {death if death else '(none)'}")
    if warning:
        print(f"Warning: {warning}")
    print("Creating TEI XML entry for the authority file...")

    person_entry = create_person_entry(viaf, name, birth, death, warning)
    xml_id = person_entry.get("{http://www.w3.org/XML/1998/namespace}id")
    annotation_tag = create_annotation_tag(xml_id, name)

    print("\n" * 3)
    print("Final TEI Authority XML entry:")
    authority_xml = etree.tostring(person_entry, pretty_print=True, encoding='unicode')
    print(authority_xml)

    print("\nFinal Annotation tag for TEI text (to be used separately):")
    annotation_xml = etree.tostring(annotation_tag, pretty_print=True, encoding='unicode')
    print(annotation_xml)

if __name__ == '__main__':
    main()
