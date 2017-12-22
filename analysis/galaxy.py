"""Galaxy driver code, workflow definitions etc should probably live
somewhere else"""
import json
import os
from time import sleep

from kantele import settings


collection_names = ['spectra']

# should make this obsolete, only define in workflow
flatfile_names = ['target db',
                  'decoy db',
                  'knownpep predpi tabular',
                  'pipeptides db',
                  'pipeptides known db',
                  'knownpep db',
                  'knownpep db decoy',
                  'knownpep tryp lookup',
                  'knownpep allpep lookup',
                  'biomart map',
                  'spectra lookup',
                  'quant lookup',
                  'psm lookup target',
                  'psm lookup decoy',
                  'psm table target',
                  'psm table decoy',
                  'psm table normalsearch',
                  ]


def initialize_run(analysis, mzmls):
    """Fills run with empty dict of datasets which are to be
    made by Galaxy"""
    run = {'apikey': analysis.account.apikey,
           'params': json.loads(analysis.params)}
    inputs = {name: {'src': 'hda', 'id': None} for name in flatfile_names}
    inputs.update({name: {'src': 'hdca', 'id': None} for name in
                   collection_names})
    run['datasets'] = inputs
    run['raw'] = mzmls
    return run


def get_msgf_inputs(params):
    inputs = {'common_variable_modifications': [],
              'common_fixed_modifications': []}
    if 'multiplextype' not in params and 'phospho' not in params:
        protocol = '0'
    elif 'multiplextype' not in params and 'phospho' in params:
        protocol = '1'
    elif params['multiplextype'] in ['tmt10plex', 'tmt6plex']:
        protocol = '4'
        inputs['common_fixed_modifications'] = [
            '229.162932_*_fix_N-term_TMT6plex',
            '229.162932_K_fix_any_TMT6plex']
    elif params['multiplextype'][:5] == 'itraq' and 'phospho' not in params:
        protocol = '2'
        inputs['common_fixed_modifications'] = [
            '304.205360_K_fix_any_iTRAQ8plex',
            '304.205360_*_fix_N-term_iTRAQ8plex',
        ]
    elif params['multiplextype'][:5] == 'itraq' and params['phospho']:
        protocol = '3'
    inputs['advanced|protocol'] = protocol
    if params['instrument'] == 'qe':
        inputs['inst'] = '3'
    elif params['instrument'] == 'velos':
        inputs['inst'] = '1'
    else:
        raise RuntimeError('Only pass qe or velos to --instrument')
    if 'custommods' in params:
        mods = []
        for mod in params['custommods']:
            mod = mod.split('_')
            mods.append({'mass': mod[0], 'aa': list(mod[1]), 'fo': mod[2],
                         'pos': mod[3], 'name': mod[4]})
        params['custommods'] = mods
    modificationmap = {'carba': 'C2H3N1O1_C_fix_any_Carbamidomethyl',
                       'ox': 'O1_M_opt_any_Oxidation'}
    for inmod in params['modifications']:
        try:
            mod = modificationmap[inmod]
        except KeyError:
            raise RuntimeError('Only pass modifications {} or update this code'
                               ''.format(', '.join(modificationmap.keys())))
        modtype = mod.split('_')[2]
        if modtype == 'fix':
            inputs['common_fixed_modifications'].append(mod)
        elif modtype == 'opt':
            inputs['common_variable_modifications'].append(mod)
    return inputs


def finalize_galaxy_workflow(raw_json, modtype, run, timestamp, gi, searchtype,
                             specquant_wfjson=False):
    # FIXME
    if specquant_wfjson:
        connect_specquant_workflow(specquant_wfjson, raw_json)
    wf_json = add_repeats_to_workflow_json(run, raw_json)
    if run['params']['fr_matcher'] is None:
        remove_ipg_steps(wf_json)
    if searchtype == 'standard':
        remove_post_peptide_steps(run, wf_json, modtype)
    if run['params']['multiplextype'] is None:
        if searchtype == 'standard':
            remove_isobaric_from_protein_centric(wf_json)
        elif searchtype in ['vardb', '6rf']:
            # FIXME the remove_iso_peptide is untested, wait for labelfree
            # vardb/6rf or labelfree peptide only
            remove_isobaric_vardb6rf(wf_json, searchtype)
    return runtime_and_upload(wf_json, run, gi)


