# Merlin Speaker Protocol

Python library for communicating with Merlin story-telling speakers.

## 📋 Protocol Overview

The Merlin protocol uses TCP communication on port 50000 with a custom binary format.

### Packet Format

```
[Length:1][CMD_ID:1][Payload...][CRC32:4 LE]
```

- **Length**: Total packet size excluding the length byte itself
- **CMD_ID**: Command identifier (see below)
- **Payload**: Variable-length command data
- **CRC32**: 32-bit CRC in little-endian format

### CRC32 Algorithm

- **Init**: `0xFFFFFFFF`
- **Polynomial**: `0x04C11DB7`
- **XOR out**: `0x00000000`
- **Calculated on**: `CMD_ID + Payload` (not the Length byte)

## 🎯 Command Reference

| CMD_ID | Name | Direction | Description |
|--------|------|-----------|-------------|
| 0x01 | FILE_INIT | → | File metadata with SHA256 |
| 0x02 | PING | ↔ | Connection test |
| 0x03 | STATUS | ↔ | Get speaker status |
| 0x04 | STORAGE_INFO | ↔ | Get storage information |
| 0x05 | CMD_05 | ↔ | Unknown |
| 0x08 | CMD_08 | ↔ | Unknown |
| 0x09 | END_SESSION | ↔ | End communication session |
| 0x0E | BATTERY | ↔ | Get battery status |
| 0x1B | CMD_1B | ↔ | Unknown |
| 0x1D | CMD_1D | ↔ | Unknown |
| 0x1E | CMD_1E | ↔ | Unknown |
| 0x1F | FILE_DESCRIPTOR | → | Announce file transfer |

### Command Details

#### PING (0x02)
Simple echo command to test connection.

**Request**: `05 02 da 84 8a 47`
**Response**: `05 02 da 84 8a 47` (identical)

#### STATUS (0x03)
Get speaker status.

**Request**: `05 03 6d 99 4b 43`
**Response**: `09 03 [Mode:1][Flags:1][Unknown:2][CRC:4]`

- **Mode**: 0x00 = Sync mode
- **Flags**: Status flags
- **Unknown**: 0x0cba (purpose unknown)

#### STORAGE_INFO (0x04)
Get storage information.

**Request**: `05 04 68 c9 0c 5d`
**Response**: `09 04 [State:2][Free:2][CRC:4]`

- **State**: Storage state (0x0000 = OK)
- **Free**: Free blocks (4KB blocks, big-endian)

#### BATTERY (0x0E)
Get battery status.

**Request**: `05 0e be 1f 86 72`
**Response**: `07 0e [Percent:1][Status:1][CRC:4]`

- **Percent**: Battery percentage (0-100)
- **Status**: 0x00 = Idle, 0x01 = Charging

#### FILE_DESCRIPTOR (0x1F)
Announce a file before sending.

**Format**: `[Length][0x1F][Flag:1][Filename][CRC:4]`

- **Flag**: 0x01 for request
- **Filename**: ASCII filename with extension

**Example**: `2e 1f 01 34383...6d703341b94df6`

#### FILE_INIT (0x01)
Send file metadata before raw data.

**Format**: `[Length][0x01][Type:1][Filename][Size:4][SHA256:32][CRC:4]`

- **Type**: File type flag
  - 0x0C = Config file
  - 0x28 = Media file (MP3/JPG)
  - 0x32 = Playlist file
- **Filename**: ASCII filename with extension
- **Size**: File size in bytes (little-endian)
- **SHA256**: SHA256 hash of file content (32 bytes)

## 🚀 Quick Start

### Installation

```bash
# No dependencies required, pure Python 3
python3 merlin_protocol.py
```

### Basic Usage

```python
from merlin_protocol import MerlinClient, MerlinCommands, FileType

# Connect to speaker
client = MerlinClient("192.168.4.1", 50000)
client.connect()

# Send PING
ping = MerlinCommands.ping()
client.send_packet(ping)
response = client.receive_packet()

# Get storage info
storage = MerlinCommands.get_storage_info()
client.send_packet(storage)
response = client.receive_packet()

# Disconnect
client.disconnect()
```

### Sending a File

```python
from merlin_protocol import MerlinClient, FileType

# Load file
with open("story.mp3", "rb") as f:
    file_data = f.read()

# Connect and send
client = MerlinClient("192.168.4.1", 50000)
client.connect()

# Send file (data is automatically chunked into 1440-byte packets)
client.send_file("story.mp3", file_data, FileType.MEDIA)

# Or with custom chunk size
client.send_file("story.mp3", file_data, FileType.MEDIA, chunk_size=2048)

client.disconnect()
```

