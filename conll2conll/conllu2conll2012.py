import re
import argparse
import sys

REGEX_NEWDOC = r'# newdoc id = (.*)'
REGEX_SENT = r'# sent_id = .*\.p\.([0-9]+)\.s\.[0-9]+'

def convert_file(fname_in, output_file, split_parts):
    lines = ''
    doc_name = ''
    part = 0
    with open(fname_in) as fin:
        for line in fin.readlines():
            begin_doc_match = re.match(REGEX_NEWDOC, line)
            sent_match = re.match(REGEX_SENT, line)
            if begin_doc_match:
                if len(lines)>0:
                    output_file.write(lines)
                    output_file.write('#end document\n\n')
                    lines = ''
                    part = 0
                doc_name = begin_doc_match.groups()[0]
                if split_parts:
                    output_file.write('#begin document ({}); part {}\n'.format(doc_name, part))
                else:
                    output_file.write('#begin document ({});\n'.format(doc_name))
            elif sent_match and split_parts:
                new_part = int(sent_match.group(1))
                if new_part != part and len(lines) > 0:
                    output_file.write(lines)
                    output_file.write('#end document\n\n')
                    part = new_part
                    lines = ''
                    if split_parts:
                        output_file.write('#begin document ({}); part {}\n'.format(doc_name, part))
                    else:
                        output_file.write('#begin document ({});\n'.format(doc_name))
            elif line.startswith('#'):
                continue
            elif line == '\n':
                lines += line
            elif len(line.split())>1:
                fields = line.split()
                coref_field = fields[-1]
                coref_field_list = [s for s in coref_field.split('|') if re.match(r'\(?[0-9]+\)?$', s)]
                coref_field = '|'.join(coref_field_list) if len(coref_field_list)>0 else '-'
                lines += '\t'.join([doc_name, fields[0], fields[1], coref_field]) + '\n'
            else:
                print(line)
        if len(lines)>0:
            output_file.write(lines)
            output_file.write('#end document\n')


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_filename')
    parser.add_argument('-o', '--output_file',
                        type=argparse.FileType('w'), default=sys.stdin)
    parser.add_argument('--split_parts')
    return parser

if __name__ == "__main__":
    args = get_parser().parse_args()
    convert_file(args.input_filename, args.output_file, args.split_parts)
