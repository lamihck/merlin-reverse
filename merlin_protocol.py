#!/usr/bin/env python3
"""
Merlin Protocol Library
=======================

Implementation of the Merlin speaker communication protocol.

Protocol Format:
    [Length:1][CMD_ID:1][Payload...][CRC32:4 LE]

CRC32 Algorithm:
    - Init: 0xFFFFFFFF
    - Polynomial: 0x04C11DB7
    - XOR out: 0x00000000
    - Calculated on: CMD_ID + Payload (not Length)

Author: Reverse-engineered from pcap analysis
Date: 2025-11-25
"""

import struct
import hashlib
import socket
from typing import Optional, Tuple, List
from enum import IntEnum
from dataclasses import dataclass


class MerlinCommand(IntEnum):
    """Merlin protocol command IDs"""
    FILE_INIT = 0x01
    PING = 0x02
    STATUS = 0x03
    STORAGE_INFO = 0x04
    CMD_05 = 0x05
    CMD_08 = 0x08
    END_SESSION = 0x09
    BATTERY = 0x0E
    CMD_1B = 0x1B
    CMD_1D = 0x1D
    CMD_1E = 0x1E
    FILE_DESCRIPTOR = 0x1F


class FileType(IntEnum):
    """File type flags for FILE_INIT command"""
    CONFIG = 0x0C
    MEDIA = 0x28
    PLAYLIST = 0x32


@dataclass
class MerlinPacket:
    """Represents a Merlin protocol packet"""
    cmd_id: int
    payload: bytes
    crc: int
    
    @property
    def length(self) -> int:
        """Total packet length (excluding length byte itself)"""
        return 1 + len(self.payload) + 4  # CMD + Payload + CRC
    
    def to_bytes(self) -> bytes:
        """Serialize packet to bytes"""
        return bytes([self.length]) + bytes([self.cmd_id]) + self.payload + struct.pack('<I', self.crc)


class MerlinProtocol:
    """Merlin protocol implementation"""
    
    # CRC32 parameters
    CRC_INIT = 0xFFFFFFFF
    CRC_POLY = 0x04C11DB7
    
    @staticmethod
    def calculate_crc32(data: bytes) -> int:
        """
        Calculate CRC32 for Merlin protocol.
        
        Args:
            data: Data to calculate CRC on (CMD_ID + Payload)
            
        Returns:
            CRC32 value (32-bit unsigned)
        """
        crc = MerlinProtocol.CRC_INIT
        for byte in data:
            crc ^= (byte << 24)
            for _ in range(8):
                if crc & 0x80000000:
                    crc = ((crc << 1) ^ MerlinProtocol.CRC_POLY) & 0xFFFFFFFF
                else:
                    crc = (crc << 1) & 0xFFFFFFFF
        return crc
    
    @staticmethod
    def create_packet(cmd_id: int, payload: bytes = b'') -> MerlinPacket:
        """
        Create a Merlin packet with automatic CRC calculation.
        
        Args:
            cmd_id: Command ID
            payload: Command payload (optional)
            
        Returns:
            MerlinPacket object
        """
        data = bytes([cmd_id]) + payload
        crc = MerlinProtocol.calculate_crc32(data)
        return MerlinPacket(cmd_id=cmd_id, payload=payload, crc=crc)
    
    @staticmethod
    def parse_packet(data: bytes) -> Optional[MerlinPacket]:
        """
        Parse a Merlin packet from bytes.
        
        Args:
            data: Raw packet data (including length byte)
            
        Returns:
            MerlinPacket object or None if invalid
        """
        if len(data) < 6:  # Min: Length + CMD + CRC
            return None
        
        length = data[0]
        if length + 1 != len(data):
            return None
        
        cmd_id = data[1]
        payload = data[2:-4]
        crc_received = struct.unpack('<I', data[-4:])[0]
        
        # Verify CRC
        crc_calculated = MerlinProtocol.calculate_crc32(data[1:-4])
        if crc_calculated != crc_received:
            return None
        
        return MerlinPacket(cmd_id=cmd_id, payload=payload, crc=crc_received)
    
    @staticmethod
    def verify_packet(data: bytes) -> Tuple[bool, Optional[int], Optional[int]]:
        """
        Verify packet CRC without full parsing.
        
        Args:
            data: Raw packet data
            
        Returns:
            Tuple of (is_valid, crc_calculated, crc_received)
        """
        if len(data) < 6:
            return False, None, None
        
        crc_received = struct.unpack('<I', data[-4:])[0]
        crc_calculated = MerlinProtocol.calculate_crc32(data[1:-4])
        
        return crc_calculated == crc_received, crc_calculated, crc_received


