# UDP Discovery constants and utilities
import socket
import ipaddress
try:
    import netifaces
    NETIFACES_AVAILABLE = True
except ImportError:
    NETIFACES_AVAILABLE = False
    
# UDP Discovery constants and utilities
UDP_SERVICE_DISCOVERY_PORT = 50001
UDP_CLIENT_DISCOVERY_PORT  = 4096
# Support multiple network ranges for cross-subnet discovery
DEFAULT_BROADCAST_NETWORKS = ['192.168.50.0']
HEARTBEAT_INTERVAL_SEC = 30
SERVICE_EXPIRY_MULTIPLIER = 3  # e.g., 3x heartbeat interval


def get_local_ip():
    """Get the local IP address of the machine"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't have to be reachable
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def get_network_interfaces():
    """Get all network interfaces and their IP addresses"""
    interfaces = []
    
    if NETIFACES_AVAILABLE:
        try:
            import netifaces
            for interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr.get('addr')
                        netmask = addr.get('netmask')
                        if ip and netmask and ip != '127.0.0.1':
                            interfaces.append({'interface': interface, 'ip': ip, 'netmask': netmask})
        except Exception as e:
            print(f"Error using netifaces: {e}")
    
    # Fallback if netifaces is not available or failed
    if not interfaces:
        local_ip = get_local_ip()
        if local_ip != '127.0.0.1':
            interfaces.append({'interface': 'default', 'ip': local_ip, 'netmask': '255.255.255.0'})
    
    return interfaces


def calculate_broadcast_address(ip, netmask):
    """Calculate broadcast address for given IP and netmask"""
    try:
        network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
        return str(network.broadcast_address)
    except Exception:
        # Fallback for common /24 networks
        ip_parts = ip.split('.')
        return f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.255"


def get_broadcast_addresses():
    """Get all broadcast addresses for discovery across multiple networks"""

    target_networks = []
    for base_network in DEFAULT_BROADCAST_NETWORKS:
        # Extract the first three octets (e.g., '192.168.50' from '192.168.50.0')
        base = '.'.join(base_network.split('.')[:-1])
        # Generate all subnets from .0 to .254
        for i in range(255):
            target_networks.append(f"{base}.{i}")

    return target_networks

def get_local_network():
    """Get the local network subnet"""
    local_ip = get_local_ip()
    if local_ip == '127.0.0.1':
        return None
    
    # Try to determine network from local interfaces
    interfaces = get_network_interfaces()
    for interface in interfaces:
        if interface['ip'] == local_ip:
            try:
                network = ipaddress.IPv4Network(f"{local_ip}/{interface['netmask']}", strict=False)
                return str(network.network_address) + '/' + str(network.prefixlen)
            except Exception:
                pass
    
    # Fallback: assume /24 network
    ip_parts = local_ip.split('.')
    return f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"


def get_cpu_load_average():
    """Get CPU load average as a single float value"""
    import os
    import sys
    import platform
    
    try:
        # Try Unix/Linux/macOS first
        if hasattr(os, 'getloadavg'):
            # Unix/Linux/macOS - return 1-minute load average
            load_avg = os.getloadavg()[0]
            # Convert to percentage (assuming load average of 1.0 = 100% on single core)
            import multiprocessing
            cpu_count = multiprocessing.cpu_count()
            return min((load_avg / cpu_count) * 100, 100.0)
        
        # Windows implementations
        elif platform.system() == 'Windows':
            # Try multiple methods for Windows
            
            # Method 1: Try psutil (most reliable)
            try:
                import psutil
                # Use a shorter interval to avoid blocking in PyInstaller
                cpu_percent = psutil.cpu_percent(interval=0.1)
                if cpu_percent > 0:
                    return float(cpu_percent)
            except (ImportError, Exception):
                pass
            
            # Method 2: Try WMI (Windows Management Instrumentation)
            try:
                import subprocess
                import json
                
                # Use PowerShell to get CPU usage
                cmd = [
                    'powershell', '-Command',
                    'Get-Counter "\\Processor(_Total)\\% Processor Time" | Select-Object -ExpandProperty CounterSamples | Select-Object -ExpandProperty CookedValue'
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout.strip():
                    cpu_usage = float(result.stdout.strip())
                    return min(max(cpu_usage, 0.0), 100.0)
            except (Exception, subprocess.TimeoutExpired):
                pass
            
            # Method 3: Try Windows Performance Toolkit
            try:
                import subprocess
                cmd = ['wmic', 'cpu', 'get', 'loadpercentage', '/value']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'LoadPercentage=' in line:
                            cpu_usage = float(line.split('=')[1].strip())
                            return min(max(cpu_usage, 0.0), 100.0)
            except (Exception, subprocess.TimeoutExpired):
                pass
            
            # Method 4: Try reading from registry or system files
            try:
                import subprocess
                # Get processor usage using typeperf
                cmd = ['typeperf', '\\Processor(_Total)\\% Processor Time', '-sc', '1']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if '\\Processor(_Total)\\% Processor Time' in line:
                            parts = line.split(',')
                            if len(parts) >= 2:
                                try:
                                    cpu_str = parts[-1].strip().replace('"', '')
                                    cpu_usage = float(cpu_str)
                                    return min(max(cpu_usage, 0.0), 100.0)
                                except ValueError:
                                    continue
            except (Exception, subprocess.TimeoutExpired):
                pass
        
        # Fallback for other systems or if all methods fail
        return 0.0
        
    except Exception as e:
        # Log the error if possible, but don't break the application
        try:
            print(f"Warning: Could not get CPU load average: {e}")
        except:
            pass
        return 0.0

def test_cpu_load_methods():
    """Test different CPU load measurement methods for debugging PyInstaller issues"""
    import platform
    import os
    
    print(f"Platform: {platform.system()}")
    print(f"Python executable: {os.path.abspath(os.sys.executable) if hasattr(os, 'sys') else 'unknown'}")
    
    methods_tested = []
    
    # Test Method 1: os.getloadavg()
    try:
        if hasattr(os, 'getloadavg'):
            load_avg = os.getloadavg()[0]
            import multiprocessing
            cpu_count = multiprocessing.cpu_count()
            result = min((load_avg / cpu_count) * 100, 100.0)
            methods_tested.append(f"os.getloadavg(): {result:.2f}%")
        else:
            methods_tested.append("os.getloadavg(): Not available")
    except Exception as e:
        methods_tested.append(f"os.getloadavg(): Error - {e}")
    
    # Test Method 2: psutil
    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=0.1)
        methods_tested.append(f"psutil.cpu_percent(): {cpu_percent:.2f}%")
    except ImportError:
        methods_tested.append("psutil: Not available (ImportError)")
    except Exception as e:
        methods_tested.append(f"psutil: Error - {e}")
    
    # Test Method 3: PowerShell (Windows)
    if platform.system() == 'Windows':
        try:
            import subprocess
            cmd = [
                'powershell', '-Command',
                'Get-Counter "\\Processor(_Total)\\% Processor Time" | Select-Object -ExpandProperty CounterSamples | Select-Object -ExpandProperty CookedValue'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                cpu_usage = float(result.stdout.strip())
                methods_tested.append(f"PowerShell Get-Counter: {cpu_usage:.2f}%")
            else:
                methods_tested.append(f"PowerShell Get-Counter: Failed (return code: {result.returncode})")
        except Exception as e:
            methods_tested.append(f"PowerShell Get-Counter: Error - {e}")
        
        # Test Method 4: WMIC
        try:
            import subprocess
            cmd = ['wmic', 'cpu', 'get', 'loadpercentage', '/value']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'LoadPercentage=' in line:
                        cpu_usage = float(line.split('=')[1].strip())
                        methods_tested.append(f"WMIC: {cpu_usage:.2f}%")
                        break
                else:
                    methods_tested.append("WMIC: No LoadPercentage found")
            else:
                methods_tested.append(f"WMIC: Failed (return code: {result.returncode})")
        except Exception as e:
            methods_tested.append(f"WMIC: Error - {e}")
    
    # Test the main function
    try:
        main_result = get_cpu_load_average()
        methods_tested.append(f"get_cpu_load_average(): {main_result:.2f}%")
    except Exception as e:
        methods_tested.append(f"get_cpu_load_average(): Error - {e}")
    
    print("\nCPU Load Test Results:")
    for i, method in enumerate(methods_tested, 1):
        print(f"  {i}. {method}")
    
    return methods_tested
