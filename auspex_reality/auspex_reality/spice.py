import yaml
from PySpice.Probe.Plot import plot
from PySpice.Spice.Library import SpiceLibrary
from PySpice.Spice.Netlist import Circuit
from PySpice.Unit import *
import numpy as np
import matplotlib.pyplot as plt

import sounddevice as sd
from scipy.io.wavfile import write

class BotSpice():

    def __init__(self, yaml_file):
        """Construction

        Load circuit configuration from a YAML file.
         """
        with open(yaml_file, 'r') as file:
            self._config = yaml.safe_load(file)


    def build_circuit(self):
        """Build the circuit dynamically based on the YAML configuration."""
        circuit = Circuit("Dynamic Circuit")

        # Define input signal generators
        for i, input_cfg in enumerate(self._config['inputs']):
            input_type = input_cfg['type']
            amplitude = input_cfg['amplitude']
            frequency = input_cfg['frequency']
            offset = input_cfg.get('offset', 0)

            if input_type == 'sine':
                circuit.SinusoidalVoltageSource(f"V{i+1}", f"input_{i+1}", circuit.gnd,
                                                amplitude@u_V, frequency@u_Hz, offset@u_V)
            elif input_type == 'square':
                circuit.PulseVoltageSource(f"V{i+1}", f"input_{i+1}", circuit.gnd,
                                           initial_value=0@u_V, pulsed_value=amplitude@u_V,
                                           pulse_width=(1 / (2 * frequency))@u_s,
                                           period=(1 / frequency)@u_s)
            elif input_type == 'triangle':
                circuit.SinusoidalVoltageSource(f"V{i+1}", f"input_{i+1}", circuit.gnd,
                                                amplitude@u_V, frequency@u_Hz)
                # Approximation with sine generator, adjust for real triangle signal

        # Add network between inputs and outputs
        for net_cfg in self._config['network']:
            component_type = net_cfg['type']
            node_a = net_cfg['node_a']
            node_b = net_cfg['node_b']
            value = net_cfg['value']

            if component_type == 'resistor':
                circuit.R(f"R_{node_a}_{node_b}", node_a, node_b, value@u_Ohm)
            elif component_type == 'capacitor':
                circuit.C(f"C_{node_a}_{node_b}", node_a, node_b, value@u_F)
            elif component_type == 'inductor':
                circuit.L(f"L_{node_a}_{node_b}", node_a, node_b, value@u_H)
            elif component_type == 'diode':
                circuit.D(f"D_{node_a}_{node_b}", node_a, node_b, model='1N4148')
            elif component_type == 'potentiometer':
                # Potentiometers need an adjustable resistance
                circuit.R(f"Rpot_{node_a}_{node_b}", node_a, node_b, value@u_Ohm)

        # Buffer outputs (for ESP32 analog inputs)
        for i in range(1, self._config['outputs'] + 1):
            circuit.VoltageControlledVoltageSource(f"E{i}", f"output_{i}", circuit.gnd,
                                                   f"node_{i}", circuit.gnd, 1)

        return circuit


    def simulate_circuit(self, circuit):
        """Simulate the circuit and return the results."""
        simulator = circuit.simulator(temperature=25, nominal_temperature=25)
        analysis = simulator.transient(step_time=1@u_ms, end_time=self._config['simulation']['end_time']@u_ms)

        return analysis


    def export_data(self, analysis):
        """Export simulation results for ESP32."""
        results = {}
        for i in range(1, self._config['outputs'] + 1):
            results[f"output_{i}"] = analysis[f"output_{i}"].as_ndarray()

        # Serialize data for ESP32 (example: as a JSON or binary stream)
        return results

    def play_waveform(self, analysis, node, sampling_rate=44100, duration=5):
        """
        Play the waveform from a PySpice simulation.

        :param analysis: PySpice analysis result.
        :param node: Node name in the circuit (e.g., "output_1").
        :param sampling_rate: Audio sampling rate (Hz).
        :param duration: Duration of the sound (s).
        """
        # Extract the waveform as a NumPy array
        waveform = analysis[node].as_ndarray()

        # Normalize to [-1.0, 1.0] for audio
        max_voltage = np.max(np.abs(waveform))
        normalized_waveform = waveform / max_voltage if max_voltage != 0 else waveform

        # Resample to match the audio sampling rate
        simulation_time = analysis.time.as_ndarray()
        simulation_rate = 1 / (simulation_time[1] - simulation_time[0])
        resampled_waveform = np.interp(
            np.linspace(0, len(waveform) / simulation_rate, int(sampling_rate * duration)),
            np.linspace(0, len(waveform) / simulation_rate, len(waveform)),
            normalized_waveform,
        )

        # Play the sound
        sd.play(resampled_waveform, samplerate=sampling_rate)
        sd.wait()

        # Optionally save to a WAV file
        write("output_sound.wav", sampling_rate, (resampled_waveform * 32767).astype(np.int16))
        print("Sound saved to output_sound.wav")

    # Example usage (assuming `analysis` is from PySpice simulation)
    # play_waveform(analysis, node="output_1")