class MerlinCommands:
    """High-level command builders for Merlin protocol"""
    
    @staticmethod
    def ping() -> MerlinPacket:
        """
        Create a PING command.
        
        Returns:
            PING packet
        """
        return MerlinProtocol.create_packet(MerlinCommand.PING)
    
    @staticmethod
    def get_status() -> MerlinPacket:
        """
        Create a STATUS query command.
        
        Returns:
            STATUS packet
        """
        return MerlinProtocol.create_packet(MerlinCommand.STATUS)
    
    @staticmethod
    def get_storage_info() -> MerlinPacket:
        """
        Create a STORAGE_INFO query command.
        
        Returns:
            STORAGE_INFO packet
        """
        return MerlinProtocol.create_packet(MerlinCommand.STORAGE_INFO)
    
    @staticmethod
    def get_battery() -> MerlinPacket:
        """
        Create a BATTERY query command.
        
        Returns:
            BATTERY packet
        """
        return MerlinProtocol.create_packet(MerlinCommand.BATTERY)
    
    @staticmethod
    def end_session() -> MerlinPacket:
        """
        Create an END_SESSION command.
        
        Returns:
            END_SESSION packet
        """
        return MerlinProtocol.create_packet(MerlinCommand.END_SESSION)
    
    @staticmethod
    def file_descriptor(filename: str, flag: int = 0x01) -> MerlinPacket:
        """
        Create a FILE_DESCRIPTOR command (announces a file).
        
        Args:
            filename: Name of the file (with extension)
            flag: Command flag (default: 0x01)
            
        Returns:
            FILE_DESCRIPTOR packet
        """
        payload = bytes([flag]) + filename.encode('ascii')
        return MerlinProtocol.create_packet(MerlinCommand.FILE_DESCRIPTOR, payload)
    
    @staticmethod
    def file_init(filename: str, filesize: int, file_data: bytes, 
                  file_type: FileType = FileType.MEDIA) -> MerlinPacket:
        """
        Create a FILE_INIT command (file metadata with SHA256).
        
        Args:
            filename: Name of the file (with extension)
            filesize: Size of the file in bytes
            file_data: Actual file content (for SHA256 calculation)
            file_type: Type of file (MEDIA, CONFIG, or PLAYLIST)
            
        Returns:
            FILE_INIT packet
        """
        # Calculate SHA256 of file content
        sha256 = hashlib.sha256(file_data).digest()
        
        # Build payload: [Flag][Filename][Filesize:4 LE][SHA256:32]
        payload = (
            bytes([file_type]) +
            filename.encode('ascii') +
            struct.pack('<I', filesize) +
            sha256
        )
        
        return MerlinProtocol.create_packet(MerlinCommand.FILE_INIT, payload)


class MerlinResponse:
    """Parser for Merlin response packets"""
    
    @staticmethod
    def parse_status(packet: MerlinPacket) -> dict:
        """
        Parse STATUS response.
        
        Args:
            packet: STATUS response packet
            
        Returns:
            Dictionary with status information
        """
        if len(packet.payload) < 4:
            return {}
        
        return {
            'mode': packet.payload[0],
            'flags': packet.payload[1],
            'unknown': struct.unpack('>H', packet.payload[2:4])[0]
        }
    
    @staticmethod
    def parse_storage_info(packet: MerlinPacket) -> dict:
        """
        Parse STORAGE_INFO response.
        
        Args:
            packet: STORAGE_INFO response packet
            
        Returns:
            Dictionary with storage information
        """
        if len(packet.payload) < 4:
            return {}
        
        state = struct.unpack('>H', packet.payload[0:2])[0]
        free_blocks = struct.unpack('>H', packet.payload[2:4])[0]
        
        return {
            'state': state,
            'free_blocks': free_blocks,
            'free_mb': free_blocks * 4 / 1024  # Assuming 4KB blocks
        }
    
    @staticmethod
    def parse_battery(packet: MerlinPacket) -> dict:
        """
        Parse BATTERY response.
        
        Args:
            packet: BATTERY response packet
            
        Returns:
            Dictionary with battery information
        """
        if len(packet.payload) < 2:
            return {}
        
        return {
            'percentage': packet.payload[0],
            'status': packet.payload[1]  # 0x00=idle, 0x01=charging
        }
    
    @staticmethod
    def parse_file_init_response(packet: MerlinPacket) -> dict:
        """
        Parse FILE_INIT response.
        
        Args:
            packet: FILE_INIT response packet
            
        Returns:
            Dictionary with response status
        """
        if len(packet.payload) < 1:
            return {}
        
        return {
            'status': packet.payload[0]  # 0x00=ready, 0x01=accepted
        }