def subtract_column_xsetfdr(wf_json, amount_cols):
    for step in wf_json['steps'].values():
        if (get_stepname_or_annotation(step) == 'X-set protein table' and
                step['label'] == 'Remove quant columns'):
            state_dic = json.loads(step['tool_state'])
            clist = json.loads(state_dic['columnList']).split('-')
            lastcol = int(clist[1][1:]) - amount_cols
            newclist = '{}-c{}'.format(clist[0], lastcol)
            change_lvlone_toolstate(step, 'columnList', newclist)
    for step in wf_json['steps'].values():
        if (get_stepname_or_annotation(step) == 'X-set protein table' and
                'Compute False Discovery Rate' in step['name']):
            change_lvltwo_toolstate(step, 'decoy', 'decoy_column',
                                    str(lastcol + 1))
            change_lvltwo_toolstate(step, 'score', 'score_column',
                                    str(lastcol - 5))
        elif step['label'] in ['xset target labeler', 'xset decoy labeler']:
            change_lvlone_toolstate(step, 'column', lastcol + 1)


def remove_post_peptide_steps(inputstore, wf_json, modtype):
    if inputstore['wf']['dbtype'] == 'ensembl':
        return
    else:
        remove_biomart_symbol_steps(wf_json)
    if modtype == 'proteingenessymbols':
        return
    else:
        remove_annotated_steps(wf_json, 'symbol table')
    if modtype == 'proteingenes':
        # e.g. uniprot still has columns for symbol but NA
        return
    else:
        remove_gene_steps(wf_json)
        # subtract 3 columns since proteincentric (no fasta parsing/biomart)
        # columns: description, symbol, gene
        subtract_column_xsetfdr(wf_json, 3)
    if modtype == 'proteins':
        return
    else:
        remove_protein_steps(wf_json)
    # FIXME proteincentric peptide searches need a proteingroup though.


def remove_ipg_steps(wfjson):
    print('Adjusting for non-IPG data')
    # remove unneccesary steps
    remove_annotated_steps(wfjson, 'IPG-deltapi')
    remove_annotated_steps(wfjson, 'Get fraction numbers')
    step_tool_states = get_step_tool_states(wfjson)
    knownpep_step = get_input_dset_step_id_for_name(step_tool_states,
                                                    'knownpep predpi tabular')
    remove_step_from_wf(knownpep_step, wfjson)
    # make process psm table target have an out:psm table target
    for step in wfjson['steps'].values():
        if (get_stepname_or_annotation(step) == 'Process PSM table' and
                'decoy' not in str(step['label'])):
            break
    pja = {'RenameDatasetActionoutput': {'action_arguments': {
        'newname': 'out: psm table target.txt'}, 'action_type':
        'RenameDatasetAction', 'output_name': 'output'}}
    step['post_job_actions'].update(pja)
    psm_table_stepid = step['id']
    # connect that with split tabular (annot: split psm target)
    for step in wfjson['steps'].values():
        name_anno = get_stepname_or_annotation(step)
        if name_anno == 'split psm target':
            step['input_connections']['input'] = {'id': psm_table_stepid,
                                                  'output_name': 'output'}
        elif name_anno == 'msstitch QC':
            step['input_connections']['psmtable'] = {'id': psm_table_stepid,
                                                     'output_name': 'output'}


