import traceback

from PySpice.Probe.Plot import plot
from PySpice.Spice.Library import SpiceLibrary
from PySpice.Spice.Netlist import Circuit
from PySpice.Unit import *
import numpy as np

class CombatResolution:
    def __init__(self):
        spice_library_path = '/opt/spice_libraries/LTSpice-parts/parts/opamp/LM324.ti.lib'
        self.spice_library = SpiceLibrary(spice_library_path)
        self.circuit = Circuit('Dual Input Integrator with Summing Amplifier')
        self._build_circuit()
        print("CombatResolution Ready!")

    def _build_circuit(self):
        # Define op-amps
        self.circuit.include(self.spice_library['LM324'])

        # Power supply for op-amps
        self.circuit.V(1, 'Vcc', self.circuit.gnd, 15@u_V)
        self.circuit.V(2, 'Vee', self.circuit.gnd, -15@u_V)

        # Input signals
        self.circuit.SinusoidalVoltageSource('Vin1', 'Vin1', self.circuit.gnd, amplitude=1@u_V, frequency=1@u_kHz)
        self.circuit.SinusoidalVoltageSource('Vin2', 'Vin2', self.circuit.gnd, amplitude=1.5@u_V, frequency=500@u_Hz)

        # Integrator 1
        self.circuit.R(1, 'Vin1', 'int1_in_neg', 10@u_kOhm)
        self.circuit.X(1, 'LM324', 'int1_in_pos', 'int1_in_neg', 'Vcc', 'Vee', 'int1_out')
        self.circuit.C(1, 'int1_in_neg', 'int1_out', 1@u_uF)
        self.circuit.R(2, 'int1_in_neg', 'int1_out', 1@u_MOhm)  # DC offset resistor
        self.circuit.R(3, 'int1_in_pos', self.circuit.gnd, 1@u_MOhm)

        # Integrator 2
        self.circuit.R(4, 'Vin2', 'int2_in_neg', 10@u_kOhm)
        self.circuit.X(2, 'LM324', 'int2_in_pos', 'int2_in_neg', 'Vcc', 'Vee', 'int2_out')
        self.circuit.C(2, 'int2_in_neg', 'int2_out', 1@u_uF)
        self.circuit.R(5, 'int2_in_neg', 'int2_out', 1@u_MOhm)  # DC offset resistor
        self.circuit.R(6, 'int2_in_pos', self.circuit.gnd, 1@u_MOhm)

        # Inverter for Integrator 2 output
        self.circuit.R(7, 'int2_out', 'inv_in_neg', 10@u_kOhm)
        self.circuit.R(8, 'int2_inv_out', 'inv_in_neg', 10@u_kOhm)  # Feedback resistor
        self.circuit.X(3, 'LM324', self.circuit.gnd, 'inv_in_neg', 'Vcc', 'Vee', 'int2_inv_out')

        # Summing Amplifier
        self.circuit.R(9, 'int1_out', 'sum_in_pos', 10@u_kOhm)
        self.circuit.R(10, 'int2_inv_out', 'sum_in_pos', 10@u_kOhm)
        self.circuit.X(4, 'LM324', 'sum_in_pos', 'sum_in_neg', 'Vcc', 'Vee', 'sum_out')
        self.circuit.R(11, 'sum_out', 'sum_in_neg', 10@u_kOhm)  # Feedback resistor
        self.circuit.R(12, 'sum_in_neg', self.circuit.gnd, 10@u_kOhm)
        self.circuit.R(13, 'sum_out', self.circuit.gnd, 1@u_MOhm)

        print(self.circuit)

    def simulate(self):
        simulator = self.circuit.simulator(temperature=25, nominal_temperature=25)
        analysis = simulator.transient(step_time=1@u_us, end_time=10@u_ms)
        return analysis

    def plot_results(self, analysis):
        import matplotlib.pyplot as plt

        plt.figure(figsize=(10, 6))

        plt.plot(analysis['Vin1'], label='Vin1')
        plt.plot(analysis['Vin2'], label='Vin2')
        plt.plot(analysis['int1_out'], label='Integrator 1 Output')
        plt.plot(analysis['int2_out'], label='Integrator 2 Output')
        plt.plot(analysis['sum_out'], label='Summing Amplifier Output')

        plt.legend()
        plt.grid()
        plt.xlabel('Time (s)')
        plt.ylabel('Voltage (V)')
        plt.title('Circuit Simulation Results')
        plt.show()

# Usage example
if __name__ == "__main__":
    circuit = CombatResolution()
    try:
        analysis = circuit.simulate()
        circuit.plot_results(analysis)
    except Exception as err:
        print(f"Error: {err} | {traceback.format_exc()}")
