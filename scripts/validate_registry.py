#!/usr/bin/env python3
"""Validate the registry snapshot with the Python standard library."""

import csv
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_csv(filename):
    path = ROOT / 'data' / filename
    with path.open(encoding='utf-8-sig', newline='') as handle:
        matrix = list(csv.reader(handle))
    require(len(matrix) > 1, f'{filename}: no data records')
    require(len(matrix[0]) == len(set(matrix[0])), f'{filename}: duplicate header')
    for index, row in enumerate(matrix[1:], start=2):
        require(len(row) == len(matrix[0]), f'{filename}:{index}: incorrect field count')
        require(all(value.strip() for value in row), f'{filename}:{index}: blank field')
    return matrix


def unique_ids(matrix, column, label):
    identifiers = [row[column] for row in matrix[1:]]
    require(len(identifiers) == len(set(identifiers)), f'{label}: duplicate ID')
    return set(identifiers)


def validate_references(matrix, column, valid, label):
    for index, row in enumerate(matrix[1:], start=2):
        references = [value.strip() for value in row[column].split(',')]
        require(set(references) <= valid, f'{label}:{index}: unknown references {set(references) - valid}')


def column_index(reference):
    value = 0
    for character in reference:
        if character.isalpha():
            value = value * 26 + ord(character) - ord('A') + 1
    return value - 1


def workbook_values(path):
    matrices = {}
    with zipfile.ZipFile(path) as archive:
        require(archive.testzip() is None, 'Workbook contains a damaged ZIP member')
        shared = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            shared_root = ET.fromstring(archive.read('xl/sharedStrings.xml'))
            shared = [''.join(t.text or '' for t in item.findall('.//s:t', NS))
                      for item in shared_root.findall('s:si', NS)]
        relationships = {
            item.attrib['Id']: item.attrib['Target']
            for item in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        }
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        for sheet in workbook.findall('s:sheets/s:sheet', NS):
            relationship = sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
            target = relationships[relationship]
            member = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            sheet_root = ET.fromstring(archive.read(member))
            rows = []
            for source_row in sheet_root.findall('s:sheetData/s:row', NS):
                row = []
                for cell in source_row.findall('s:c', NS):
                    index = column_index(cell.attrib['r'])
                    while len(row) <= index:
                        row.append('')
                    kind = cell.attrib.get('t')
                    require(kind != 'e', f'{sheet.attrib["name"]}:{cell.attrib["r"]}: Excel error')
                    value = cell.find('s:v', NS)
                    if kind == 's':
                        text = shared[int(value.text)]
                    elif kind == 'inlineStr':
                        text = ''.join(item.text or '' for item in cell.findall('.//s:t', NS))
                    else:
                        text = '' if value is None else value.text or ''
                    row[index] = text
                rows.append(row)
            matrices[sheet.attrib['name']] = rows
    return matrices


def validate_markdown_links():
    for path in list(ROOT.glob('*.md'))+list((ROOT/'docs').rglob('*.md')):
        text = path.read_text(encoding='utf-8')
        for target in re.findall(r'\[[^\]]*\]\(([^\s)]+)\)', text):
            if target.startswith(('https://', 'http://', 'mailto:', '#')):
                continue
            target = target.split('#', 1)[0].split('?', 1)[0]
            require((path.parent / target).exists(), f'{path.relative_to(ROOT)}: missing link target {target}')


def main():
    metadata = json.loads((ROOT / 'metadata' / 'registry.json').read_text(encoding='utf-8'))
    tables = {
        'features': read_csv('english_linguistic_feature_registry.csv'),
        'specifications': read_csv('paper_measure_specifications.csv'),
        'resources': read_csv('external_resource_selection.csv'),
        'sources': read_csv('sources.csv'),
        'guidance': read_csv('modeling_guidance.csv'),
    }
    features = unique_ids(tables['features'], 0, 'features')
    unique_ids(tables['specifications'], 0, 'specifications')
    unique_ids(tables['resources'], 0, 'resources')
    sources = unique_ids(tables['sources'], 0, 'sources')
    validate_references(tables['features'], 10, sources, 'features/source')
    validate_references(tables['specifications'], 1, features, 'specifications/feature')
    validate_references(tables['specifications'], 15, sources, 'specifications/source')
    validate_references(tables['resources'], 3, features, 'resources/feature')
    validate_references(tables['resources'], 11, sources, 'resources/source')
    counts = {
        'features': len(features),
        'categories': len({row[1] for row in tables['features'][1:]}),
        'sources': len(sources),
        'paper_operationalizations': len(tables['specifications']) - 1,
        'resource_decisions': len(tables['resources']) - 1,
        'guidance_rows': len(tables['guidance']) - 1,
    }
    require(counts == metadata['counts'], 'Metadata counts differ from CSV counts')
    category_counts = {}
    for row in tables['features'][1:]:
        category_counts[row[1]] = category_counts.get(row[1], 0) + 1
    require(category_counts == metadata['category_counts'], 'Category counts differ from metadata')
    sheets = workbook_values(ROOT / 'downloads' / 'english_linguistic_feature_registry_20261014.xlsx')
    mapping = {'指标目录': 'features', '论文指标细节': 'specifications', '资源选型': 'resources',
               '工具与来源': 'sources', '使用与建模': 'guidance'}
    require(set(sheets) == set(mapping), 'Unexpected workbook worksheets')
    for sheet, key in mapping.items():
        require(sheets[sheet] == tables[key], f'{sheet}: Excel and CSV contents differ')
    for item in metadata['files']:
        path = ROOT / item['path']
        require(path.is_file(), f'Missing release file {item["path"]}')
        content = path.read_bytes()
        require(len(content) == item['bytes'], f'Size differs: {item["path"]}')
        require(hashlib.sha256(content).hexdigest() == item['sha256'], f'Hash differs: {item["path"]}')
    validate_markdown_links()
    print(json.dumps({'status': 'passed', 'counts': counts, 'workbook_matches_csv': True,
                      'file_hashes_verified': len(metadata['files']), 'relative_links_verified': True},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, ET.ParseError, zipfile.BadZipFile) as error:
        print(f'Validation failed: {error}', file=sys.stderr)
        sys.exit(1)
