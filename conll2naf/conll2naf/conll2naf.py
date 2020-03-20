import conllu
from KafNafParserPy import KafNafParser
import KafNafParserPy
from xml.sax.saxutils import escape
import os

from .__version__ import __version__


def create_naf(text):
    naf = KafNafParser(type="NAF")
    naf.set_version("3.0")
    naf.set_language("nl")
    naf.lang = "nl"
    naf.raw = text
    naf.set_raw(naf.raw)
    return naf


def create_text_layer(knaf_obj, sentences):
    id_to_tokenid = {}
    wcount = 1
    offsets = {}
    txt = knaf_obj.get_raw()
    for sid, sentence in enumerate(sentences):
        id_to_tokenid[sid+1] = {}
        for token in sentence.tokens:
            token_obj = KafNafParserPy.Cwf(type=knaf_obj.get_type())
            token_id = 'w{}'.format(wcount)
            token_length = len(token['form'])
            offsets[wcount] = txt.find(token['form'], offsets.get(wcount-1, 0))
            token_obj.set_id(token_id)
            token_obj.set_length(str(token_length))
            token_obj.set_para('1')
            token_obj.set_sent(str(sid+1))
            token_obj.set_text(token['form'])
            token_obj.set_offset(str(offsets[wcount]))

            wcount += 1
            id_to_tokenid[sid+1][token['id']] = token_id
            knaf_obj.add_wf(token_obj)
    return id_to_tokenid


def _get_term_type(pos):
    if pos in ['det', 'pron', 'prep', 'vg', 'conj']:
        return 'close'
    else:
        return 'open'


def create_term_layer(knaf_obj, sentences, id_to_tokenid):
    tcount = 0
    term_id_mapping = {}  # Mapping from conll word index -> NAF term id
    for sid, sentence in enumerate(sentences):
        for token in sentence.tokens:
            new_term_id = 't_'+str(tcount)
            term_id_mapping[(sid, token['id'])] = new_term_id
            term_obj = KafNafParserPy.Cterm(type=knaf_obj.get_type())
            term_obj.set_id(new_term_id)

            new_span = KafNafParserPy.Cspan()
            new_span.create_from_ids([id_to_tokenid[sid+1]
                                      [token['id']]])
            term_obj.set_span(new_span)

            term_obj.set_lemma(token['lemma'])

            pos = token['upos'].lower()
            term_obj.set_pos(pos)

            feats = token['xpos'].split('|') # Specific for Dutch??
            feats = feats[0]+'(' + ','.join(feats[1:]) + ')'

            term_obj.set_morphofeat(feats)

            termtype = _get_term_type(pos)
            term_obj.set_type(termtype)
            knaf_obj.add_term(term_obj)

            tcount += 1
    return term_id_mapping


def add_dependencies(knaf_obj, sentences, term_id_mapping):
    for s_id, sent in enumerate(sentences):
        for token in sent.tokens:
            rel = token['deprel']
            parent = str(token['head'])
            # Do not include root
            if rel != 'root' and parent != '0' and parent!= '_':
                # Creating comment
                parent = int(parent)
                parent_lemma = str(sent.tokens[parent-1]['lemma'])
                str_comment = ' '+rel+'('+str(token['lemma'])+','+parent_lemma+') '
                str_comment = escape(str_comment, {"--":"&ndash"})

                my_dep = KafNafParserPy.Cdependency()
                my_dep.set_from(term_id_mapping.get((s_id, parent)))
                my_dep.set_to(term_id_mapping.get((s_id, token['id'])))
                my_dep.set_function(rel)
                my_dep.set_comment(str_comment)
                knaf_obj.add_dependency(my_dep)

def create_lp_object():

    mylp = KafNafParserPy.Clp()
    mylp.set_name("conll2naf")
    mylp.set_version(__version__)
    mylp.set_timestamp()
    return mylp


def create_layer_for_header(header, layer):

    lingproc = KafNafParserPy.ClinguisticProcessors()
    lingproc.set_layer(layer)
    mylp = create_lp_object()
    lingproc.add_linguistic_processor(mylp)

    header.add_linguistic_processors(lingproc)


def set_metadata(nafobj, filename, features):

    nafobj.set_language("nl")
    header = KafNafParserPy.CHeader()
    filedesc = KafNafParserPy.CfileDesc()
    filedesc.set_title(filename)
    header.set_fileDesc(filedesc)

    create_layer_for_header(header, 'raw')
    if 'form' in features:
        create_layer_for_header(header, 'text')
    if 'lemma' in features and 'upos' in features and 'xpos' in features:
        create_layer_for_header(header, 'terms')
    if 'deps' in features:
        create_layer_for_header(header, 'deps')

    #create_layer_for_header(header, 'srl')

    nafobj.set_header(header)


def build_naf(conll_file, features, output_path, one_file_per_sent=False):
    with open(conll_file) as fin:
        sentences = conllu.parse(fin.read(), fields=features)

    docs = {}
    if one_file_per_sent:
        docs = {sent.metadata['sent_id']: [sent] for sent in sentences}
    else:
        fname = os.path.splitext(os.path.basename(conll_file))[0]
        docs = {fname: sentences}

    for doc_id in docs:
        # Create raw layer
        text = '\n'.join([sent.metadata['text'] for sent in docs[doc_id]])
        naf_obj = create_naf(text)

        # Create text layer
        if 'form' in features:
            id_to_tokenid = create_text_layer(naf_obj, docs[doc_id])

        # Create term layer
        if 'lemma' in features and 'upos' in features and 'xpos' in features:
            term_id_mapping = create_term_layer(naf_obj, docs[doc_id], id_to_tokenid)

        # Create deps layer
        if 'deps' in features:
            add_dependencies(naf_obj, docs[doc_id], term_id_mapping)

        # Add header
        set_metadata(naf_obj, doc_id, features)

        # Write NAF file
        naf_obj.dump(os.path.join(output_path, doc_id+'.naf'))
