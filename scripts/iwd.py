#!/usr/bin/env python3
"""
iwd-tui - Professional TUI for iwd wireless management
A clean, modern implementation in a single file
"""

import curses
import subprocess
import asyncio
import json
import logging
import sys
import time
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# === Data Models ===
class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"

@dataclass
class NetworkDevice:
    name: str
    type: str
    powered: bool
    connected: bool
    network: str = ""
    address: str = ""

@dataclass
class WirelessNetwork:
    ssid: str
    security: str
    signal_strength: int
    connected: bool = False
    known: bool = False
    frequency: str = ""

# === Core Network Manager ===
class NetworkManager:
    def __init__(self):
        self.logger = self._setup_logging()
        self.devices: List[NetworkDevice] = []
        self.networks: List[WirelessNetwork] = []
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger('iwd-tui')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    def run_command(self, cmd: List[str], input_text: str = None) -> Tuple[bool, str]:
        """Execute system command with error handling"""
        try:
            result = subprocess.run(
                cmd,
                input=input_text,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0, result.stdout
        except Exception as e:
            self.logger.error(f"Command failed: {' '.join(cmd)} - {e}")
            return False, str(e)

    def get_devices(self) -> List[NetworkDevice]:
        """Get network devices"""
        success, output = self.run_command(["iwctl", "device", "list"])
        devices = []
        
        if success:
            for line in output.split('\n')[3:]:
                if line.strip() and not line.startswith('-'):
                    parts = line.split()
                    if len(parts) >= 3:
                        devices.append(NetworkDevice(
                            name=parts[0],
                            type=parts[1],
                            powered='on' in line,
                            connected='connected' in line,
                            network=parts[3] if len(parts) > 3 and 'connected' in line else ""
                        ))
        
        self.devices = devices
        return devices

    def scan_networks(self, device: str = None) -> List[WirelessNetwork]:
        """Scan for wireless networks"""
        if not device and self.devices:
            for dev in self.devices:
                if dev.type == "station" and dev.powered:
                    device = dev.name
                    break
        
        if not device:
            return []

        # Start scan
        self.run_command(["iwctl", "station", device, "scan"])
        time.sleep(2)  # Wait for results

        # Get networks
        success, output = self.run_command(["iwctl", "station", device, "get-networks"])
        networks = []
        
        if success:
            for line in output.split('\n')[4:]:
                if line.strip() and not line.startswith('-'):
                    parts = line.split()
                    if parts:
                        ssid = parts[0]
                        security = "secured" if "PSK" in line or "802.1X" in line else "open"
                        connected = ">" in line
                        
                        # Parse signal strength
                        signal = 50  # Default
                        for part in parts:
                            if "dBm" in part:
                                try:
                                    signal = abs(int(part.replace("dBm", "").strip()))
                                except:
                                    pass
                        
                        networks.append(WirelessNetwork(
                            ssid=ssid,
                            security=security,
                            signal_strength=signal,
                            connected=connected
                        ))
        
        self.networks = networks
        return networks

    def connect_to_network(self, device: str, ssid: str, password: str = None) -> Tuple[bool, str]:
        """Connect to a wireless network"""
        cmd = ["iwctl", "station", device, "connect", ssid]
        success, output = self.run_command(cmd, password)
        
        if success:
            # Verify connection
            time.sleep(2)
            self.get_devices()
            for dev in self.devices:
                if dev.connected and dev.network == ssid:
                    return True, f"Connected to {ssid}"
            return False, "Connection verification failed"
        else:
            return False, f"Connection failed: {output}"

    def disconnect_network(self, device: str) -> Tuple[bool, str]:
        """Disconnect from current network"""
        success, output = self.run_command(["iwctl", "station", device, "disconnect"])
        return success, "Disconnected" if success else f"Disconnect failed: {output}"

    def toggle_device_power(self, device: str) -> bool:
        """Toggle device power state"""
        for dev in self.devices:
            if dev.name == device:
                new_state = "off" if dev.powered else "on"
                success, _ = self.run_command([
                    "iwctl", "device", device, "set-property", "Powered", new_state
                ])
                return success
        return False

# === UI Components ===
class UITheme:
    """UI color and style configuration"""
    COLORS = {
        'border': 1,
        'title': 2,
        'selected': 3,
        'status_connected': 4,
        'status_disconnected': 5,
        'error': 6
    }
    
    @classmethod
    def init_colors(cls):
        """Initialize color pairs"""
        curses.start_color()
        curses.use_default_colors()
        
        # Professional color scheme
        curses.init_pair(1, curses.COLOR_CYAN, -1)      # Border
        curses.init_pair(2, curses.COLOR_YELLOW, -1)    # Title  
        curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Selected
        curses.init_pair(4, curses.COLOR_GREEN, -1)     # Connected
        curses.init_pair(5, curses.COLOR_RED, -1)       # Disconnected
        curses.init_pair(6, curses.COLOR_RED, -1)       # Error

class ListView:
    """Generic list view component"""
    def __init__(self, y: int, x: int, width: int, height: int):
        self.y = y
        self.x = x
        self.width = width
        self.height = height
        self.items = []
        self.selected_index = 0
        self.scroll_offset = 0
    
    def draw(self, stdscr, items: List[str], selected_index: int):
        """Draw the list view"""
        self.items = items
        self.selected_index = selected_index
        
        # Adjust scroll
        if selected_index < self.scroll_offset:
            self.scroll_offset = selected_index
        elif selected_index >= self.scroll_offset + self.height:
            self.scroll_offset = selected_index - self.height + 1
        
        # Draw visible items
        visible_items = items[self.scroll_offset:self.scroll_offset + self.height]
        
        for i, item in enumerate(visible_items):
            y_pos = self.y + i
            is_selected = (i + self.scroll_offset) == selected_index
            
            # Truncate item to fit width
            display_text = item.ljust(self.width)[:self.width]
            
            if is_selected:
                stdscr.attron(curses.color_pair(UITheme.COLORS['selected']))
                stdscr.addstr(y_pos, self.x, display_text)
                stdscr.attroff(curses.color_pair(UITheme.COLORS['selected']))
            else:
                stdscr.addstr(y_pos, self.x, display_text)
        
        # Scroll indicators
        if self.scroll_offset > 0:
            stdscr.addstr(self.y, self.x + self.width - 1, "↑")
        if len(items) > self.scroll_offset + self.height:
            stdscr.addstr(self.y + self.height - 1, self.x + self.width - 1, "↓")

class Dialog:
    """Dialog box component"""
    @staticmethod
    def message(stdscr, title: str, message: str):
        """Show message dialog"""
        lines = message.split('\n')
        width = max(len(line) for line in lines) + 4
        width = max(width, len(title) + 4)
        height = len(lines) + 6
        
        screen_height, screen_width = stdscr.getmaxyx()
        y = (screen_height - height) // 2
        x = (screen_width - width) // 2
        
        # Draw box
        stdscr.attron(curses.color_pair(UITheme.COLORS['border']))
        stdscr.addstr(y, x, "┌" + "─" * (width - 2) + "┐")
        for i in range(1, height - 1):
            stdscr.addstr(y + i, x, "│" + " " * (width - 2) + "│")
        stdscr.addstr(y + height - 1, x, "└" + "─" * (width - 2) + "┘")
        
        # Title
        stdscr.addstr(y, x + (width - len(title)) // 2 - 1, f" {title} ")
        stdscr.attroff(curses.color_pair(UITheme.COLORS['border']))
        
        # Message
        for i, line in enumerate(lines):
            stdscr.addstr(y + 3 + i, x + 2, line)
        
        # Button
        stdscr.addstr(y + height - 3, x + (width - 8) // 2, "[ OK ]", curses.A_REVERSE)
        stdscr.refresh()
        
        # Wait for input
        while True:
            key = stdscr.getch()
            if key in [curses.KEY_ENTER, 10, 13, 27, ord(' ')]:
                break

    @staticmethod
    def input(stdscr, title: str, prompt: str, password: bool = False) -> Optional[str]:
        """Show input dialog"""
        width = max(len(title), len(prompt)) + 10
        height = 8
        
        screen_height, screen_width = stdscr.getmaxyx()
        y = (screen_height - height) // 2
        x = (screen_width - width) // 2
        
        # Draw box
        stdscr.attron(curses.color_pair(UITheme.COLORS['border']))
        stdscr.addstr(y, x, "┌" + "─" * (width - 2) + "┐")
        for i in range(1, height - 1):
            stdscr.addstr(y + i, x, "│" + " " * (width - 2) + "│")
        stdscr.addstr(y + height - 1, x, "└" + "─" * (width - 2) + "┘")
        
        # Title
        stdscr.addstr(y, x + (width - len(title)) // 2 - 1, f" {title} ")
        stdscr.attroff(curses.color_pair(UITheme.COLORS['border']))
        
        # Prompt
        stdscr.addstr(y + 2, x + 2, prompt)
        
        # Input field
        input_text = ""
        cursor_pos = 0
        
        while True:
            # Clear input area
            stdscr.addstr(y + 4, x + 2, " " * (width - 4))
            
            # Display text (mask if password)
            display_text = "*" * len(input_text) if password else input_text
            if len(display_text) > width - 6:
                display_text = "..." + display_text[-(width - 6):]
            
            stdscr.addstr(y + 4, x + 2, display_text)
            stdscr.move(y + 4, x + 2 + min(cursor_pos, width - 6))
            
            key = stdscr.getch()
            
            if key in [curses.KEY_ENTER, 10, 13]:
                return input_text
            elif key == 27:  # ESC
                return None
            elif key in [curses.KEY_BACKSPACE, 127]:
                if cursor_pos > 0:
                    input_text = input_text[:cursor_pos-1] + input_text[cursor_pos:]
                    cursor_pos -= 1
            elif key == curses.KEY_LEFT:
                cursor_pos = max(0, cursor_pos - 1)
            elif key == curses.KEY_RIGHT:
                cursor_pos = min(len(input_text), cursor_pos + 1)
            elif 32 <= key <= 126:
                input_text = input_text[:cursor_pos] + chr(key) + input_text[cursor_pos:]
                cursor_pos += 1

# === Main Application ===
class IwdTUI:
    """Main TUI Application"""
    
    def __init__(self):
        self.network_mgr = NetworkManager()
        self.current_screen = "main"
        self.selected_index = 0
        self.scroll_offset = 0
        self.connection_status = "disconnected"
        self.active_connection = ""
        self.auto_refresh = True
        self.last_scan = 0
        
    def draw_header(self, stdscr, title: str):
        """Draw application header"""
        height, width = stdscr.getmaxyx()
        
        # Clear header area
        stdscr.addstr(0, 0, " " * width)
        
        # Title
        stdscr.attron(curses.color_pair(UITheme.COLORS['title']))
        stdscr.addstr(0, 2, f" iwd-tui - {title} ")
        stdscr.attroff(curses.color_pair(UITheme.COLORS['title']))
        
        # Status
        status_color = UITheme.COLORS['status_connected'] if "connected" in self.connection_status else UITheme.COLORS['status_disconnected']
        stdscr.attron(curses.color_pair(status_color))
        status_text = f"Status: {self.connection_status}"
        stdscr.addstr(0, width - len(status_text) - 2, status_text)
        stdscr.attroff(curses.color_pair(status_color))
        
        # Separator
        stdscr.addstr(1, 0, "═" * width)
    
    def draw_footer(self, stdscr, hints: List[str]):
        """Draw application footer"""
        height, width = stdscr.getmaxyx()
        footer_text = " • ".join(hints)
        stdscr.addstr(height - 1, 2, footer_text[:width-4])
    
    def draw_main_screen(self, stdscr):
        """Draw main menu screen"""
        height, width = stdscr.getmaxyx()
        
        self.draw_header(stdscr, "Wireless Network Manager")
        
        menu_items = [
            "📶 Scan and Connect to Networks",
            "🔌 Network Devices", 
            "⭐ Saved Networks",
            "⚡ Radio Power Management",
            "ℹ️  Connection Information",
            "❌ Quit"
        ]
        
        # Center the menu
        menu_height = len(menu_items)
        menu_width = max(len(item) for item in menu_items) + 4
        start_y = (height - menu_height) // 2
        start_x = (width - menu_width) // 2
        
        list_view = ListView(start_y, start_x, menu_width, menu_height)
        list_view.draw(stdscr, menu_items, self.selected_index)
        
        self.draw_footer(stdscr, ["↑↓: Navigate", "Enter: Select", "Q: Quit"])
    
    def draw_network_list_screen(self, stdscr):
        """Draw network list screen"""
        height, width = stdscr.getmaxyx()
        
        self.draw_header(stdscr, "Available Networks")
        
        # Get networks
        current_time = time.time()
        if self.auto_refresh and (current_time - self.last_scan > 10):
            self.network_mgr.scan_networks()
            self.last_scan = current_time
        
        # Format network list
        display_items = []
        for network in self.network_mgr.networks:
            connected_icon = "✓" if network.connected else " "
            security_icon = "🔒" if network.security == "secured" else "🔓"
            
            # Signal strength bars
            signal_bars = self.get_signal_bars(network.signal_strength)
            
            item = f"{connected_icon} {network.ssid:<20} {security_icon} {signal_bars}"
            display_items.append(item)
        
        if not display_items:
            display_items = ["No networks found", "Press R to rescan"]
        
        # Add actions
        display_items.extend(["", "🔄 Rescan Networks", "🔙 Back to Main Menu"])
        
        list_view = ListView(3, 2, width - 4, height - 6)
        list_view.draw(stdscr, display_items, self.selected_index)
        
        self.draw_footer(stdscr, [
            "↑↓: Navigate", 
            "Enter: Connect", 
            "R: Rescan", 
            "B: Back"
        ])
    
    def get_signal_bars(self, strength: int) -> str:
        """Convert signal strength to visual bars"""
        if strength > 80:
            return "|||||"
        elif strength > 60:
            return "|||| "
        elif strength > 40:
            return "|||  "
        elif strength > 20:
            return "||   "
        else:
            return "|    "
    
    def draw_device_list_screen(self, stdscr):
        """Draw device list screen"""
        height, width = stdscr.getmaxyx()
        
        self.draw_header(stdscr, "Network Devices")
        
        # Format device list
        display_items = []
        for device in self.network_mgr.devices:
            status = "ON" if device.powered else "OFF"
            connected = "✓" if device.connected else " "
            device_type = "WiFi" if device.type == "station" else "Ethernet"
            
            item = f"{connected} {device.name} ({device_type}) - Power: {status}"
            if device.connected and device.network:
                item += f" - Connected to: {device.network}"
            
            display_items.append(item)
        
        if not display_items:
            display_items = ["No devices found"]
        
        display_items.extend(["", "🔙 Back to Main Menu"])
        
        list_view = ListView(3, 2, width - 4, height - 6)
        list_view.draw(stdscr, display_items, self.selected_index)
        
        self.draw_footer(stdscr, [
            "↑↓: Navigate", 
            "Enter: Toggle Power", 
            "B: Back"
        ])
    
    def handle_main_screen_input(self, stdscr, key: int) -> bool:
        """Handle input on main screen"""
        menu_count = 6  # Number of menu items
        
        if key == curses.KEY_UP:
            self.selected_index = (self.selected_index - 1) % menu_count
        elif key == curses.KEY_DOWN:
            self.selected_index = (self.selected_index + 1) % menu_count
        elif key in [curses.KEY_ENTER, 10, 13]:
            if self.selected_index == 0:  # Scan and Connect
                self.current_screen = "networks"
                self.selected_index = 0
            elif self.selected_index == 1:  # Devices
                self.current_screen = "devices"
                self.selected_index = 0
                self.network_mgr.get_devices()
            elif self.selected_index == 5:  # Quit
                return False
        elif key in [ord('q'), ord('Q')]:
            return False
        
        return True
    
    def handle_network_list_input(self, stdscr, key: int):
        """Handle input on network list screen"""
        network_count = len(self.network_mgr.networks)
        total_items = network_count + 3  # networks + blank + actions
        
        if key == curses.KEY_UP:
            self.selected_index = max(0, self.selected_index - 1)
        elif key == curses.KEY_DOWN:
            self.selected_index = min(total_items - 1, self.selected_index + 1)
        elif key in [curses.KEY_ENTER, 10, 13]:
            if self.selected_index < network_count:
                # Connect to network
                network = self.network_mgr.networks[self.selected_index]
                if network.security == "secured":
                    password = Dialog.input(stdscr, "Password", f"Enter password for {network.ssid}:", password=True)
                    if password:
                        # Find a wireless device
                        device = None
                        for dev in self.network_mgr.devices:
                            if dev.type == "station" and dev.powered:
                                device = dev.name
                                break
                        
                        if device:
                            success, message = self.network_mgr.connect_to_network(device, network.ssid, password)
                            Dialog.message(stdscr, "Connection Result", message)
                else:
                    # Open network
                    device = None
                    for dev in self.network_mgr.devices:
                        if dev.type == "station" and dev.powered:
                            device = dev.name
                            break
                    
                    if device:
                        success, message = self.network_mgr.connect_to_network(device, network.ssid)
                        Dialog.message(stdscr, "Connection Result", message)
            
            elif self.selected_index == network_count + 1:  # Rescan
                self.network_mgr.scan_networks()
                self.last_scan = time.time()
            
            elif self.selected_index == network_count + 2:  # Back
                self.current_screen = "main"
                self.selected_index = 0
        
        elif key in [ord('r'), ord('R')]:
            self.network_mgr.scan_networks()
            self.last_scan = time.time()
        elif key in [ord('b'), ord('B')]:
            self.current_screen = "main"
            self.selected_index = 0
    
    def handle_device_list_input(self, stdscr, key: int):
        """Handle input on device list screen"""
        device_count = len(self.network_mgr.devices)
        total_items = device_count + 2  # devices + blank + back
        
        if key == curses.KEY_UP:
            self.selected_index = max(0, self.selected_index - 1)
        elif key == curses.KEY_DOWN:
            self.selected_index = min(total_items - 1, self.selected_index + 1)
        elif key in [curses.KEY_ENTER, 10, 13]:
            if self.selected_index < device_count:
                # Toggle device power
                device = self.network_mgr.devices[self.selected_index]
                if self.network_mgr.toggle_device_power(device.name):
                    self.network_mgr.get_devices()  # Refresh device list
            elif self.selected_index == device_count + 1:  # Back
                self.current_screen = "main"
                self.selected_index = 0
        
        elif key in [ord('b'), ord('B')]:
            self.current_screen = "main"
            self.selected_index = 0
    
    def update_status(self):
        """Update connection status"""
        connected = False
        connection_info = ""
        
        for device in self.network_mgr.devices:
            if device.connected:
                connected = True
                connection_info = f"{device.network} on {device.name}"
                break
        
        self.connection_status = f"connected to {connection_info}" if connected else "disconnected"
        self.active_connection = connection_info if connected else ""
    
    def run(self, stdscr):
        """Main application loop"""
        # Setup
        curses.curs_set(0)
        stdscr.keypad(True)
        stdscr.timeout(100)  # Non-blocking input
        UITheme.init_colors()
        
        # Initial data load
        self.network_mgr.get_devices()
        self.network_mgr.scan_networks()
        self.update_status()
        
        running = True
        while running:
            try:
                # Update status periodically
                self.update_status()
                
                # Draw current screen
                stdscr.clear()
                
                if self.current_screen == "main":
                    self.draw_main_screen(stdscr)
                elif self.current_screen == "networks":
                    self.draw_network_list_screen(stdscr)
                elif self.current_screen == "devices":
                    self.draw_device_list_screen(stdscr)
                
                stdscr.refresh()
                
                # Handle input
                key = stdscr.getch()
                
                if key == -1:
                    continue  # No input
                
                if self.current_screen == "main":
                    running = self.handle_main_screen_input(stdscr, key)
                elif self.current_screen == "networks":
                    self.handle_network_list_input(stdscr, key)
                elif self.current_screen == "devices":
                    self.handle_device_list_input(stdscr, key)
                
                # Refresh data on user interaction
                if key != -1:
                    self.network_mgr.get_devices()
                    self.update_status()
                    
            except Exception as e:
                logging.error(f"UI error: {e}")
                Dialog.message(stdscr, "Error", f"Application error: {e}")

def check_dependencies():
    """Check if required dependencies are available"""
    try:
        subprocess.run(["iwctl", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def main():
    """Application entry point"""
    # Check dependencies
    if not check_dependencies():
        print("Error: iwd (iwctl) is not installed or not in PATH")
        print("Please install iwd package:")
        print("  Arch: sudo pacman -S iwd")
        print("  Debian/Ubuntu: sudo apt install iwd")
        print("  Fedora: sudo dnf install iwd")
        sys.exit(1)
    
    # Check privileges
    if os.geteuid() != 0:
        print("Warning: Running without root privileges. Some operations may fail.")
        print("Consider running with sudo for full functionality.")
        time.sleep(2)
    
    # Run application
    app = IwdTUI()
    try:
        curses.wrapper(app.run)
    except KeyboardInterrupt:
        print("\nApplication terminated by user")
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
