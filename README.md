# persNamer
[![DOI](https://zenodo.org/badge/933156851.svg)](https://doi.org/10.5281/zenodo.14875030)

**persNamer** is a Python script that retrieves VIAF RDF data for a given VIAF identifier, extracts key personal information (such as the preferred name, birth date, and death date), and generates two TEI XML snippets:

- An **authority file entry** (a `<person>` element with a generated `xml:id`, `<persName>`, `<birth>`, `<death>`, and `<idno type="VIAF">`).
- A separate **annotation tag** for immediate text annotation (a `<persName>` element with a `ref` attribute referencing the authority file entry).

This setup allows you to maintain a centralized authority file and use a ready-made annotation tag in your TEI texts.

## Features

- **Fetch VIAF RDF Data:** Uses HTTP content negotiation to request RDF/XML from VIAF.
- **RDF Parsing:** Utilizes `rdflib` to parse the RDF data and extract:
  - Preferred name (via properties like `rdfs:label`, `schema:name`, `viaf:mainHead`, etc.)
  - Birth date
  - Death date
- **TEI XML Generation:**
  - Creates a `<person>` element with an `xml:id` in the format `pers-[familyname]-[givenname initial]` (e.g., `pers-deteligny-c`).
  - Generates a separate `<persName>` annotation tag with a `ref` attribute pointing to the authority entry.
- **Verbose Output:** The script prints informative messages during processing and separates verbose logs from the final XML output.

## Dependencies

- Python 3.x
- [requests](https://pypi.org/project/requests/)
- [rdflib](https://pypi.org/project/rdflib/)
- [lxml](https://pypi.org/project/lxml/)

## Installation

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/yourusername/persNamer.git
   cd persNamer

2.	Install Dependencies:
It is recommended to use a virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows use: venv\Scripts\activate
    pip install -r requirements.txt
    ```
If you don’t have a requirements.txt, you can install dependencies manually:
    ```bash
    pip install requests rdflib lxml
    ```

## Usage
Run the script by providing a VIAF number as a command-line argument:
    ```bash
    python persNamer.py <VIAF number>
    ```
Example: 
    ```bash
    python persNamer.py 314802260
    ```
Example output:
    ```xml
    Processing VIAF number: 314802260
    Starting to fetch VIAF record (RDF)...
    Fetching data from URL: https://viaf.org/viaf/314802260
    Successfully fetched VIAF RDF data.
    Parsing RDF data with rdflib, forcing format='xml'...
    Name found: Charles deTéligny
    Birth date found: 1535
    Death date found: 1572-08-24
    Creating TEI XML entry for the authority file...
    TEI entry created successfully.
    Final Authority XML entry:
    <person xml:id="pers-deteligny-c">
      <persName>Charles deTéligny</persName>
      <birth>1535</birth>
      <death>1572-08-24</death>
      <idno type="VIAF">314802260</idno>
    </person>
    
    Final Annotation tag for TEI text (to be used separately):
    <persName ref="#pers-deteligny-c">Charles deTéligny</persName>
    ```
    
## Files

- persNamer.py

## License

This project is licensed under the APACHE License. See the LICENSE file for details.

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests for improvements or bug fixes.

## Author

Clément Godbarge
