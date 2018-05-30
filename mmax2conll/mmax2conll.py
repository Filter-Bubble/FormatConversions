#! /usr/bin/env python3

import logging
import os

from lxml import etree

import code.constants as c
from code.util import file_exists

from code.mmax_readers import (
    document_ID_from_filename,
    MMAXWordsDocumentReader,
    MMAXMarkablesDocumentReader,
    CoreaMedWordReader,
)
from code.conll_converters import CorefConverter
from code.conll_writers import CoNLLWriter

logger = logging.getLogger(None if __name__ == '__main__' else __name__)


def find_data_dirs(directory,
                   words_dir=c.WORDS_DIR,
                   markables_dir=c.MARKABLES_DIR):
    """
    Recursively search `directory` for directories containing a `words_dir`
    and `markables_dir` directory as direct children.
    """
    for subdir, subsubdirs, _ in os.walk(directory):
        has_words = words_dir in subsubdirs
        has_markables = markables_dir in subsubdirs
        if has_words and has_markables:
            yield subdir
        elif has_markables:
            logger.warn(
                f"{subdir} has a markables directory ({markables_dir}), but no"
                f" words directory ({words_dir})."
            )
        elif has_words:
            logger.warn(
                f"{subdir} has a words directory ({words_dir}), but no"
                f" markables directory ({markables_dir})."
            )


def super_dir_main(directories, output_dir,
                   words_dir=c.WORDS_DIR,
                   markables_dir=c.MARKABLES_DIR,
                   allow_overwriting=c.ALLOW_OVERWRITING,
                   **kwargs):
    for directory in directories:
        data_dirs = find_data_dirs(
            directory,
            words_dir,
            markables_dir
        )
        for data_dir in data_dirs:
            cur_output_dir = os.path.join(
                output_dir,
                data_dir[len(directory):]
            )
            if not allow_overwriting and os.path.exists(cur_output_dir):
                logger.warn(
                    f"Merging output converted from {data_dir} into"
                    f" {cur_output_dir}"
                )
            else:
                os.makedirs(cur_output_dir, True)
                logger.info(
                    f"Saving data converted from {data_dir} in"
                    f" {cur_output_dir}"
                )

            dir_main(
                input_dir=data_dir,
                output_dir=cur_output_dir,
                words_dir=words_dir,
                markables_dir=markables_dir,
                allow_overwriting=allow_overwriting,
                **kwargs
            )


def dir_main(input_dir, output_dir,
             words_dir=c.WORDS_DIR,
             markables_dir=c.MARKABLES_DIR,
             allow_overwriting=c.ALLOW_OVERWRITING,
             conll_extension=c.CONLL_EXTENSION,
             words_files_extension=c.WORDS_FILES_EXTENSION,
             markables_files_extension=c.MARKABLES_FILES_EXTENSION,
             log_on_error=c.LOG_ON_ERROR,
             **kwargs):
    """
    Batch convert all files in a directory containing a `words_dir` and
    `markables_dir` directory as direct children.
    """
    words_dir = os.path.join(input_dir, words_dir)
    markables_dir = os.path.join(input_dir, markables_dir)

    words_files = {
        filename[:-len(words_files_extension)]
        for filename in os.listdir(words_dir)
        if filename.endswith(words_files_extension)
    }

    markables_files = {
        filename[:-len(markables_files_extension)]
        for filename in os.listdir(markables_dir)
        if filename.endswith(markables_files_extension)
    }

    both = words_files & markables_files

    if words_files - both:
        logger.warn(
            "The following files seem to be words files, but do not have a"
            " corresponding markables file:\n" + '\n'.join(
                words_files - both
            )
        )

    if markables_files - both:
        logger.warn(
            "The following files seem to be markables files, but do not have a"
            " corresponding words file:\n" + '\n'.join(
                markables_files - both
            )
        )

    for name in both:
        words_file = os.path.join(words_dir, name) + words_files_extension
        markables_file = os.path.join(markables_dir, name) + \
            markables_files_extension
        output_file = os.path.join(output_dir, name) + conll_extension
        if os.path.exists(output_file):
            if allow_overwriting:
                logger.warn(f"Overwriting {output_file}")
            else:
                raise IOError(f"Will not overwrite: {output_file}")
        try:
            single_main(words_file, markables_file, output_file, **kwargs)
        except Exception as e:
            if log_on_error:
                logger.error(
                    f"{name} from {input_dir} is skipped: " + e.args[0]
                )
            else:
                e.args = (
                    f"While processing {name} from {input_dir}: " + e.args[0],
                ) + e.args[1:]
                raise e


