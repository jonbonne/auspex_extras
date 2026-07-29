"""
MicroPython Application for Real-Time Impedance Control
Runs a PD loop and streams data over WiFi (UDP).

- Device is identifiable by its unique MAC address (hex ID).
- Inputs (via UDP): q_desired, qdot_desired, qdotdot_ff, Kp, Kd
- Outputs (via UDP): hex_id, q_actual, qdot_actual, tau_calculated

Hardware: ESP12F (ESP8266)
Platform: MicroPython
"""

import uasyncio
import network
import socket
import struct
import time
import ubinascii
import machine
import gc

# -----------------------------------------------------------------------------
# --- 1. CONFIGURATION --------------------------------------------------------
# -----------------------------------------------------------------------------

# --- WiFi Configuration ---
# !!! REPLACE WITH YOUR WIFI CREDENTIALS !!!
WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASS = "YOUR_WIFI_PASSWORD"

# --- Network Configuration ---
UDP_PORT = 12345  # Port to listen on and send from

# --- Control Loop Configuration ---
CONTROL_LOOP_FREQ_HZ = 1000  # Target frequency for the PD loop (e.g., 1000 Hz)
CONTROL_LOOP_PERIOD_US = 1_000_000 // CONTROL_LOOP_FREQ_HZ

# --- Network Loop Configuration ---
# Data will be streamed in/out at this rate
NETWORK_LOOP_FREQ_HZ = 100  # Target frequency for network I/O (e.g., 100 Hz)
NETWORK_LOOP_PERIOD_MS = 1000 // NETWORK_LOOP_FREQ_HZ

# --- Data Structures ---
# 5 inputs (all floats)
# (q_desired, qdot_desired, qdotdot_feedforward, kp, kd)
INPUT_STRUCT = struct.Struct('fffff')  # 5 * 4 = 20 bytes

# 3 outputs (all floats) + 12-byte ID string
# (hex_id, q_actual, qdot_actual, tau_ext)
# '12s' is a 12-byte string (for the MAC address)
OUTPUT_STRUCT = struct.Struct('12sfff')  # 12 + 3 * 4 = 24 bytes


# -----------------------------------------------------------------------------
# --- 2. SHARED STATE ---------------------------------------------------------
# -----------------------------------------------------------------------------

class State:
    """
    A thread-safe (async-safe) class to store and share state
    between the control loop and the network loop.
    """
    def __init__(self):
        self.lock = uasyncio.Lock()
        
        # --- Input Command (from network) ---
        # (q_desired, qdot_desired, qdotdot_ff, Kp, Kd)
        self.q_in = 0.0
        self.qdot_in = 0.0
        self.qdotdot_in = 0.0  # Note: Not used in simple PD loop, but received
        self.kp = 0.0
        self.kd = 0.0
        
        # --- Output State (from control loop) ---
        # (q_actual, qdot_actual, tau_calculated)
        self.q_out = 0.0
        self.qdot_out = 0.0
        self.tau_out = 0.0
        
        # --- Network Info ---
        self.remote_addr = None  # (ip, port) of the last sender

    async def set_command(self, q, qd, qdd, kp, kd, addr):
        """Asynchronously update the desired state from the network."""
        async with self.lock:
            self.q_in = q
            self.qdot_in = qd
            self.qdotdot_in = qdd
            self.kp = kp
            self.kd = kd
            self.remote_addr = addr

    async def get_command(self):
        """Asynchronously get the latest command for the control loop."""
        async with self.lock:
            return (self.q_in, self.qdot_in, self.kp, self.kd)

    async def set_output(self, q, qd, tau):
        """Asynchronously update the output state from the control loop."""
        async with self.lock:
            self.q_out = q
            self.qdot_out = qd
            self.tau_out = tau

    async def get_output_and_addr(self):
        """Asynchronously get the latest output for the network loop."""
        async with self.lock:
            return (self.q_out, self.qdot_out, self.tau_out, self.remote_addr)


# -----------------------------------------------------------------------------
# --- 3. HARDWARE ABSTRACTION (MOCK FUNCTIONS) --------------------------------
# -----------------------------------------------------------------------------

# !!! REPLACE THESE WITH YOUR ACTUAL HARDWARE CODE !!!

def read_sensors():
    """
    MOCK FUNCTION: Reads the actual position and velocity.
    
    TODO: Replace this with your code to read from an encoder (e.g., via I2C,
    SPI, or GPIO interrupts) and estimate velocity.
    
    Returns:
        (float, float): A tuple of (q_actual, qdot_actual)
    """
    # Example: return my_encoder.get_position(), my_encoder.get_velocity()
    # For now, just return a static value
    return (0.0, 0.0)

def apply_torque(tau):
    """
    MOCK FUNCTION: Applies the calculated torque to the motor.
    
    TODO: Replace this with your code to drive a motor controller
    (e.g., by setting a PWM duty cycle on a GPIO pin).
    
    Args:
        tau (float): The calculated torque command.
    """
    # Example: my_motor_driver.set_torque_pwm(tau)
    # print(f"Applying torque: {tau:.4f}")
    pass

# -----------------------------------------------------------------------------
# --- 4. ASYNCHRONOUS TASKS ---------------------------------------------------
# -----------------------------------------------------------------------------