def get_workflow_params(wf_json):
    """Should return step tool_id, name, composed_name"""
    for step in wf_json['steps'].values():
        try:
            tool_param_inputs = step['tool_inputs'].items()
        except AttributeError:
            continue
        dset_input_names = [x['name'] for x in step['inputs']]
        for input_name, input_val in tool_param_inputs:
            if input_name in dset_input_names:
                continue
            try:
                input_val = json.loads(input_val)
            except ValueError:
                # no json obj, no runtime values
                continue
            if type(input_val) == dict:
                if dict in [type(x) for x in input_val.values()]:
                    # complex input with repeats/conditional
                    for subname, subval in input_val.items():
                        composed_name = '{}|{}'.format(input_name, subname)
                        if is_runtime_param(subval, composed_name, step):
                            yield {'tool_id': step['tool_id'],
                                   'name': composed_name,
                                   'storename': input_name}
                else:
                    # simple runtime value check and fill with inputstore value
                    if is_runtime_param(input_val, input_name, step):
                        yield {'tool_id': step['tool_id'],
                               'name': input_name, 'storename': False}


def add_repeats_to_workflow_json(inputstore, wf_json):
    """Takes as input wf_json the thing the output from
    gi.workflows.export_workflow_json"""
    print('Updating set names and other repeats')
    params = inputstore['params']
    has_strips = False
    if params['strippatterns'] is not None:
        has_strips = True
        strip_list_splitdb = json.dumps([
            {'__index__': ix, 'intercept': strip['intercept'],
             'fr_width': strip['fr_width'], 'peptable_pattern': strippat,
             'tolerance': strip['pi_tolerance'],
             'fr_amount': strip['fr_amount'], 'reverse': strip['reverse'],
             'picutoff': 0.2}
            for ix, (strip, strippat) in enumerate(
                zip(params['strips'], params['strippatterns']))])
        strip_list = json.dumps([{'__index__': ix,
                                  'intercept': strip['intercept'],
                                  'fr_width': strip['fr_width'],
                                  'pattern': strippat}
                                 for ix, (strip, strippat) in
                                 enumerate(zip(params['strips'],
                                               params['strippatterns']))])
    ppool_list = json.dumps([{'__index__': ix, 'pool_identifier': name}
                             for ix, name in enumerate(params['perco_ids'])])
    set_list = json.dumps([{'__index__': ix, 'pool_identifier': name}
                           for ix, name in enumerate(params['setpatterns'])])
    lookup_list = json.dumps([{'__index__': ix, 'set_identifier': setid,
                               'set_name': setname} for ix, (setid, setname) in
                              enumerate(zip(params['setpatterns'],
                                            params['setnames']))])
    if params['fdrclasses'] is not None:
        print('Adding FDR classes to workflow')
        fdrclass_set_list = json.dumps([{'__index__': ix, 'pool_identifier':
                                         name} for ix, name in
                                        enumerate(params['setfdrclasses'])])
        fdrclass_list = [{'__index__': ix, 'pattern': pat} for ix, pat in
                         enumerate(params['fdrclasses'])]
        decoy_fdrclass_list = [{'__index__': ix, 'pattern': pat} for ix, pat in
                               enumerate(params['decoy_fdrclasses'])]
    if params['multiplextype'] is not None:
        print('Making denomlist')
        denom_list = [{'__index__': ix, 'setpattern': sd['setpattern'],
                       'denompatterns': sd['denoms']} for ix, sd in
                      enumerate(params['setdenominators'])]
    percin_input_stepids = set()
    # Add setnames to repeats, pi strips to delta-pi-calc
    for step in wf_json['steps'].values():
        name_annot = get_stepname_or_annotation(step)
        state_dic = json.loads(step['tool_state'])
        if step['tool_id'] is None:
            continue
        elif 'batched_set' in step['tool_id']:
            if 'RuntimeValue' in state_dic['batchsize']:
                # also find decoy perco-in batch ID
                percin_input_stepids.add(step['id'])
                state_dic['poolids'] = ppool_list
            elif 'varDB nest' in get_stepname_or_annotation(step):
                state_dic['poolids'] = fdrclass_set_list
            else:
                state_dic['poolids'] = set_list
        elif 'msslookup_spectra' in step['tool_id']:
            state_dic['pools'] = lookup_list
        elif (('create_protein_table' in step['tool_id'] or
                'create_peptide_table' in step['tool_id']) and
              params['multiplextype'] is not None and
              json.loads(state_dic['isoquant'])['yesno'] == 'true'):
            iq = json.loads(state_dic['isoquant'])
            iq['setdenoms'] = denom_list
            state_dic['isoquant'] = json.dumps(iq)
            step['tool_state'] = json.dumps(state_dic)
        elif 'calc_delta_pi' in step['tool_id'] and has_strips:
            state_dic['strips'] = strip_list
        elif 'pi_db_split' in step['tool_id'] and has_strips:
            state_dic['strips'] = strip_list_splitdb
        elif 'varDB class splitter' in name_annot:
            sp = json.loads(state_dic['splitter'])
            if 'decoy' in name_annot:
                sp['headers'] = decoy_fdrclass_list
            else:
                sp['headers'] = fdrclass_list
            state_dic['splitter'] = json.dumps(sp)
            step['tool_state'] = json.dumps(state_dic)
        elif 'MS-GF+' in name_annot and params['custommods']:
            custommods = json.dumps([
                {'__index__': ix, 'formula_or_mass': mod['mass'],
                 'aa_specificity': mod['aa'], 'fix_or_opt': mod['fo'],
                 'position_specificity': mod['pos'], 'mod_name': mod['name']}
                for ix, mod in enumerate(params['custommods'])])
            state_dic['custom_mods'] = custommods
            print(state_dic)
        step['tool_state'] = json.dumps(state_dic)

    return connect_percolator_in_steps(wf_json, percin_input_stepids)