def single_main(words_file, markables_file, output_file,
                validate_xml=c.VALIDATE_XML,
                auto_use_Med_item_reader=c.AUTO_USE_MED_ITEM_READER,
                warn_on_auto_use_Med_item_reader=c.WARN_ON_AUTO_USE_MED_ITEM_READER,  # noqa
                conll_defaults=c.CONLL_DEFAULTS,
                min_column_spacing=c.MIN_COLUMN_SPACING,
                on_missing=c.CONLL_ON_MISSING,
                markables_filter=c.MMAX_MARKABLES_FILTER):
    # Read in the data from MMAX *_words.xml file
    document_id, sentences = read_words_file(
        filename=words_file,
        reader=MMAXWordsDocumentReader(validate=validate_xml),
        on_missing_document_ID=on_missing['document_id'],
        auto_use_Med_item_reader=auto_use_Med_item_reader,
        warn_on_auto_use_Med_item_reader=warn_on_auto_use_Med_item_reader
    )

    # Read in coreference data
    coref_sets = MMAXMarkablesDocumentReader(
        validate=validate_xml,
        item_filter=markables_filter,
    ).extract_coref_sets(
        etree.parse(markables_file)
    )

    # Merge coref data into sentences (in place)
    CorefConverter.add_data_from_coref_sets(sentences, coref_sets)

    # Save the data to CoNLL
    write_conll(
        filename=output_file,
        writer=CoNLLWriter(
            defaults=conll_defaults,
            min_column_spacing=min_column_spacing,
            on_missing=on_missing
        ),
        document_id=document_id,
        sentences=sentences
    )


def read_words_file(filename, reader,
                    on_missing_document_ID=c.CONLL_ON_MISSING['document_id'],
                    auto_use_Med_item_reader=c.AUTO_USE_MED_ITEM_READER,
                    warn_on_auto_use_Med_item_reader=c.WARN_ON_AUTO_USE_MED_ITEM_READER,  # noqa
                    ):
    """
    Read in word and sentence data and a document ID from a file from COREA.

    First tries to figure out the document ID using the xml and falls back
    on finding a document ID using the file basename.

    See Ch. 7 of Essential Speech and Language Technology for Dutch
    COREA: Coreference Resolution for Extracting Answers for Dutch
    https://link.springer.com/book/10.1007/978-3-642-30910-6
    """
    xml = etree.parse(filename)

    document_id = reader.extract_document_ID(xml)
    if document_id is None:
        document_id = document_ID_from_filename(filename)

    message = f"No document ID could be found for {filename}."
    if on_missing_document_ID == 'warn':
        if document_id is None:
            logger.warn(message)
    elif on_missing_document_ID == 'throw':
        if document_id is None:
            logger.warn(message)
    elif on_missing_document_ID != 'nothing':
        raise ValueError(
                "`on_missing` should be either 'nothing', 'warn' or 'throw',"
                " but `on_missing['document_id']` is"
                f" {on_missing_document_ID!r}"
            )

    logger.debug(f"auto_use_Med_item_reader: {auto_use_Med_item_reader}")
    logger.debug(f"document_id: {document_id}")
    if auto_use_Med_item_reader and document_id.startswith(c.COREA_MED_ID):
        if warn_on_auto_use_Med_item_reader:
            logger.warn(
                "Ignoring reader.item_reader and automatically using the item"
                " reader for COREA Med"
            )
        reader.item_reader = CoreaMedWordReader()

    sentences = reader.extract_sentences(xml)
    return document_id, sentences


def write_conll(filename, writer, document_id, sentences):
    """
    Write sentence data to a file in CoNLL format.
    """
    with open(filename, 'w') as fd:
        writer.write(fd, document_id, sentences)


def can_output_to(output, config, batch):
    if os.path.exists(output):
        if not config['allow_overwriting']:
            thing = "folder" if batch else "file"
            raise ValueError(
                "The configuration specifies overwriting is not allowed, but"
                f" the output {thing} already exists: {output}"
            )
    else:
        # (Check if we can) create it
        if batch:
            os.makedirs(output)
        else:
            open(output, 'w').close()
            # Remove it, because if something goes wrong empty files are more
            # annoying than empty directories
            os.remove(output)