## 📁 File Transfer Protocol

Complete sequence for sending a file:

1. **Announce file** (CMD 0x1F)
   ```
   → FILE_DESCRIPTOR: filename.mp3
   ← Response (ACK)
   ```

2. **Send metadata** (CMD 0x01)
   ```
   → FILE_INIT: filename, size, SHA256
   ← Response (0x00 = ready)
   ```

3. **Send raw data**
   ```
   → Raw file bytes (unencrypted, sent in 1440-byte chunks)
   ```

4. **Confirmation**
   ```
   ← Response (0x01 = accepted)
   ```

### Data Chunking

File data is sent in **1440-byte chunks** (TCP Maximum Segment Size) to match the observed protocol behavior in pcap captures. This ensures compatibility with the speaker's TCP stack and prevents potential buffer issues.

The chunk size can be customized if needed:
```python
client.send_file(filename, data, FileType.MEDIA, chunk_size=2048)
```

Or via CLI:
```bash
python3 merlin_cli.py send 192.168.4.1 file.mp3 --chunk-size 2048
```

## 🔍 Examples

See `merlin_example.py` for complete examples:

- Basic commands (ping, status, battery)
- File transfer
- Manual packet creation
- SHA256 verification

## 📊 Packet Analysis

The library includes a complete pcap analyzer:

```bash
python3 parse_merlin_pcap.py
```

Output: `merlin_pcap_all.txt` with detailed packet analysis.

## 🛠️ API Reference

### MerlinProtocol

Core protocol implementation.

```python
# Calculate CRC32
crc = MerlinProtocol.calculate_crc32(data)

# Create packet
packet = MerlinProtocol.create_packet(cmd_id, payload)

# Parse packet
packet = MerlinProtocol.parse_packet(raw_data)

# Verify CRC
is_valid, crc_calc, crc_recv = MerlinProtocol.verify_packet(raw_data)
```

### MerlinCommands

High-level command builders.

```python
# Basic commands
ping = MerlinCommands.ping()
status = MerlinCommands.get_status()
storage = MerlinCommands.get_storage_info()
battery = MerlinCommands.get_battery()
end = MerlinCommands.end_session()

# File commands
fd = MerlinCommands.file_descriptor(filename, flag=0x01)
fi = MerlinCommands.file_init(filename, size, data, FileType.MEDIA)
```

### MerlinResponse

Response parsers.

```python
# Parse responses
status = MerlinResponse.parse_status(packet)
storage = MerlinResponse.parse_storage_info(packet)
battery = MerlinResponse.parse_battery(packet)
file_resp = MerlinResponse.parse_file_init_response(packet)
```

### MerlinClient

High-level client for speaker communication.

```python
client = MerlinClient(host, port=50000)

# Connection
client.connect()
client.disconnect()

# Communication
client.send_packet(packet)
response = client.receive_packet(timeout=5.0)

# File transfer
client.send_file(filename, data, file_type)
```

## 🔐 Security Notes

- **No encryption**: File data is sent in clear text
- **SHA256 verification**: Files are verified using SHA256 hash
- **CRC32 integrity**: All packets include CRC32 for integrity check

## 📝 Protocol Discoveries

This implementation is based on reverse-engineering from pcap analysis:

- ✅ CRC32 algorithm identified and verified
- ✅ All command formats decoded
- ✅ File transfer protocol complete
- ✅ SHA256 metadata verification
- ❓ Some command purposes unknown (0x05, 0x08, 0x1B, 0x1D, 0x1E)
- ❓ STATUS response field 0x0cba purpose unknown

## 📄 Files

- `merlin_protocol.py` - Core protocol library
- `merlin_example.py` - Usage examples
- `parse_merlin_pcap.py` - Pcap analyzer
- `merlin_pcap_all.txt` - Complete packet analysis
- `README_MERLIN.md` - This file

## 🤝 Contributing

This is a reverse-engineered protocol. If you discover new commands or understand unknown fields, please contribute!

## ⚠️ Disclaimer

This library is for educational and interoperability purposes. Use responsibly and respect the manufacturer's terms of service.

## 📜 License

Reverse-engineered protocol implementation - use at your own risk.

---

**Last updated**: 2025-11-25
**Protocol version**: Merlin v1 (based on pcap analysis)