def connect_percolator_in_steps(wf_json, percin_input_stepids):
    print('Connecting loose step (percolator-in)...')
    # connect percolator in step
    for step in wf_json['steps'].values():
        if (step['tool_id'] is not None and
                'percolator_input_converters' in step['tool_id']):
            step_input = step['input_connections']
            percin_input_stepids.remove(step_input['mzids|target']['id'])
            step_input['mzids|decoy'] = {
                'output_name': 'batched_fractions_mzid',
                'id': percin_input_stepids.pop()}
    return wf_json


def fill_runtime_params(step, params):
    """Should return step tool_id, name, composed_name"""
    tool_param_inputs = json.loads(step['tool_state'])
    # Use annotation to define step name in case that is given, to be able
    # to get steps like sed which have a very general name and may occur more
    # than once
    stepname = get_stepname_or_annotation(step)
    dset_input_names = [x['name'] for x in step['inputs'] if not
                        x['description'].startswith('runtime parameter')]
    for input_name, input_val in tool_param_inputs.items():
        if input_name in dset_input_names:
            continue
        try:
            input_val = json.loads(input_val)
        except (TypeError, ValueError):
            # no json obj, no runtime values
            continue
        if type(input_val) == dict:
            # Only runtime vals or conditionals are dict, simple values
            # are just strings
            if dict in [type(x) for x in input_val.values()]:
                # complex input dict from e.g. conditional which contains
                # a dict possibly containing runtime value
                # TODO make this recursive maybe for nested conditionals
                for subname, subval in input_val.items():
                    composed_name = '{}|{}'.format(input_name, subname)
                    if is_runtime_param(subval, composed_name, step):
                        try:
                            input_val[subname] = params[stepname][composed_name]
                        except:
                            print('WARNING, RuntimeValue for tool {}, param '
                                  '{} expected, but nothing passed (possibly '
                                  'is an unneeded dataset '
                                  'though).'.format(stepname, composed_name))
                tool_param_inputs[input_name] = json.dumps(input_val)
            else:
                if is_runtime_param(input_val, input_name, step):
                    try:
                        tool_param_inputs[input_name] = json.dumps(
                            params[stepname][input_name])
                    except:
                        print('WARNING, RuntimeValue for tool {}, param {} '
                              'expected, but nothing passed (possibly is an '
                              'unneeded dataset though).'.format(stepname,
                                                                 input_name))
    step['tool_state'] = json.dumps(tool_param_inputs)


