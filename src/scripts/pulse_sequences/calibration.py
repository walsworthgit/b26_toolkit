"""
    This file is part of b26_toolkit, a PyLabControl add-on for experiments in Harvard LISE B26.
    Copyright (C) <2016>  Arthur Safira, Jan Gieseler, Aaron Kabcenell

    Foobar is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Foobar is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Foobar.  If not, see <http://www.gnu.org/licenses/>.
"""

import numpy as np
from b26_toolkit.src.scripts.pulse_blaster_base_script import PulseBlasterBaseScript
from b26_toolkit.src.instruments import NI6259, B26PulseBlaster, MicrowaveGenerator, Pulse
from PyLabControl.src.core import Parameter
from b26_toolkit.src.data_processing.fit_functions import cose_with_decay, fit_exp_decay


class CalibrateMeasurementWindow(PulseBlasterBaseScript):
    """
This script find the optimal duration of the measurment window.
It applies a sliding measurement window with respect to a readout from the NV 0 state and the NV 1 state.
    """
    _DEFAULT_SETTINGS = [
        Parameter('mw_power', -45.0, float, 'microwave power in dB'),
        Parameter('mw_frequency', 2.87e9, float, 'microwave frequency in Hz'),
        Parameter('pi_pulse_time', 50, float, 'time duration of pi-pulse (in ns)'),
        Parameter('readout_window_incremement', 10, [5, 10, 20, 50, 100], 'time step increment of measurement duration (in ns)'),
        Parameter('initial_readout_displacement', -80, int, 'min time of measurement duration (in ns)'),
        Parameter('final_readout_displacement', 450, int, 'max time of measurement duration (in ns)'),
        Parameter('reset_time', 3000, int, 'time with laser on at the beginning to reset state'),
        Parameter('delay_init_mw', 200, int, 'time delay before pi pulse after NV reset'),
        Parameter('delay_mw_readout', 200, int, 'time delay before readout after pi pulse'),
        Parameter('measurement_window_width', 20, int, 'the width of the sliding readout window'),
        Parameter('laser_on_time', 500, list(range(100, 1201, 100)), 'time laser is on for readout'),
        Parameter('ref_meas_off_time', 1000, int, 'time reset laser is turned off before reference measurement is made'),
        Parameter('num_averages', 1000000, int, 'number of averages')
    ]

    _INSTRUMENTS = {'daq': NI6259, 'PB': B26PulseBlaster, 'mw_gen': MicrowaveGenerator}

    def _function(self):
        self.instruments['mw_gen']['instance'].update({'modulation_type': 'IQ'})
        self.instruments['mw_gen']['instance'].update({'amplitude': self.settings['mw_power']})
        self.instruments['mw_gen']['instance'].update({'frequency': self.settings['mw_frequency']})
        super(CalibrateMeasurementWindow, self)._function()

    def _create_pulse_sequences(self):
        """

        Returns: pulse_sequences, num_averages, tau_list
            pulse_sequences: a list of pulse sequences, each corresponding to a different time 'tau' that is to be
            scanned over. Each pulse sequence is a list of pulse objects containing the desired pulses. Each pulse
            sequence must have the same number of daq read pulses
            num_averages: the number of times to repeat each pulse sequence
            tau_list: the list of times tau, with each value corresponding to a pulse sequence in pulse_sequences
            meas_time: the width (in ns) of the daq measurement

        """
        pulse_sequences = []
        tau_list = list(range(self.settings['initial_readout_displacement'],
                         self.settings['final_readout_displacement'],
                         self.settings['readout_window_incremement']))
        reset_time = self.settings['reset_time']

        for tau in tau_list:
            pulse_sequences.append([Pulse('laser', 0, reset_time - self.settings['ref_meas_off_time'] - self.settings['laser_on_time']),
                                    Pulse('apd_readout', reset_time - self.settings['laser_on_time'] + tau, self.settings['measurement_window_width']),
                                    Pulse('laser', reset_time - self.settings['laser_on_time'], self.settings['laser_on_time']),
                                    Pulse('microwave_i', reset_time + self.settings['delay_init_mw'], self.settings['pi_pulse_time']),
                                    Pulse('laser', reset_time + self.settings['delay_init_mw'] + self.settings['pi_pulse_time'] + self.settings[
                                        'delay_mw_readout'], self.settings['laser_on_time']),
                                    Pulse('apd_readout', reset_time + self.settings['delay_init_mw'] + self.settings['pi_pulse_time'] +
                                          self.settings['delay_mw_readout'] + tau, self.settings['measurement_window_width'])
                                    ])

        return pulse_sequences, self.settings['num_averages'], tau_list, self.settings['measurement_window_width']

    def _plot(self, axes_list, data = None):
        """
        Plot 1: self.data['tau'], the list of times specified for a given experiment, verses self.data['counts'], the data
        received for each time
        Plot 2: the pulse sequence performed at the current time (or if plotted statically, the last pulse sequence
        performed

        Args:
            axes_list: list of axes to write plots to (uses first)
            data (optional): dataset to plot (dictionary that contains keys counts, tau), if not provided use self.data
        """

        super(CalibrateMeasurementWindow, self)._plot(axes_list, data)
        axes_list[0].set_title('Measurement Calibration')
        axes_list[0].legend(labels=('|0> State Fluorescence', '|1> State Fluoresence'), fontsize=8)

