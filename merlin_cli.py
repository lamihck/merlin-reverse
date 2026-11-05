#!/usr/bin/env python3
"""
Merlin Speaker CLI
==================

Command-line interface for Merlin speaker communication.

Usage:
    python3 merlin_cli.py <command> [options]

Commands:
    ping <ip>                    - Test connection
    status <ip>                  - Get speaker status
    storage <ip>                 - Get storage info
    battery <ip>                 - Get battery status
    send <ip> <file> [type]      - Send file (type: media|config|playlist)
    info <file>                  - Show file info and SHA256
"""

import sys
import argparse
from pathlib import Path

from merlin_protocol import (
    MerlinClient, MerlinCommands, MerlinResponse,
    FileType, MerlinCommand
)


def cmd_ping(args):
    """Test connection with PING"""
    client = MerlinClient(args.ip, args.port)
    
    print(f"Connecting to {args.ip}:{args.port}...")
    if not client.connect():
        print("❌ Connection failed")
        return 1
    
    print("✅ Connected")
    print("\nSending PING...")
    
    packet = MerlinCommands.ping()
    if not client.send_packet(packet):
        print("❌ Send failed")
        client.disconnect()
        return 1
    
    response = client.receive_packet()
    if response and response.cmd_id == MerlinCommand.PING:
        print("✅ PONG received")
        result = 0
    else:
        print("❌ No response")
        result = 1
    
    client.disconnect()
    return result


def cmd_status(args):
    """Get speaker status"""
    client = MerlinClient(args.ip, args.port)
    
    print(f"Connecting to {args.ip}:{args.port}...")
    if not client.connect():
        print("❌ Connection failed")
        return 1
    
    print("✅ Connected")
    print("\nGetting status...")
    
    packet = MerlinCommands.get_status()
    if not client.send_packet(packet):
        print("❌ Send failed")
        client.disconnect()
        return 1
    
    response = client.receive_packet()
    if response:
        status = MerlinResponse.parse_status(response)
        print("✅ Status received:")
        print(f"   Mode:    0x{status['mode']:02X}")
        print(f"   Flags:   0x{status['flags']:02X}")
        print(f"   Unknown: 0x{status['unknown']:04X}")
        result = 0
    else:
        print("❌ No response")
        result = 1
    
    client.disconnect()
    return result


def cmd_storage(args):
    """Get storage information"""
    client = MerlinClient(args.ip, args.port)
    
    print(f"Connecting to {args.ip}:{args.port}...")
    if not client.connect():
        print("❌ Connection failed")
        return 1
    
    print("✅ Connected")
    print("\nGetting storage info...")
    
    packet = MerlinCommands.get_storage_info()
    if not client.send_packet(packet):
        print("❌ Send failed")
        client.disconnect()
        return 1
    
    response = client.receive_packet()
    if response:
        info = MerlinResponse.parse_storage_info(response)
        print("✅ Storage info:")
        print(f"   State:       0x{info['state']:04X}")
        print(f"   Free blocks: {info['free_blocks']}")
        print(f"   Free space:  {info['free_mb']:.1f} MB")
        result = 0
    else:
        print("❌ No response")
        result = 1
    
    client.disconnect()
    return result


def cmd_battery(args):
    """Get battery status"""
    client = MerlinClient(args.ip, args.port)
    
    print(f"Connecting to {args.ip}:{args.port}...")
    if not client.connect():
        print("❌ Connection failed")
        return 1
    
    print("✅ Connected")
    print("\nGetting battery status...")
    
    packet = MerlinCommands.get_battery()
    if not client.send_packet(packet):
        print("❌ Send failed")
        client.disconnect()
        return 1
    
    response = client.receive_packet()
    if response:
        battery = MerlinResponse.parse_battery(response)
        status_str = "Charging" if battery['status'] == 0x01 else "Idle"
        print("✅ Battery status:")
        print(f"   Level:  {battery['percentage']}%")
        print(f"   Status: {status_str}")
        result = 0
    else:
        print("❌ No response")
        result = 1
    
    client.disconnect()
    return result