def get_spectraquant_wf(inputstore):
    # FIXME cannot open a file!
    if 'IsobaricAnalyzer' in inputstore['params']:
        wf_fn = 'json_workflows/spectra_quant_isobaric_v0.2.json'
    else:
        wf_fn = 'json_workflows/spectra_quant_labelfree_v0.2.json'
    with open(wf_fn) as fp:
        return json.load(fp)


def get_step_tool_states(wf_json):
    return {step['id']: json.loads(step['tool_state'])
            for step in wf_json['steps'].values()}


def get_input_dset_step_id_for_name(tool_states, name):
    return [step_id for step_id, ts in tool_states.items()
            if 'name' in ts and ts['name'] == name][0]


def connect_specquant_workflow(spec_wf_json, search_wf_json):
    print('Connecting spectra quant workflow to search workflow')
    step_tool_states = get_step_tool_states(search_wf_json)
    # first remove quant lookup input
    qlookup_step_id = get_input_dset_step_id_for_name(step_tool_states,
                                                      'quant lookup')
    remove_step_from_wf(qlookup_step_id, search_wf_json)
    # to make space for spec quant, change ID on all steps, and all connections
    for step in search_wf_json['steps'].values():
        if get_stepname_or_annotation(step) == 'reformatted spectra':
            first_post_spec = step['id'] + 1
            break
    if first_post_spec > qlookup_step_id:
        first_post_spec -= 1
    amount_spec_steps = len([step for step in spec_wf_json['steps'].values()
                             if step['tool_id'] is not None])
    newsteps = {}
    for step in search_wf_json['steps'].values():
        if step['id'] >= first_post_spec:
            step['id'] = step['id'] + amount_spec_steps
            for connection in step['input_connections'].values():
                if type(connection) == list:
                    for multi_connection in connection:
                        if multi_connection['id'] >= first_post_spec:
                            multi_connection['id'] = (multi_connection['id'] +
                                                      amount_spec_steps)
                elif connection['id'] >= first_post_spec:
                    connection['id'] = connection['id'] + amount_spec_steps
        newsteps[str(step['id'])] = step
    search_wf_json['steps'] = newsteps
    # Subtract 1 because we have removed an input step (quant lookup)
    for step in search_wf_json['steps'].values():
        if get_stepname_or_annotation(step) == 'reformatted spectra':
            spec_step_id = step['id']
            break
    # Add spectra/quant steps, connect to spectra collection input
    for step in spec_wf_json['steps'].values():
        if step['tool_id'] is None:
            continue
        step['id'] = step['id'] - 1 + first_post_spec
        for connection in step['input_connections'].values():
            connection['id'] = connection['id'] - 1 + first_post_spec
        if 'spectra' in step['input_connections']:
            step['input_connections']['spectra']['id'] = spec_step_id
        elif 'ms1_in' in step['input_connections']:
            step['input_connections']['ms1_in']['id'] = spec_step_id
        elif 'param_in' in step['input_connections']:
            step['input_connections']['param_in']['id'] = spec_step_id
        search_wf_json['steps'][str(step['id'])] = step
        if step['name'] == 'Create lookup table with quant data':
            lookupstep = step
    # Connect to PSM table and QC
    for step in search_wf_json['steps'].values():
        if step['name'] == 'Process PSM table':
            step['input_connections']['lookup']['id'] = lookupstep['id']
        elif step['name'] == 'msstitch QC':
            step['input_connections']['lookup']['id'] = lookupstep['id']


def get_stepname_or_annotation(step):
    annot = step['annotation']
    return annot[:annot.index('---')] if annot else step['name']