class readout_T_double_init(PulseBlasterBaseScript):  # ER 10.21.2017
    """
This script sweeps the readout pulse rise time. To symmetrize the sequence between the 0 and +/-1 state we reinitialize every time
    """
    _DEFAULT_SETTINGS = [
        Parameter('mw_pulse', [
            Parameter('mw_power', -45.0, float, 'microwave power in dB'),
            Parameter('mw_frequency', 2.87e9, float, 'microwave frequency in Hz'),
            Parameter('microwave_channel', 'i', ['i', 'q'], 'Channel to use for mw pulses'),
            Parameter('pi_time', 30.0, float, 'pi time in ns')
        ]),
        Parameter('tau_times', [
            Parameter('min_time', 15, float, 'minimum time for rabi oscillations (in ns)'),
            Parameter('max_time', 200, float, 'total time of rabi oscillations (in ns)'),
            Parameter('time_step', 5, [5, 10, 20, 50, 100, 200, 500, 1000, 10000, 100000, 500000],
                      'time step increment of readout pulse duration (in ns)')
        ]),
        Parameter('read_out', [
            Parameter('nv_reset_time', 1750, int, 'time with laser on to reset state'),
            Parameter('laser_off_time', 1000, int,
                      'minimum laser off time before taking measurements (ns)'),
            Parameter('delay_mw_readout', 100, int, 'delay between mw and readout (in ns)'),
            Parameter('delay_readout', 30, int, 'delay between laser on and readout (given by spontaneous decay rate)'),
            Parameter('readout_window', 300, int, 'length of readout window')
        ]),
        Parameter('num_averages', 100000, int, 'number of averages'),
    ]

    _INSTRUMENTS = {'daq': NI6259, 'PB': B26PulseBlaster, 'mw_gen': MicrowaveGenerator}

    def _function(self):
        # COMMENT_ME

        self.data['fits'] = None
        self.instruments['mw_gen']['instance'].update({'modulation_type': 'IQ'})
        self.instruments['mw_gen']['instance'].update({'amplitude': self.settings['mw_pulse']['mw_power']})
        self.instruments['mw_gen']['instance'].update({'frequency': self.settings['mw_pulse']['mw_frequency']})
        super(readout_T_double_init, self)._function(self.data)


        counts = self.data['counts'][:, 1] # / self.data['counts'][:, 0]
        tau = self.data['tau']

        try:
            fits = fit_exp_decay(tau, counts, varibale_phase=True)
            self.data['fits'] = fits
        except:
            self.data['fits'] = None
            self.log('fit failed')

    def _create_pulse_sequences(self):
        '''

        Returns: pulse_sequences, num_averages, tau_list, meas_time
            pulse_sequences: a list of pulse sequences, each corresponding to a different time 'tau' that is to be
            scanned over. Each pulse sequence is a list of pulse objects containing the desired pulses. Each pulse
            sequence must have the same number of daq read pulses
            num_averages: the number of times to repeat each pulse sequence
            tau_list: the list of times tau, with each value corresponding to a pulse sequence in pulse_sequences
            meas_time: the width (in ns) of the daq measurement

        '''
        pulse_sequences = []
        # tau_list = range(int(max(15, self.settings['tau_times']['time_step'])), int(self.settings['tau_times']['max_time'] + 15),
        #                  self.settings['tau_times']['time_step'])
        # JG 16-08-25 changed (15ns min spacing is taken care of later):
        tau_list = list(range(int(self.settings['tau_times']['min_time']), int(self.settings['tau_times']['max_time']),
                         self.settings['tau_times']['time_step']))

        # ignore the sequence if the mw-pulse is shorter than 15ns (0 is ok because there is no mw pulse!)
        tau_list = [x for x in tau_list if x == 0 or x >= 15]
        nv_reset_time = self.settings['read_out']['nv_reset_time']
        delay_readout = self.settings['read_out']['delay_readout']
        microwave_channel = 'microwave_' + self.settings['mw_pulse']['microwave_channel']

        laser_off_time = self.settings['read_out']['laser_off_time']
        delay_mw_readout = self.settings['read_out']['delay_mw_readout']
        pi_time = self.settings['mw_pulse']['pi_time']
        meas_time = self.settings['read_out']['readout_window']


        for tau in tau_list:
            pulse_sequence = \
                [Pulse('laser', laser_off_time, nv_reset_time),
                 Pulse('apd_readout', laser_off_time+ delay_readout + tau, meas_time),
                 ]
            # if tau is 0 there is actually no mw pulse
            if tau > 0:
                pulse_sequence += [Pulse(microwave_channel, laser_off_time + nv_reset_time + laser_off_time, pi_time)]

            pulse_sequence += [
                Pulse('laser', laser_off_time + nv_reset_time + laser_off_time + delay_mw_readout, nv_reset_time),
                Pulse('apd_readout', laser_off_time + nv_reset_time + laser_off_time + delay_mw_readout + delay_readout + tau, meas_time)
            ]
            # ignore the sequence is the mw is shorter than 15ns (0 is ok because there is no mw pulse!)
            # if tau == 0 or tau>=15:
            pulse_sequences.append(pulse_sequence)

        return pulse_sequences, self.settings['num_averages'], tau_list, meas_time

    def _plot(self, axislist, data=None):
        '''
        Plot 1: self.data['tau'], the list of times specified for a given experiment, verses self.data['counts'], the data
        received for each time
        Plot 2: the pulse sequence performed at the current time (or if plotted statically, the last pulse sequence
        performed

        Args:
            axes_list: list of axes to write plots to (uses first 2)
            data (optional) dataset to plot (dictionary that contains keys counts, tau, fits), if not provided use self.data
        '''

        if data is None:
            data = self.data

        if data['fits'] is not None:
            counts = data['counts'][:, 1] / data['counts'][:, 0]
            tau = data['tau']
            fits = data['fits']  # amplitude, frequency, phase, offset

            axislist[0].plot(tau, counts, 'b')
            axislist[0].hold(True)

            axislist[0].plot(tau, cose_with_decay(tau, *fits), 'k', lw=3)
            # pi_time = 2*np.pi / fits[1] / 2
            pi_time = (np.pi - fits[2]) / fits[1]
            pi_half_time = (np.pi / 2 - fits[2]) / fits[1]
            three_pi_half_time = (3 * np.pi / 2 - fits[2]) / fits[1]
            rabi_freq = 1000 * fits[1] / (2 * np.pi)
            #   axislist[0].set_title('Rabi mw-power:{:0.1f}dBm, mw_freq:{:0.3f} GHz, pi-time: {:2.1f}ns, pi-half-time: {:2.1f}ns, 3pi_half_time: {:2.1f}ns, Rabi freq: {2.1f}MHz'.format(self.settings['mw_pulses']['mw_power'], self.settings['mw_pulses']['mw_frequency']*1e-9, pi_time, pi_half_time, three_pi_half_time, rabi_freq))
            axislist[0].set_title('Readout pulse width counts')
        else:
            super(readout_T_double_init, self)._plot(axislist)
            axislist[0].set_title('Readout pulse width counts')
            axislist[0].legend(labels=('Ref Fluorescence', 'Pi pulse Data'), fontsize=8)