async def control_loop(state):
    """
    High-frequency, "real-time" PD control loop.
    This task should do NO allocations or blocking operations (like print).
    """
    print(f"Starting control loop at {CONTROL_LOOP_FREQ_HZ} Hz")
    
    while True:
        loop_start_us = time.ticks_us()
        
        # 1. Read actual state from sensors
        q_actual, qdot_actual = read_sensors()
        
        # 2. Get latest command from shared state
        # This is fast as the lock is typically not contended.
        q_desired, qdot_desired, kp, kd = await state.get_command()
        
        # 3. Calculate PD error and torque
        # tau_ext = Kp * (q_desired - q_actual) + Kd * (qdot_desired - qdot_actual)
        error_q = q_desired - q_actual
        error_qdot = qdot_desired - qdot_actual
        
        tau_ext = (kp * error_q) + (kd * error_qdot)
        
        # 4. Apply torque to motor
        apply_torque(tau_ext)
        
        # 5. Update shared state with new output
        await state.set_output(q_actual, qdot_actual, tau_ext)
        
        # 6. Sleep to maintain loop frequency
        elapsed_us = time.ticks_diff(time.ticks_us(), loop_start_us)
        sleep_us = CONTROL_LOOP_PERIOD_US - elapsed_us
        
        if sleep_us > 0:
            await uasyncio.sleep_us(sleep_us)
        else:
            # Loop overran. Yield to other tasks immediately.
            # WARNING: This means you are not meeting your real-time target.
            # Consider lowering CONTROL_LOOP_FREQ_HZ or optimizing sensor/motor code.
            await uasyncio.sleep_ms(0)

async def network_loop(state, my_id_bytes):
    """
    Lower-frequency loop to handle all WiFi (UDP) I/O.
    """
    print(f"Starting network loop at {NETWORK_LOOP_FREQ_HZ} Hz")
    
    # 1. Setup UDP socket
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setblocking(False)  # Critically important for asyncio
    udp_socket.bind(("", UDP_PORT))
    
    rx_buffer = bytearray(INPUT_STRUCT.size)
    
    print(f"Listening for UDP packets on port {UDP_PORT}")
    
    while True:
        loop_start_ms = time.ticks_ms()
        
        # --- 2. Receive Data (Non-Blocking) ---
        try:
            # Read from socket
            nbytes, addr = udp_socket.recvfrom_into(rx_buffer, INPUT_STRUCT.size)
            
            if nbytes == INPUT_STRUCT.size:
                # Unpack the 5 floats
                q, qd, qdd, kp, kd = INPUT_STRUCT.unpack(rx_buffer)
                
                # Update the shared state
                await state.set_command(q, qd, qdd, kp, kd, addr)
                
        except OSError as e:
            # This is expected. errno 11 (EAGAIN/EWOULDBLOCK) means
            # "no data available right now".
            if e.args[0] != 11:
                print(f"Network Read Error: {e}")
                
        # --- 3. Send Data (Non-Blocking) ---
        (q_out, qdot_out, tau_out, remote_addr) = await state.get_output_and_addr()
        
        if remote_addr:
            try:
                # Pack the 12-byte ID and 3 floats
                tx_buffer = OUTPUT_STRUCT.pack(my_id_bytes, q_out, qdot_out, tau_out)
                udp_socket.sendto(tx_buffer, remote_addr)
                
            except OSError as e:
                print(f"Network Send Error: {e}")
                
        # --- 4. Sleep to maintain loop frequency ---
        elapsed_ms = time.ticks_diff(time.ticks_ms(), loop_start_ms)
        await uasyncio.sleep_ms(max(0, NETWORK_LOOP_PERIOD_MS - elapsed_ms))
        
        # 5. Clean up memory
        gc.collect()

# -----------------------------------------------------------------------------
# --- 5. HELPER FUNCTIONS -----------------------------------------------------
# -----------------------------------------------------------------------------

def connect_wifi():
    """Connects the device to WiFi."""
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print(f"Connecting to WiFi (SSID: {WIFI_SSID})...")
        sta_if.active(True)
        sta_if.connect(WIFI_SSID, WIFI_PASS)
        while not sta_if.isconnected():
            time.sleep(0.5)
    
    print("--- WiFi Connected! ---")
    print(f"IP Address: {sta_if.ifconfig()[0]}")

def get_hex_id():
    """Returns the device's unique MAC address as a 12-char hex string."""
    mac_bytes = network.WLAN(network.STA_IF).config('mac')
    hex_id_str = ubinascii.hexlify(mac_bytes).decode('utf-8')
    print(f"Device Hex ID: {hex_id_str}")
    return hex_id_str.encode('utf-8')  # Return as bytes for packing

# -----------------------------------------------------------------------------
# --- 6. MAIN EXECUTION -------------------------------------------------------
# -----------------------------------------------------------------------------

async def main():
    try:
        connect_wifi()
        my_id_bytes = get_hex_id()  # This is our 12-byte hex ID
        
        # Create the shared state object
        shared_state = State()
        
        # Create and start the asynchronous tasks
        uasyncio.create_task(control_loop(shared_state))
        uasyncio.create_task(network_loop(shared_state, my_id_bytes))
        
        # Run the asyncio event loop forever
        while True:
            await uasyncio.sleep(10) # Keep main task alive
            
    except Exception as e:
        print(f"Error in main loop: {e}")
        print("Rebooting in 5 seconds...")
        time.sleep(5)
        machine.reset()

# Start the application
if __name__ == "__main__":
    try:
        uasyncio.run(main())
    except KeyboardInterrupt:
        print("Program stopped.")
    except Exception as e:
        print(f"Fatal error: {e}")
        machine.reset()