def remove_annotated_steps(wf_json, annot_or_name):
    stepfound = True
    while stepfound:
        stepfound = False
        for step in wf_json['steps'].values():
            stepname = get_stepname_or_annotation(step)
            if annot_or_name in stepname:
                remove_step_from_wf(step['id'], wf_json,
                                    remove_connections=True)
                stepfound = True
                break


def change_lvlone_toolstate(step, option, value):
    ts = json.loads(step['tool_state'])
    ts[option] = json.dumps(value)
    step['tool_state'] = json.dumps(ts)


def change_lvltwo_toolstate(step, levelone_key, subkey, value):
    ts = json.loads(step['tool_state'])
    sub_ts = json.loads(ts[levelone_key])
    sub_ts[subkey] = value
    ts[levelone_key] = json.dumps(sub_ts)
    step['tool_state'] = json.dumps(ts)


def set_level_one_option(wf_json, stepname, option, value):
    for step in wf_json['steps'].values():
        if step['name'] == stepname:
            change_lvlone_toolstate(step, option, value)


def set_level_two_option(wf_json, stepname, levelone_key, subkey, value):
    for step in wf_json['steps'].values():
        if step['name'] == stepname:
            change_lvltwo_toolstate(step, levelone_key, subkey, value)


def remove_protein_steps(wf_json):
    print('Removing proteingrouping, proteincentric steps and inputs '
          'from workflow')
    remove_annotated_steps(wf_json, 'protein table')
    # Remove proteingrouping too
    set_level_one_option(wf_json, 'Process PSM table', 'proteingroup', 'false')
    set_level_two_option(wf_json, 'Merge peptide or protein tables',
                         'quants', 'centric', 'plain')
    # Protein column for normalizing protein table is not master protein
    set_level_one_option(wf_json, 'Create protein table', 'accessioncol', '12')


def remove_gene_steps(wf_json):
    print('Removing Genecentric steps, options and inputs from workflow')
    remove_annotated_steps(wf_json, 'gene table')
    set_level_one_option(wf_json, 'Process PSM table', 'genes', 'false')


def remove_biomart_symbol_steps(wf_json):
    print('Removing ENSEMBL steps and inputs from workflow')
    # remove biomart from PSM table input connections
    for step in wf_json['steps'].values():
        if step['name'] == 'Process PSM table':
            del(step['input_connections']['mapfn'])
            step['inputs'] = [x for x in step['inputs']
                              if x['name'] != 'mapfn']
    # remove biomart input, update all IDs that come from there
    step_tool_states = get_step_tool_states(wf_json)
    mart_step_id = get_input_dset_step_id_for_name(step_tool_states,
                                                   'biomart map')
    remove_step_from_wf(mart_step_id, wf_json)


def remove_step_from_wf(removestep_id, wf_json, remove_connections=False):
    """Removes a step, subtracts one from all step IDs after it, also resetting
    input connections step IDs. If remove_connections is True, this deletes
    the connections that represent the removestep_id from other steps in the
    workflow. Set to True in case the removestep is not a Galaxy "input step"
    """
    del(wf_json['steps'][str(removestep_id)])
    newsteps = {}
    for step in wf_json['steps'].values():
        if step['id'] > removestep_id:
            step['id'] -= 1
        removekeys = []
        for conkey, connection in step['input_connections'].items():
            if type(connection) == list:
                keepsubkeys = []
                for conix, multi_connection in enumerate(connection):
                    if multi_connection['id'] != removestep_id:
                        keepsubkeys.append(conix)
                    if multi_connection['id'] > removestep_id:
                        multi_connection['id'] -= 1
                if remove_connections:
                    connection = [connection[ix] for ix in keepsubkeys]
            elif connection['id'] > removestep_id:
                connection['id'] -= 1
            elif connection['id'] == removestep_id:
                removekeys.append(conkey)
        if remove_connections:
            for ck in removekeys:
                del(step['input_connections'][ck])
        newsteps[str(step['id'])] = step
    wf_json['steps'] = newsteps