class MerlinClient:
    """High-level client for Merlin speaker communication"""
    
    def __init__(self, host: str, port: int = 50000):
        """
        Initialize Merlin client.
        
        Args:
            host: Speaker IP address
            port: Speaker port (default: 50000)
        """
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
    
    def connect(self) -> bool:
        """
        Connect to the Merlin speaker.
        
        Returns:
            True if connected successfully
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the speaker"""
        if self.socket:
            self.socket.close()
            self.socket = None
    
    def send_packet(self, packet: MerlinPacket) -> bool:
        """
        Send a packet to the speaker.
        
        Args:
            packet: Packet to send
            
        Returns:
            True if sent successfully
        """
        if not self.socket:
            return False
        
        try:
            self.socket.sendall(packet.to_bytes())
            return True
        except Exception as e:
            print(f"Send failed: {e}")
            return False
    
    def receive_packet(self, timeout: float = 5.0) -> Optional[MerlinPacket]:
        """
        Receive a packet from the speaker.
        
        Args:
            timeout: Receive timeout in seconds
            
        Returns:
            Received packet or None
        """
        if not self.socket:
            return None
        
        try:
            self.socket.settimeout(timeout)
            
            # Read length byte
            length_byte = self.socket.recv(1)
            if not length_byte:
                return None
            
            length = length_byte[0]
            
            # Read rest of packet
            data = length_byte + self.socket.recv(length)
            
            return MerlinProtocol.parse_packet(data)
        except socket.timeout:
            return None
        except Exception as e:
            print(f"Receive failed: {e}")
            return None
    
    def send_file(self, filename: str, file_data: bytes, 
                  file_type: FileType = FileType.MEDIA,
                  chunk_size: int = 1440) -> bool:
        """
        Send a file to the speaker.
        
        Args:
            filename: Name of the file
            file_data: File content
            file_type: Type of file
            chunk_size: Size of data chunks (default: 1440 bytes, TCP MSS)
            
        Returns:
            True if file sent successfully
        """
        # Step 1: Send FILE_DESCRIPTOR
        fd_packet = MerlinCommands.file_descriptor(filename)
        if not self.send_packet(fd_packet):
            return False
        
        # Wait for response
        response = self.receive_packet()
        if not response:
            return False
        
        # Step 2: Send FILE_INIT with metadata
        fi_packet = MerlinCommands.file_init(filename, len(file_data), file_data, file_type)
        if not self.send_packet(fi_packet):
            return False
        
        # Wait for response
        response = self.receive_packet()
        if not response:
            return False
        
        # Step 3: Send raw file data in chunks
        try:
            offset = 0
            total_size = len(file_data)
            
            while offset < total_size:
                chunk = file_data[offset:offset + chunk_size]
                self.socket.sendall(chunk)
                offset += len(chunk)
                
                # Optional: print progress
                if total_size > 10000:  # Only for large files
                    progress = (offset / total_size) * 100
                    print(f"\rSending: {progress:.1f}% ({offset}/{total_size} bytes)", end='')
            
            if total_size > 10000:
                print()  # New line after progress
            
            return True
        except Exception as e:
            print(f"File data send failed: {e}")
            return False


if __name__ == "__main__":
    # Example usage
    print("Merlin Protocol Library")
    print("=" * 60)
    
    # Create some example packets
    ping = MerlinCommands.ping()
    print(f"PING packet: {ping.to_bytes().hex()}")
    
    status = MerlinCommands.get_status()
    print(f"STATUS packet: {status.to_bytes().hex()}")
    
    # Verify known good packet
    known_ping = bytes.fromhex("0502da848a47")
    is_valid, crc_calc, crc_recv = MerlinProtocol.verify_packet(known_ping)
    print(f"\nVerify known PING: {'✅' if is_valid else '❌'}")
    print(f"  CRC calculated: 0x{crc_calc:08X}")
    print(f"  CRC received:   0x{crc_recv:08X}")