def get_args(args_from_config=[
                'validate_xml',
                'auto_use_Med_item_reader',
                'warn_on_auto_use_Med_item_reader',
                'min_column_spacing',
                'conll_defaults',
                'on_missing',
             ], batch_args_from_config=[
                'allow_overwriting',
                'conll_extension',
                'words_dir',
                'words_files_extension',
                'markables_dir',
                'markables_files_extension',
                'log_on_error',
             ]):
    from argparse import ArgumentParser, RawDescriptionHelpFormatter

    # Read command line arguments
    parser = ArgumentParser(
        description="""
Script to convert coreference data in MMAX format to CoNLL format.

See `CoNLL-specification.md` and `MMAX-specification.md` for extensive
descriptions of the CoNLL and MMAX formats.

To convert a whole directory recursively, run:

    mmax2conll.py <output folder> -d <input folder> [-d <input folder> ...]


To only convert one pair of files, run:

    mmax2conll.py <output.conll> <*_words.xml> <*_coref_level.xml>


When passing folders for batch processing using -d, the passed folders are
searched for a folder containing both a `Basedata` and `Markables` folder. The
output is saved in using the same path relative to the output folder as the
original folder has relative to the passed folder it was found in.

!! NB !! This means that the data of two folders is merged if they happen
         to have the same path relative to passed folders. No files will be
         overwritten if overwriting isn't allowed in the configuration. If
         is allowed according to the configuration, a warning will be issued.

""",
        formatter_class=RawDescriptionHelpFormatter
    )
    parser.add_argument('-l', '--log-level', default='INFO',
                        help="Logging level")
    parser.add_argument('-c', '--config', default=c.DEFAULT_CONFIG_FILE,
                        help="YAML configuration file")
    parser.add_argument('-d', '--directory', action='append',
                        dest='directories',
                        help="Directory to batch convert files from")
    parser.add_argument('output',
                        help="Where to save the CoNLL output")
    parser.add_argument('words_file', type=file_exists, nargs='?',
                        help="MMAX *_words.xml file to use as input")
    parser.add_argument('markables_file', type=file_exists, nargs='?',
                        help="MMAX *_coref_level.xml file to use as input")
    args = vars(parser.parse_args())

    # Set the logging level
    logging.basicConfig(level=args.pop('log_level'))
    logger.debug(f"Args: {args}")

    batch = bool(args['directories'])
    output = args.pop('output')

    # Verify that the command line arguments are legal
    # AND remove the ones not needed
    if batch:
        args['output_dir'] = output
        if args.pop('words_file') is not None or \
           args.pop('markables_file') is not None:
            parser.error(
                "Please either specify a number of directories or the"
                " necessary files to use as input, but not both."
            )
    else:
        del args['directories']
        args['output_file'] = output
        if args['words_file'] is None or args['markables_file'] is None:
            parser.error(
                "Please specify both a *_words.xml file and a"
                " *_coref_level.xml file. You can also choose to specify a"
                " number directories to use as input instead."
            )

    # Read configuration
    config_file = args.pop('config')
    config = read_config(config_file)

    # Read common keys
    args.update(keys_from_config(config, args_from_config, config_file))
    args['markables_filter'] = lambda i: \
        c.MMAX_TYPE_FILTERS[config['markables_type_filter']](i) and \
        c.MMAX_LEVEL_FILTERS[config['markables_level_filter']](i)

    # Read batch keys
    if batch:
        args.update(
            keys_from_config(config, batch_args_from_config, config_file)
        )

    # Verify the output location
    can_output_to(output, config, batch)

    return batch, args


def keys_from_config(config, keys, filename):
    """
    Select some `keys` with their values from a dictionary

    `filename` is only used for the error message if a key is missing
    """
    args = {}
    # Extract required arguments from configuration
    for arg in keys:
        if arg not in config:
            raise ValueError(
                f"The key {arg!r} is not in the specified configuration file"
                f" {filename}"
            )
        args[arg] = config[arg]

    return args


def read_config(filename):
    from pyaml import yaml

    # Read the configuration file
    with open(filename) as config_fd:
        config = yaml.load(config_fd)

    return config


if __name__ == '__main__':
    batch, args = get_args()
    if batch:
        super_dir_main(**args)
    else:
        single_main(**args)
    logger.info("Done!")