def disable_isobaric_params(wf_json):
    print('Removing isobaric steps and inputs from workflow')
    set_level_two_option(wf_json, 'Process PSM table', 'isobaric', 'yesno',
                         'false')
    set_level_two_option(wf_json,  'Process PSM table', 'isobaric',
                         'denompatterns', '')
    set_level_one_option(wf_json, 'Merge peptide or protein tables',
                         'isobqcolpattern', '')
    set_level_one_option(wf_json, 'Merge peptide or protein tables',
                         'nopsmcolpattern', '')
    for stepname in ['Create peptide table', 'Create protein table',
                     'Create gene table', 'Create symbol table']:
        set_level_two_option(wf_json, stepname, 'isoquant', 'yesno', 'false')


def remove_isobaric_vardb6rf(wf_json, searchtype):
    # FIXME untested! This removes ENS-search-normalization PSMs input but that
    # should be done on normalization protein steps too!
    # There is possibly more to delete. Check it.
    # THIS IS FOR LABELFREE 6RF/VARDB
    # in 6RF psm normalsearch is also for shift of peptides, so do not remove
    # normalsearch table step
    disable_isobaric_params(wf_json)
    step_toolstates = get_step_tool_states(wf_json)
    remove_annotated_steps(wf_json,
                           'Normalization protein isobaric ratio table')
    if searchtype == 'vardb':
        # need psmstep for pI shift in 6RF WF
        psmstep = get_input_dset_step_id_for_name(step_toolstates,
                                                  'psm table normalsearch')
        remove_step_from_wf(psmstep, wf_json)


def remove_isobaric_from_protein_centric(wf_json):
    remove_annotated_steps(wf_json,
                           'Normalization protein isobaric ratio table')
    disable_isobaric_params(wf_json)


def is_runtime_param(val, name, step):
    try:
        isruntime = val['__class__'] == 'RuntimeValue'
    except (KeyError, TypeError):
        return False
    else:
        if isruntime and name not in step['input_connections']:
            return True
        return False


def wait_for_copyjob(dset, gi):
    state = dset['jobs'][0]['state']
    while state in ['new', 'queued', 'running']:
        sleep(3)
        state = gi.jobs.show_job(dset['jobs'][0]['id'])['state']
    return state


def collect_spectra(inputstore, gi):
    print('Putting files from source histories {} in collection in search '
          'history {}'.format(inputstore['source_history'],
                              inputstore['history']))
    name_id_hdas = []
    for mzml in inputstore['raw']:
        name_id_hdas.append((mzml['filename'], mzml['galaxy_id']))
    if 'sort_specfiles' in inputstore['params']:
        name_id_hdas = sorted(name_id_hdas, key=lambda x: x[0])
    coll_spec = {
        'name': 'spectra', 'collection_type': 'list',
        'element_identifiers': [{'name': name, 'id': g_id, 'src': 'hda'}
                                for name, g_id in name_id_hdas]}
    collection = gi.histories.create_dataset_collection(inputstore['history'],
                                                        coll_spec)
    inputstore['datasets']['spectra'] = {'src': 'hdca', 'id': collection['id'],
                                         'history': inputstore['history']}
    return inputstore


def get_datasets_to_download(run, outpath_full, gi):
    print('Collecting datasets to download')
    download_dsets = {}
    for step in run['wf']['steps'].values():
        if 'post_job_actions' not in step:
            continue
        pj = step['post_job_actions']
        for pjk in pj:
            if pjk[:19] == 'RenameDatasetAction':
                nn = pj[pjk]['action_arguments']['newname']
                if nn[:4] == 'out:':
                    outname = nn[5:].replace(' ', '_')
                    download_dsets[nn] = {
                        'download_state': False, 'download_id': False,
                        'id': None, 'src': 'hda',
                        'download_dest': os.path.join(outpath_full, outname)}
    run['output_dsets'] = download_dsets
    print('Defined datasets from workflow: {}'.format(download_dsets.keys()))
    update_inputstore_from_history(gi, run['output_dsets'],
                                   run['output_dsets'].keys(), run['history'],
                                   'download')
    print('Found datasets to download, {}'.format(download_dsets))
    return run


