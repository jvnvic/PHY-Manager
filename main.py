import tkinter as tk
from tkinter import ttk, scrolledtext
import serial
import serial.tools.list_ports
import time
from datetime import datetime

class SerialManager:
    def __init__(self):
        self.ser = None
        self.port_map = {}

    def list_ports(self):
        ports = serial.tools.list_ports.comports()
        self.port_map = {f"{port.device} - {port.description}": port.device for port in ports}
        return list(self.port_map.keys())

    def connect(self, port, baudrate=115200):
        self.ser = serial.Serial(port, baudrate, timeout=1)

    def send(self, message):
        if self.ser and self.ser.is_open:
            self.ser.write((message + "\n").encode())

    def read_lines(self):
        lines = []
        while self.ser and self.ser.in_waiting:
            line = self.ser.readline().decode(errors='ignore').strip()
            if line:
                lines.append(line)
        return lines

class EthernetPHYApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ethernet PHY Manager")
        self.geometry("720x480")

        self.serial_manager = SerialManager()
        self.port_map = {}
        self.device_id = ""
        self.connected = False
        self.reading_info = False
        self.device_speed = ""  # ← Add this line here
        self.device_info = {}  # stores controller, version, speed
        self.node_functions = {}  # maps tree item IDs to list of functions

        self.after(0, self.auto_scan_ports)              # Start scanning immediately
        self.after(500, self.check_serial_connection)    # Start hardware check





        self.create_widgets()

        

    def create_widgets(self):
        tab_control = ttk.Notebook(self)
        self.home_tab = ttk.Frame(tab_control)
        self.register_tab = ttk.Frame(tab_control)
        self.raw_mdio_tab = ttk.Frame(tab_control)
        self.settings_tab = ttk.Frame(tab_control)

        tab_control.add(self.home_tab, text='Home')
        tab_control.add(self.register_tab, text='Register Edit')
        tab_control.add(self.raw_mdio_tab, text='Raw MDIO')
        tab_control.add(self.settings_tab, text='Settings')
        tab_control.pack(expand=1, fill='both')
        self.setup_home_tab()
        self.setup_register_tab()




    def setup_home_tab(self):
        frame = ttk.Frame(self.home_tab)
        frame.pack(pady=10, fill='x')

        # scan_button = ttk.Button(frame, text="Scan", command=self.scan_ports)
        # scan_button.pack(side='left', padx=5)

        self.port_combo = ttk.Combobox(frame, state='readonly')
        self.port_combo.pack(side='left', fill='x', expand=True, padx=5)

        # Green status dot
        self.status_dot = tk.Canvas(frame, width=20, height=20, highlightthickness=0)
        self.status_circle = self.status_dot.create_oval(5, 5, 15, 15, fill="gray")
        self.status_dot.pack(side='left', padx=5)

        self.connect_button = ttk.Button(frame, text="Connect", command=self.connect_device)
        self.connect_button.pack(side='left', padx=5)

        content_frame = ttk.Frame(self.home_tab)
        content_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Treeview on the left
        self.tree = ttk.Treeview(content_frame)
        self.tree.heading("#0", text="Devices")
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.pack(side='left', fill='y')

        # Right panel for device/phy interaction
        self.interaction_frame = ttk.Frame(content_frame)
        self.interaction_frame.pack(side='left', fill='both', expand=True, padx=10)

        self.selected_label = ttk.Label(self.interaction_frame, text="Select a device or PHY", anchor='w', justify='left')
        self.selected_label.pack(pady=5, fill='x')

        self.speed_label = ttk.Label(self.interaction_frame, text="", anchor='w', justify='left')
        self.speed_label.pack(pady=2, fill='x')

        self.button_frame = ttk.Frame(self.interaction_frame)
        self.button_frame.pack(pady=5)

        # Container frame for serial monitor + dev note
        self.serial_container = ttk.Frame(self.home_tab)

        # Serial monitor frame
        self.serial_frame = ttk.Frame(self.serial_container)

        header_frame = ttk.Frame(self.serial_frame)
        header_frame.pack(fill='x')

        self.serial_header = ttk.Label(header_frame, text="Serial Monitor")
        self.serial_header.pack(side='left', padx=5)

        self.hide_console_button = ttk.Button(header_frame, text="Hide Serial Monitor", command=self.toggle_serial_monitor)
        self.hide_console_button.pack(side='right', padx=5, pady=5)

        self.console_home = scrolledtext.ScrolledText(self.serial_frame, height=5, state='disabled')
        self.console_home.pack(fill='x', expand=False)

        self.serial_frame.pack(fill='x', padx=10, pady=(5, 2))  # Slight padding under monitor

        # Dev note under serial monitor
        self.dev_note = ttk.Label(self.serial_container, text="Bosch XC-HWP", font=("Arial", 8), foreground="gray")
        self.dev_note.pack(side='left', anchor='w', padx=10, pady=(0, 5))

        # Show/hide toggle button (initially shown)
        self.show_console_button = ttk.Button(self.home_tab, text="Show Serial Monitor", command=self.toggle_serial_monitor)
        self.show_console_button.pack(side='right', anchor='se', pady=5, padx=10)

        self.serial_visible = False



    def check_serial_connection(self):
        if self.connected and self.serial_manager.ser:
            try:
                self.serial_manager.ser.in_waiting  # This triggers a check
            except (serial.SerialException, OSError):
                self.log("Device unplugged. Forcing disconnect.")
                self.force_disconnect()

        self.after(500, self.check_serial_connection)




    def force_disconnect(self):
        self.connected = False
        self.reading_info = False
        self.connect_button.config(text="Connect")
        self.status_dot.itemconfig(self.status_circle, fill="gray")
        self.log("Disconnected")

        self.tree.delete(*self.tree.get_children())
        self.selected_label.config(text="Select a device or PHY")
        self.speed_label.config(text="")

        self.port_combo.set('')
        self.port_combo['values'] = []

        # --- Clear Register tab fields ---
        self.phy_selector.set('')
        self.phy_selector['values'] = []

        self.register_id_entry.delete(0, 'end')
        self.register_value_var.set('')

        for var in self.bit_vars:
            var.set(0)

        self.reading_register = False





    def auto_scan_ports(self):
        ports = self.serial_manager.list_ports()

        current = self.port_combo.get()
        self.port_combo['values'] = ports

        # Keep current selection if still valid
        if current in ports:
            self.port_combo.set(current)
        elif ports:
            self.port_combo.current(0)
        else:
            self.port_combo.set('')

        self.after(500, self.auto_scan_ports)


    def setup_register_tab(self):
        # Full-width container
        container = ttk.Frame(self.register_tab)
        container.pack(fill='both', expand=True, pady=50)

        # Inner frame centered horizontally
        wrapper = ttk.Frame(container)
        wrapper.place(relx=0.5, rely=0.0, anchor='n')  # Center horizontally, top-aligned vertically

        # Top: PHY selection
        ttk.Label(wrapper, text="Select PHY:").grid(row=0, column=0, sticky='w')
        self.phy_selector = ttk.Combobox(wrapper, state='readonly', width=30)
        self.phy_selector.grid(row=0, column=1, sticky='w', pady=2)

        # Register ID below
        ttk.Label(wrapper, text="Register ID:").grid(row=1, column=0, sticky='w')
        self.register_id_entry = ttk.Entry(wrapper, width=10, validate='key')
        self.register_id_entry.grid(row=1, column=1, sticky='w', pady=2)
        self.register_id_entry['validatecommand'] = (self.register_id_entry.register(self.limit_length), '%P', 4)

        # Divider line
        ttk.Separator(wrapper, orient='horizontal').grid(row=2, column=0, columnspan=3, sticky='ew', pady=10)

        # Checkboxes for 16 bits
        bit_frame = ttk.Frame(wrapper)
        bit_frame.grid(row=3, column=0, columnspan=3, pady=(0, 10))

        self.bit_vars = [tk.IntVar() for _ in range(16)]
        for i in range(16):
            chk = ttk.Checkbutton(bit_frame, text=str(15 - i), variable=self.bit_vars[i], command=self.update_from_bits)
            chk.grid(row=0, column=i, padx=1)

        # Hex value + buttons
        ttk.Label(wrapper, text="Hex Value:").grid(row=4, column=0, sticky='e', padx=(0, 5))
        self.register_value_var = tk.StringVar()
        self.register_value_entry = ttk.Entry(wrapper, textvariable=self.register_value_var, width=10, validate='key')
        self.register_value_entry.grid(row=4, column=1, sticky='w')
        self.register_value_entry['validatecommand'] = (self.register_value_entry.register(self.limit_length), '%P', 4)


        button_frame = ttk.Frame(wrapper)
        button_frame.grid(row=4, column=2, sticky='w', padx=10)

        self.read_button = ttk.Button(button_frame, text="Read", command=self.read_register)
        self.read_button.pack(side='left', padx=5)

        self.write_button = ttk.Button(button_frame, text="Write", command=self.write_register)
        self.write_button.pack(side='left')

        # Sync hex ↔ bit states
        self.register_value_var.trace_add("write", lambda *args: self.update_bits_from_hex())

        # Serial Monitor Section (always visible in this tab)
        monitor_frame = ttk.Frame(self.register_tab)
        monitor_frame.pack(side='bottom', fill='x', padx=10, pady=10)

        header = ttk.Label(monitor_frame, text="Serial Monitor", font=("Arial", 10))
        header.pack(anchor='w')

        self.console_register = scrolledtext.ScrolledText(monitor_frame, height=5, state='disabled')
        self.console_register.pack(fill='x')



    def limit_length(self, new_value, max_len):
        return len(new_value) <= int(max_len)




    def read_register(self):
        phy = self.phy_selector.get()
        reg_id = self.register_id_entry.get().strip()

        if not phy or not reg_id:
            self.log("Please select a PHY and enter a Register ID.")
            return

        # Extract address only
        phy_addr = phy.split(" - ")[0].strip()

        command = f"READ_{phy_addr}_{reg_id}"
        self.send_command(command)

        self.reading_register = True
        self.expected_phy_addr = phy_addr
        self.register_poll_start_time = time.time()
        self.after(100, self.poll_register_response)

    def poll_register_response(self):
        if not self.reading_register:
            return

        if time.time() - self.register_poll_start_time > 0.5:
            self.log("Read timeout.")
            self.reading_register = False
            return

        lines = self.serial_manager.read_lines()
        if lines:
            for line in lines:
                self.log(line)

        if line.startswith("READ_RESPONSE"):
            parts = line.split()
            try:
                # Fixed: match actual values
                phy_val = parts[2].strip()
                reg_val = parts[4].strip()
                value = parts[6].strip()

                expected_phy = int(self.expected_phy_addr, 16 if 'x' in self.expected_phy_addr.lower() else 10)
                actual_phy = int(phy_val)

                expected_reg = int(self.register_id_entry.get().strip(), 16 if 'x' in self.register_id_entry.get().strip().lower() else 10)
                actual_reg = int(reg_val, 16 if 'x' in reg_val.lower() else 10)

                # self.log(f"Parsed → PHY: {actual_phy} vs {expected_phy}, REG: {actual_reg} vs {expected_reg}")

                if actual_phy == expected_phy and actual_reg == expected_reg:
                    self.register_value_var.set(value)
                    self.reading_register = False
                    return
            except Exception as e:
                self.log(f"Error parsing response: {e}")


        self.after(100, self.poll_register_response)




    def write_register(self):
        phy = self.phy_selector.get()
        reg_id = self.register_id_entry.get().strip()
        hex_val = self.register_value_var.get().strip()
        

        if not phy or not reg_id or not hex_val:
            self.log("Please fill in PHY, Register ID, and Hex Value.")
            return

        try:
            val_int = int(hex_val, 16)
            val_hex = f"{val_int:04X}"
        except ValueError:
            self.log("Invalid Register ID or Hex Value format.")
            return

        phy_addr = phy.split(" - ")[0].strip()
        command = f"WRITE_{phy_addr}_{reg_id}_{val_hex}"
        self.send_command(command)


    def update_bits_from_hex(self):
        try:
            hex_val = int(self.register_value_var.get(), 16)
            for i in range(16):
                self.bit_vars[15 - i].set((hex_val >> i) & 1)
        except ValueError:
            pass  # invalid hex input


    def update_from_bits(self):
        val = 0
        for i in range(16):
            val |= (self.bit_vars[15 - i].get() << i)
        self.register_value_var.set(f"{val:04X}")


    def toggle_serial_monitor(self):
        if self.serial_visible:
            self.serial_container.pack_forget()
            self.show_console_button.pack(side='right', anchor='se', pady=5, padx=10)
        else:
            self.show_console_button.pack_forget()
            self.serial_container.pack(side='bottom', fill='x')
        self.serial_visible = not self.serial_visible


    def connect_device(self):
        selected = self.port_combo.get()
        port = self.serial_manager.port_map.get(selected, selected)

        if not self.connected:
            if not port:
                self.log("No port selected")
                return
            try:
                self.serial_manager.connect(port)
                self.connected = True
                self.reading_info = True
                self.connect_button.config(text="Disconnect")
                self.log(f"Connected to {port}")
                self.send_command("INFO")
                self.after(100, self.read_info)
            except Exception as e:
                self.log(f"Connection error: {e}")
        else:
            try:
                if self.serial_manager.ser and self.serial_manager.ser.is_open:
                    self.serial_manager.ser.close()
                self.force_disconnect()


            except Exception as e:
                self.log(f"Disconnection error: {e}")




    def send_command(self, cmd):
        self.serial_manager.send(cmd)
        self.log(f"{cmd}")

    def read_info(self):
        if not self.reading_info:
            return

        lines = self.serial_manager.read_lines()
        if lines:
            self.log("\n".join(lines))
            if "END" in lines:
                filtered_info = [line for line in lines if line not in ("INFO", "END")]
                device_name = ""
                device_info = {}
                tree_info = []

                self.node_functions = {}
                current_label = None
                pending_functions = {}

                for line in filtered_info:
                    if line.startswith("Device:"):
                        device_name = line.replace("Device:", "").strip()
                        current_label = device_name
                    elif line.startswith("PHY"):
                        tree_info.append(line)
                        current_label = line.strip()
                    elif line.startswith("FUNCTION:"):
                        funcs = [f.strip() for f in line.replace("FUNCTION:", "").split(",")]
                        if current_label:
                            pending_functions[current_label] = funcs
                    elif ":" in line and not line.startswith("PHY"):
                        key, value = line.split(":", 1)
                        device_info[key.strip().upper()] = value.strip()

                self.device_info = device_info
                self.update_tree(device_name, tree_info, pending_functions)
                self.selected_label.config(text=device_name)
                self.display_device_info()
                self.status_dot.itemconfig(self.status_circle, fill="green")
                return

        self.after(100, self.read_info)







    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        for console in [getattr(self, 'console_home', None), getattr(self, 'console_register', None)]:
            if console:
                console['state'] = 'normal'
                console.insert('end', f"[{timestamp}] {message}\n")
                console['state'] = 'disabled'
                console.see('end')


    def update_tree(self, device_name, tree_lines, function_map):
        self.tree.delete(*self.tree.get_children())
        self.node_functions.clear()
        self.phy_addresses = {}

        device_node = self.tree.insert('', 'end', text=device_name, open=True)
        self.device_id = device_node
        self.node_functions[device_node] = function_map.get(device_name, [])

        phy_display_list = []

        for line in tree_lines:
            phy_address = ""
            phy_name = line
            for prefix in ("PHY1:", "PHY2:"):
                if line.startswith(prefix):
                    parts = line.split("-", 1)
                    if len(parts) == 2:
                        phy_address = parts[0].split(":")[1].strip()
                        phy_name = parts[1].strip()
            display_text = f"{phy_address} - {phy_name}" if phy_address else phy_name
            phy_id = self.tree.insert(device_node, 'end', text=phy_name)
            self.node_functions[phy_id] = function_map.get(line.strip(), [])
            if phy_address:
                self.phy_addresses[phy_id] = phy_address
            phy_display_list.append(display_text)

        self.phy_selector['values'] = phy_display_list
        if phy_display_list:
            self.phy_selector.current(0)






    def on_tree_select(self, event):
        selected_item = self.tree.selection()
        if selected_item:
            item_id = selected_item[0]
            item_text = self.tree.item(item_id, 'text')
            self.selected_label.config(text=item_text)

            parent = self.tree.parent(item_id)
            if parent == '':
                self.display_device_info()
            else:
                self.speed_label.config(text="")

            # Clear old buttons
            for widget in self.button_frame.winfo_children():
                widget.destroy()

            # Add new buttons based on functions
            for func in self.node_functions.get(item_id, []):
                if parent == '':  # device-level
                    command = f"DEV_{func.upper().replace(' ', '_')}"
                else:  # PHY-level
                    addr = self.phy_addresses.get(item_id, "")
                    command = f"{addr}_{func.upper().replace(' ', '_')}"
                btn = ttk.Button(self.button_frame, text=func, command=lambda c=command: self.send_command(c))
                btn.pack(side='left', padx=5)




    def display_device_info(self):
        info_lines = []
        if "CONTROLLER" in self.device_info:
            info_lines.append(f"Controller: {self.device_info['CONTROLLER']}")
        if "SOFTWARE VERSION" in self.device_info:
            info_lines.append(f"Software: {self.device_info['SOFTWARE VERSION']}")
        if "SPEED" in self.device_info:
            info_lines.append(f"Speed: {self.device_info['SPEED']}")
        self.speed_label.config(text="\n".join(info_lines))





if __name__ == "__main__":
    app = EthernetPHYApp()
    app.mainloop()