def cmd_send(args):
    """Send file to speaker"""
    file_path = Path(args.file)
    
    if not file_path.exists():
        print(f"❌ File not found: {args.file}")
        return 1
    
    # Determine file type
    type_map = {
        'media': FileType.MEDIA,
        'config': FileType.CONFIG,
        'playlist': FileType.PLAYLIST
    }
    file_type = type_map.get(args.type.lower(), FileType.MEDIA)
    
    # Load file
    print(f"Loading file: {file_path.name}")
    with open(file_path, 'rb') as f:
        file_data = f.read()
    
    print(f"   Size: {len(file_data)} bytes")
    print(f"   Type: {args.type}")
    print(f"   Chunk size: {args.chunk_size} bytes")
    
    # Connect
    client = MerlinClient(args.ip, args.port)
    print(f"\nConnecting to {args.ip}:{args.port}...")
    if not client.connect():
        print("❌ Connection failed")
        return 1
    
    print("✅ Connected")
    
    # Send file
    print(f"\nSending file...")
    if client.send_file(file_path.name, file_data, file_type, chunk_size=args.chunk_size):
        print("✅ File sent successfully")
        result = 0
    else:
        print("❌ File send failed")
        result = 1
    
    client.disconnect()
    return result


def cmd_info(args):
    """Show file information"""
    import hashlib
    
    file_path = Path(args.file)
    
    if not file_path.exists():
        print(f"❌ File not found: {args.file}")
        return 1
    
    # Load file
    with open(file_path, 'rb') as f:
        file_data = f.read()
    
    # Calculate hashes
    md5 = hashlib.md5(file_data).hexdigest()
    sha256 = hashlib.sha256(file_data).hexdigest()
    
    print(f"File: {file_path.name}")
    print(f"Size: {len(file_data)} bytes ({len(file_data)/1024:.1f} KB)")
    print(f"\nHashes:")
    print(f"  MD5:    {md5}")
    print(f"  SHA256: {sha256}")
    
    # Show what the FILE_INIT packet would look like
    from merlin_protocol import MerlinCommands
    packet = MerlinCommands.file_init(file_path.name, len(file_data), file_data, FileType.MEDIA)
    
    print(f"\nFILE_INIT packet preview:")
    print(f"  Length:  {packet.length} bytes")
    print(f"  CMD_ID:  0x{packet.cmd_id:02X}")
    print(f"  CRC:     0x{packet.crc:08X}")
    print(f"  Raw:     {packet.to_bytes()[:50].hex()}...")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Merlin Speaker CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ping 192.168.4.1
  %(prog)s status 192.168.4.1
  %(prog)s storage 192.168.4.1
  %(prog)s battery 192.168.4.1
  %(prog)s send 192.168.4.1 story.mp3
  %(prog)s send 192.168.4.1 playlist.json playlist
  %(prog)s info story.mp3
        """
    )
    
    parser.add_argument('--port', type=int, default=50000,
                       help='Speaker port (default: 50000)')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # ping
    ping_parser = subparsers.add_parser('ping', help='Test connection')
    ping_parser.add_argument('ip', help='Speaker IP address')
    
    # status
    status_parser = subparsers.add_parser('status', help='Get speaker status')
    status_parser.add_argument('ip', help='Speaker IP address')
    
    # storage
    storage_parser = subparsers.add_parser('storage', help='Get storage info')
    storage_parser.add_argument('ip', help='Speaker IP address')
    
    # battery
    battery_parser = subparsers.add_parser('battery', help='Get battery status')
    battery_parser.add_argument('ip', help='Speaker IP address')
    
    # send
    send_parser = subparsers.add_parser('send', help='Send file')
    send_parser.add_argument('ip', help='Speaker IP address')
    send_parser.add_argument('file', help='File to send')
    send_parser.add_argument('type', nargs='?', default='media',
                            choices=['media', 'config', 'playlist'],
                            help='File type (default: media)')
    send_parser.add_argument('--chunk-size', type=int, default=1440,
                            help='Data chunk size in bytes (default: 1440)')
    
    # info
    info_parser = subparsers.add_parser('info', help='Show file info')
    info_parser.add_argument('file', help='File to analyze')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Execute command
    commands = {
        'ping': cmd_ping,
        'status': cmd_status,
        'storage': cmd_storage,
        'battery': cmd_battery,
        'send': cmd_send,
        'info': cmd_info
    }
    
    return commands[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