def get_workflow_inputs_json(wfjson):
    """From workflow JSON returns (name, uuid) of the input steps"""
    for step in wfjson['steps'].values():
        if (step['tool_id'] is None and step['name'] in
                ['Input dataset', 'Input dataset collection']):
            yield(step['label'], step['uuid'])


def update_inputstore_from_history(gi, datasets, dsetnames, history_id,
                                   modname):
    print('Getting history contents')
    while not check_inputs_ready(datasets, dsetnames, modname):
        his_contents = gi.histories.show_history(history_id, contents=True,
                                                 deleted=False)
        # FIXME reverse contents so we start with newest dsets?
        for index, dset in enumerate(his_contents):
            if not dset_usable(dset):
                continue
            name = dset['name']
            if name in dsetnames and datasets[name]['id'] is None:
                print('found dset {}'.format(name))
                datasets[name]['history'] = history_id
                if datasets[name]['src'] == 'hdca':
                    datasets[name]['id'] = get_collection_id_in_his(
                        his_contents, name, dset['id'], gi, index)
                elif datasets[name]['src'] == 'hda':
                    datasets[name]['id'] = dset['id']
        sleep(10)


def dset_usable(dset):
    state_ok = True
    if 'state' in dset and dset['state'] == 'error':
        state_ok = False
    if dset['deleted'] or not state_ok:
        return False
    else:
        return True


def get_collection_id_in_his(his_contents, dset_name, named_dset_id, gi,
                             his_index=False, direction=False):
    """Search through history contents (passed) to find a collection that
    contains the named_dset_id. When passing direction=-1, the history will
    be searched backwards. Handy when having tools that do discover_dataset
    and populate a collection after creating it."""
    print('Trying to find collection ID belonging to dataset {}'
          'and ID {}'.format(dset_name, named_dset_id))
    if his_index:
        search_start = his_index
        direction = 1
    elif direction == -1:
        search_start = -1
    for dset in his_contents[search_start::direction]:
        if dset['type'] == 'collection':
            dcol = gi.histories.show_dataset_collection(dset['history_id'],
                                                        dset['id'])
            if named_dset_id in [x['object']['id'] for x in dcol['elements']]:
                print('Correct, using {} id {}'.format(dset['name'],
                                                       dset['id']))
                return dset['id']
    print('No matching collection in history (yet)')
    return None


def check_inputs_ready(datasets, inputnames, modname):
    print('Checking inputs {} for module {}'.format(inputnames, modname))
    ready, missing = True, []
    for name in inputnames:
        if datasets[name]['id'] is None:
            missing.append(name)
            ready = False
    if not ready:
        print('Missing inputs for module {}: '
              '{}'.format(modname, ', '.join(missing)))
    else:
        print('All inputs found for module {}'.format(modname))
    return ready


def get_input_map_from_json(module, inputstore):
    inputmap = {}
    for label, uuid in get_workflow_inputs_json(module):
        inputmap[uuid] = {
            'id': inputstore[label]['id'],
            'src': inputstore[label]['src'],
        }
    return inputmap


def wait_for_completion(inputstore, gi):
    """Waits for all output data to be finished before continuing with
    download steps"""
    print('Wait for completion of datasets to download')
    workflow_ok = True
    while workflow_ok and False in [x['download_id'] for x in
                                    inputstore['output_dsets'].values()]:
        print('Datasets not ready yet, checking')
        workflow_ok = check_outputs_workflow_ok(gi, inputstore)
        sleep(60)
    if workflow_ok:
        print('Datasets ready for downloading in history '
              '{}'.format(inputstore['history']))
        return inputstore
    else:
        raise RuntimeError('Output datasets are in error or deleted state!')
