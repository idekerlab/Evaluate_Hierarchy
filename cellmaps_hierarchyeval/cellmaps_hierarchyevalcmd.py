#! /usr/bin/env python

import os
import argparse
import sys
import logging
import logging.config
from cellmaps_utils import logutils
from cellmaps_utils import constants
import cellmaps_hierarchyeval
from cellmaps_hierarchyeval.runner import CellmapshierarchyevalRunner
from cellmaps_hierarchyeval.analysis import OllamaCommandLineGeneSetAgent
from cellmaps_hierarchyeval.analysis import FakeGeneSetAgent

logger = logging.getLogger(__name__)


HIERARCHYDIR = '--hierarchy_dir'


def _parse_arguments(desc, args):
    """
    Parses command line arguments

    :param desc: description to display on command line
    :type desc: str
    :param args: command line arguments usually :py:func:`sys.argv[1:]`
    :type args: list
    :return: arguments parsed by :py:mod:`argparse`
    :rtype: :py:class:`argparse.Namespace`
    """
    parser = argparse.ArgumentParser(description=desc,
                                     formatter_class=constants.ArgParseFormatter)
    parser.add_argument('outdir', help='Output directory')
    parser.add_argument(HIERARCHYDIR, required=True,
                        help='Directory where hierarchy was generated')
    parser.add_argument('--max_fdr', type=float, default='0.05',
                        help='Maximum false discovery rate')
    parser.add_argument('--min_jaccard_index', type=float, default=0.1,
                        help='Minimum jaccard index')
    parser.add_argument('--min_comp_size', type=int, default=4,
                        help='Minimum term size to consider for enrichment')
    parser.add_argument('--corum', default='764f7471-9b79-11ed-9a1f-005056ae23aa',
                        help='UUID for CORUM network')
    parser.add_argument('--go_cc', default='f484e8ee-0b0f-11ee-aa50-005056ae23aa',
                        help='UUID for GO-CC network')
    parser.add_argument('--hpa', default='a6a88e2d-9c0f-11ed-9a1f-005056ae23aa',
                        help='UUID for HPA network')
    parser.add_argument('--ndex_server', default='http://www.ndexbio.org',
                        help='NDEx server to use')
    parser.add_argument('--ollama_binary', default='/usr/local/bin/ollama',
                        help='Path to ollama binary')
    parser.add_argument('--ollama_prompts', nargs='+',
                        help='Comma delimited value of format <MODEL NAME> or '
                             '<MODEL NAME>,<PROMPT> '
                             'where <PROMPT> can be path to prompt file or prompt to '
                             'run. For insertion of gene set please include {GENE_SET} '
                             'in prompt and tell LLM to put Process: <name> on first line '
                             'with name assigned to assembly and Confidence Score: <score> '
                             'on 2nd line with confidence in the name given. '
                             'If just <MODEL NAME> is set, then default prompt is used with '
                             'model specified. '
                             'NOTE: if <MODEL NAME> is set to FAKE then a completely fake '
                             ' agent will be used')
    parser.add_argument('--name',
                        help='Name of this run, needed for FAIRSCAPE. If '
                             'unset, name value from specified '
                             'by --hierarchy_dir directory will be used')
    parser.add_argument('--organization_name',
                        help='Name of organization running this tool, needed '
                             'for FAIRSCAPE. If unset, organization name specified '
                             'in --hierarchy_dir directory will be used')
    parser.add_argument('--project_name',
                        help='Name of project running this tool, needed for '
                             'FAIRSCAPE. If unset, project name specified '
                             'in --hierarchy_dir directory will be used')
    parser.add_argument('--skip_logging', action='store_true',
                        help='If set, output.log, error.log '
                             'files will not be created')
    parser.add_argument('--logconf', default=None,
                        help='Path to python logging configuration file in '
                             'this format: https://docs.python.org/3/library/'
                             'logging.config.html#logging-config-fileformat '
                             'Setting this overrides -v parameter which uses '
                             ' default logger. (default None)')
    parser.add_argument('--verbose', '-v', action='count', default=1,
                        help='Increases verbosity of logger to standard '
                             'error for log messages in this module. Messages are '
                             'output at these python logging levels '
                             '-v = WARNING, -vv = INFO, '
                             '-vvv = DEBUG, -vvvv = NOTSET (default ERROR '
                             'logging)')
    parser.add_argument('--version', action='version',
                        version=('%(prog)s ' +
                                 cellmaps_hierarchyeval.__version__))

    return parser.parse_args(args)


