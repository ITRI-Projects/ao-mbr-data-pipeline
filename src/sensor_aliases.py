"""Read sensor aliases from the workbook used by import and cleaning."""

from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from src.database import identifier

WORKBOOK = Path(__file__).resolve().parents[1] / 'Sensor_Configurations.xlsx'


def read_aliases(workbook=WORKBOOK):
    ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    mapping = {}
    with ZipFile(workbook) as archive:
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(t.text or '' for t in item.findall('.//m:t', ns))
                       for item in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('m:si', ns)]
        for name in archive.namelist():
            if not re.fullmatch(r'xl/worksheets/sheet\d+\.xml', name):
                continue
            columns = None
            for row in ET.fromstring(archive.read(name)).findall('.//m:row', ns):
                values = {}
                for cell in row:
                    column = re.sub(r'\d+', '', cell.attrib['r'])
                    v = cell.find('m:v', ns)
                    if cell.attrib.get('t') == 's':
                        text = strings[int(v.text)]
                    elif cell.attrib.get('t') == 'inlineStr':
                        text = ''.join(t.text or '' for t in cell.findall('.//m:t', ns))
                    else:
                        text = v.text if v is not None else ''
                    values[column] = text.strip()
                normalized = {v.lower(): k for k, v in values.items() if v}
                if 'full tag name' in normalized:
                    alias_key = normalized.get('prefered alias') or normalized.get('preferred alias')
                    if not alias_key or 'column' not in normalized:
                        raise ValueError('Workbook requires Preferred Alias and Column headers')
                    columns = (normalized['full tag name'], alias_key, normalized['column'])
                    continue
                if columns:
                    tag, alias, source = (values.get(k, '') for k in columns)
                    if tag:
                        alias = alias or source
                        identifier(alias)
                        if tag in mapping and mapping[tag] != alias:
                            raise ValueError(f'Conflicting workbook mapping for {tag}')
                        mapping[tag] = alias
    if not mapping or len(set(a.lower() for a in mapping.values())) != len(mapping):
        raise ValueError('Workbook has missing or duplicate aliases')
    return mapping
