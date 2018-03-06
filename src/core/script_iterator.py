from PyLabControl.src.core.script_iterator import ScriptIterator
from PyLabControl.src.core import Script, Parameter
import numpy as np


class ScriptIteratorB26(ScriptIterator):

    ITER_TYPES = ScriptIterator.ITER_TYPES + ['iter nvs', 'iter points', 'test']

    def __init__(self, scripts, name=None, settings=None, log_function=None, data_path=None):
        super(ScriptIteratorB26, self).__init__(scripts=scripts, name=name, settings=settings, log_function=log_function, data_path=data_path)


    @staticmethod
    def get_iterator_type(script_settings, subscripts={}):
        """
        figures out the iterator type based on the script settings and (optionally) subscripts
        Args:
            script_settings: iterator_type
            subscripts: subscripts
        Returns:

        """

        if 'iterator_type' in script_settings:
            print('JG tmp iterator_type', script_settings['iterator_type'])

        if 'iterator_type' in script_settings:
            # figure out the iterator type
            if script_settings['iterator_type'] == 'Iter NVs':
                iterator_type = 'iter nvs'
            elif script_settings['iterator_type'] == 'Iter Points':
                iterator_type = 'iter points'
            elif script_settings['iterator_type'] == 'Iter test':
                iterator_type = 'test'
            else:
                iterator_type = ScriptIterator.get_iterator_type(script_settings, subscripts)
        else:
            # asign the correct iterator script type
            if 'find_nv' in subscripts and 'select_points' in subscripts:
                iterator_type = 'iter nvs'
            elif 'set_laser' in subscripts and 'select_points' in subscripts:
                iterator_type = 'iter points'
            elif 'wait' in subscripts:
                iterator_type = 'test'
            else:
                iterator_type = ScriptIterator.get_iterator_type(script_settings, subscripts)

        assert iterator_type in ScriptIteratorB26.ITER_TYPES


        return iterator_type

    @staticmethod
    def get_iterator_default_script(iterator_type):
        """


        Returns:
            sub_scripts: a dictionary with the default scripts for the script_iterator
            script_settings: a dictionary with the script_settingsfor the default scripts

        """

        sub_scripts = {}
        script_settings = {}

        package = 'b26_toolkit' # todo JG: mabye find a dynamic whay to get this

        # for point iteration we add some default scripts
        if iterator_type == 'iter nvs':

            module = Script.get_script_module('SelectPoints')# Select points is actually in PyLabControl
            sub_scripts.update(
                {'select_points': getattr(module, 'SelectPoints')}
            )
            module = Script.get_script_module('FindNV', package)
            sub_scripts.update(
                #      {'find_nv': getattr(module, 'FindNV_cDAQ')}
                {'find_nv': getattr(module, 'FindNV')}
            )
            module = Script.get_script_module('Take_And_Correlate_Images', package)
            sub_scripts.update(
                {'correlate_iter': getattr(module, 'Take_And_Correlate_Images', package)}
            )
            script_settings['script_order'] = {'select_points': -3, 'correlate_iter': -2, 'find_nv': -1}

        elif iterator_type == 'iter points':
            module = Script.get_script_module('SelectPoints', 'PyLabControl')
            sub_scripts.update(
                {'select_points': getattr(module, 'SelectPoints')}
            )
            module = Script.get_script_module('SetLaser', package)
            sub_scripts.update(
                {'set_laser': getattr(module, 'SetLaser')}
            )
            module = Script.get_script_module('Take_And_Correlate_Images', package)
            sub_scripts.update(
                {'correlate_iter': getattr(module, 'Take_And_Correlate_Images')}
            )
            script_settings['script_order']={'select_points': -3, 'correlate_iter': -2, 'set_laser': -1}

        elif iterator_type == 'test':
            module = Script.get_script_module('Wait', 'PyLabControl')
            sub_scripts.update(
                {'wait': getattr(module, 'Wait')}
            )



        return sub_scripts, script_settings

    @staticmethod
    def get_default_settings(sub_scripts, script_order, script_execution_freq, iterator_type):
        """
        assigning the actual script settings depending on the iterator type
        Args:
            sub_scripts: dictionary with the subscripts
            script_order: execution order of subscripts
            script_execution_freq: execution frequency of subscripts

        Returns:
            the default setting for the iterator

        """

        def populate_sweep_param(scripts, parameter_list, trace=''):
            '''

            Args:
                scripts: a dict of {'class name': <class object>} pairs

            Returns: A list of all parameters of the input scripts

            '''

            def get_parameter_from_dict(trace, dic, parameter_list, valid_values=None):
                """
                appends keys in the dict to a list in the form trace.key.subkey.subsubkey...
                Args:
                    trace: initial prefix (path through scripts and parameters to current location)
                    dic: dictionary
                    parameter_list: list to which append the parameters

                    valid_values: valid values of dictionary values if None dic should be a dictionary

                Returns:

                """
                if valid_values is None and isinstance(dic, Parameter):
                    valid_values = dic.valid_values

                for key, value in dic.iteritems():
                    if isinstance(value, dict):  # for nested parameters ex {point: {'x': int, 'y': int}}
                        parameter_list = get_parameter_from_dict(trace + '.' + key, value, parameter_list,
                                                                 dic.valid_values[key])
                    elif (valid_values[key] in (float, int)) or \
                            (isinstance(valid_values[key], list) and valid_values[key][0] in (float, int)):
                        parameter_list.append(trace + '.' + key)
                    else:  # once down to the form {key: value}
                        # in all other cases ignore parameter
                        print('ignoring sweep parameter', key)

                return parameter_list

            for script_name in scripts.keys():
                from PyLabControl.src.core import ScriptIterator
                script_trace = trace
                if script_trace == '':
                    script_trace = script_name
                else:
                    script_trace = script_trace + '->' + script_name
                if issubclass(scripts[script_name], ScriptIterator):  # gets subscripts of ScriptIterator objects
                    populate_sweep_param(vars(scripts[script_name])['_SCRIPTS'], parameter_list=parameter_list,
                                         trace=script_trace)
                else:
                    # use inspect instead of vars to get _DEFAULT_SETTINGS also for classes that inherit _DEFAULT_SETTINGS from a superclass
                    for setting in \
                    [elem[1] for elem in inspect.getmembers(scripts[script_name]) if elem[0] == '_DEFAULT_SETTINGS'][0]:
                        parameter_list = get_parameter_from_dict(script_trace, setting, parameter_list)

            return parameter_list

        print('iterator_type AA', iterator_type)


        if iterator_type in ('iter nvs', 'iter points'):
            script_default_settings = [
                Parameter('script_order', script_order),
                Parameter('script_execution_freq', script_execution_freq),
                Parameter('run_all_first', True, bool, 'Run all scripts with nonzero frequency in first pass')
            ]

        elif iterator_type == 'test':
            script_default_settings = [
                Parameter('script_order', script_order),
                Parameter('script_execution_freq', script_execution_freq),
                Parameter('run_all_first', True, bool, 'Run all scripts with nonzero frequency in first pass')
            ]
        else:
            script_default_settings = ScriptIterator.get_default_settings(sub_scripts=sub_scripts,
                                                script_order=script_order,
                                                script_execution_freq=script_execution_freq,
                                                iterator_type=iterator_type)

        return script_default_settings

    @staticmethod
    def get_script_order(script_order):
        """

        Args:
            script_order:
                a dictionary giving the order that the scripts in the ScriptIterator should be executed.
                Must be in the form {'script_name': int}. Scripts are executed from lowest number to highest

        Returns:
            script_order_parameter:
                A list of parameters giving the order that the scripts in the ScriptIterator should be executed.
            script_execution_freq:
                A list of parameters giving the frequency with which each script should be executed

        """
        script_order_parameter = []
        script_execution_freq = []
        # update the script order
        for sub_script_name in script_order.keys():
            script_order_parameter.append(Parameter(sub_script_name, script_order[sub_script_name], int,
                                          'Order in queue for this script'))
            if sub_script_name == 'select_points':
                script_execution_freq.append(Parameter(sub_script_name, 0, int,
                                                       'How often the script gets executed ex. 1 is every loop, 3 is every third loop, 0 is never'))
            else:
                script_execution_freq.append(Parameter(sub_script_name, 1, int,
                                                       'How often the script gets executed ex. 1 is every loop, 3 is every third loop, 0 is never'))

        return script_order_parameter, script_execution_freq

    def _function(self):
        """
        Runs either a loop or a parameter sweep over the subscripts in the order defined by the parameter_list 'script_order'
        """

        script_names = self.settings['script_order'].keys()
        script_indices = [self.settings['script_order'][name] for name in script_names]
        _, sorted_script_names = zip(*sorted(zip(script_indices, script_names)))


        if self.iterator_type in ('iter nvs', 'iter points'):

            if self.iterator_type == 'iter nvs':
                set_point = self.scripts['find_nv'].settings['initial_point']
            elif self.iterator_type == 'iter points':
                set_point = self.scripts['set_laser'].settings['point']

            #shift found by correlation
            [x_shift, y_shift] = [0,0]
            shifted_pt = [0,0]

            self.scripts['correlate_iter'].data['baseline_image'] = self.scripts['select_points'].data['image_data']
            self.scripts['correlate_iter'].data['image_extent'] = self.scripts['select_points'].data['extent']

            points = self.scripts['select_points'].data['nv_locations']
            N_points = len(points)

            for i, pt in enumerate(points):

                # account for displacements found by correlation
                shifted_pt[0] = pt[0] + x_shift
                shifted_pt[1] = pt[1] + y_shift

                print('NV num: {:d}, shifted_pt: {:.3e}, {:.3e}', i, shifted_pt[0], shifted_pt[1])

                self.iterator_progress = 1. * i / N_points

                set_point.update({'x': shifted_pt[0], 'y': shifted_pt[1]})
                self.log('found NV {:03d} near x = {:0.3e}, y = {:0.3e}'.format(i, shifted_pt[0], shifted_pt[1]))
                # skip first script since that is the select NV script!
                for script_name in sorted_script_names[1:]:
                    if self._abort:
                        break
                    j = i if self.settings['run_all_first'] else (i+1)
                    if self.settings['script_execution_freq'][script_name] == 0 \
                            or not (j % self.settings['script_execution_freq'][script_name] == 0):
                        continue
                    self.log('starting {:s}'.format(script_name))
                    tag = self.scripts[script_name].settings['tag']
                    tmp = tag + '_pt_{' + ':0{:d}'.format(len(str(N_points))) + '}'
                    self.scripts[script_name].settings['tag'] = tmp.format(i)
                    self.scripts[script_name].run()
                    self.scripts[script_name].settings['tag'] = tag
                    #after correlation script runs, update new shift value
                    if script_name == 'correlate_iter':
                        [x_shift, y_shift] = self.scripts['correlate_iter'].data['shift']
                        shifted_pt[0] = pt[0] + x_shift
                        shifted_pt[1] = pt[1] + y_shift
                        set_point.update({'x': shifted_pt[0], 'y': shifted_pt[1]})

                        print('NV num: {:d}, shifted_pt: {:.3e}, {:.3e}', i, shifted_pt[0], shifted_pt[1])


        else:
            super(ScriptIteratorB26, self)._function()


    def to_dict(self):
        """
        Returns: itself as a dictionary
        """
        dictator = super(ScriptIteratorB26, self).to_dict()
        # the dynamically created ScriptIterator classes have a generic name
        # replace this with ScriptIterator to indicate that this class is of type ScriptIteratorB26
        dictator[self.name]['class'] = 'ScriptIteratorB26'

        return dictator