def get_ollama_geneset_agents(ollama_binary=None, ollama_prompts=None):
    """
    Parses **ollama_prompts** from argparse and creates geneset agents

    :param ollama_binary: Path to ollama binary
    :type ollama_binary: str
    :param ollama_prompts:
    :type ollama_prompts: list
    :return:
    """
    if ollama_prompts is None:
        return None

    res = []
    for o_prompt in ollama_prompts:
        if ',' not in o_prompt:
            if o_prompt.lower() == 'fake':
                agent = FakeGeneSetAgent()
            else:
                agent = OllamaCommandLineGeneSetAgent(ollama_binary=ollama_binary,
                                                      model=o_prompt)
            res.append(agent)
            continue

        split_prompt = o_prompt.split(',')
        model = split_prompt[0]
        if model == 'FAKE':
            logger.debug('Creating FAKE geneset agent')
            res.append(FakeGeneSetAgent())
            continue

        raw_prompt = split_prompt[1]
        if os.path.isfile(prompt):
            with open(prompt, 'r') as f:
                prompt = f.read()
        else:
            prompt = raw_prompt
        logger.debug('Creating ollama geneset agent for model: ' + str(model))
        agent = OllamaCommandLineGeneSetAgent(ollama_binary=ollama_binary,
                                              model=model, prompt=prompt)
        res.append(agent)
    return res


def main(args):
    """
    Main entry point for program

    :param args: arguments passed to command line usually :py:func:`sys.argv[1:]`
    :type args: list

    :return: return value of :py:meth:`cellmaps_hierarchyeval.runner.CellmapshierarchyevalRunner.run`
             or ``2`` if an exception is raised
    :rtype: int
    """
    desc = """
    Version {version}
    Takes a HiDeF {hierarchy_file} file from {hierarchy_dir} and runs enrichment tests for GO, CORUM, and HPA terms.

    """.format(version=cellmaps_hierarchyeval.__version__,
               hierarchy_file=constants.HIERARCHY_NETWORK_PREFIX,
               hierarchy_dir=HIERARCHYDIR)

    theargs = _parse_arguments(desc, args[1:])
    theargs.program = args[0]
    theargs.version = cellmaps_hierarchyeval.__version__
    try:
        logutils.setup_cmd_logging(theargs)

        ollama_prompts = get_ollama_geneset_agents(ollama_binary=theargs.ollama_binary,
                                                   ollama_prompts=theargs.ollama_prompts)

        return CellmapshierarchyevalRunner(outdir=theargs.outdir,
                                           max_fdr=theargs.max_fdr,
                                           min_jaccard_index=theargs.min_jaccard_index,
                                           min_comp_size=theargs.min_comp_size,
                                           corum=theargs.corum,
                                           go_cc=theargs.go_cc,
                                           hpa=theargs.hpa,
                                           ndex_server=theargs.ndex_server,
                                           geneset_agents=ollama_prompts,
                                           name=theargs.name,
                                           organization_name=theargs.organization_name,
                                           project_name=theargs.project_name,
                                           hierarchy_dir=theargs.hierarchy_dir,
                                           skip_logging=theargs.skip_logging,
                                           input_data_dict=theargs.__dict__).run()
    except Exception as e:
        logger.exception('Caught exception: ' + str(e))
        return 2
    finally:
        logging.shutdown()


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main(sys.argv))
