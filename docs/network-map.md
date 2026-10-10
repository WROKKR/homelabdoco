# Network map

## Internet edge

The internet edge and routing platform is a UniFi Dream Machine Pro SE. The broader network uses a UniFi stack. The home web server is exposed through a port forward. ISP details, WAN configuration, the exact forwarded ports and destination, switching, and wireless access points are not yet documented.

## Networks and VLANs

The local network began with two unnamed nominal networks bridged into one security domain. On 2026-09-28, a UniFi DMZ network using VLAN 90 was created and assigned to the DMZ firewall zone for the Minecraft VM. The DMZ is `192.168.90.0/24`, its gateway is `192.168.90.1`, and VM 119 has a DHCP reservation at `192.168.90.171`. A separate UniFi Teleport network provides remote access.

| Name | VLAN | Subnet | Gateway | Purpose | Trust level |
|---|---:|---|---|---|---|
| Unnamed bridged LANs | Unknown | `/24`; observed primary range is `192.168.0.0/24` | `odin` at `192.168.0.1` for the observed range | General clients and servers | Effectively one shared trust domain |
| Minecraft DMZ | 90 | `192.168.90.0/24` | `192.168.90.1` | Internet-facing Minecraft VM 119 at `192.168.90.171` | Untrusted/DMZ |
| UniFi Teleport | Managed by UniFi | Unknown | UDM Pro SE | Remote access | Remote-access boundary |

## DNS and ingress

- Technitium DNS runs as a container on `dockerhost26` at `192.168.0.160`, publishing TCP and UDP port 53 and its management UI on port 5380.
- The UDM Pro SE (`odin`) provides DHCP; clients use Technitium for DNS.
- The internal DNS namespace is `wwbb.casa`.
- Nginx Proxy Manager runs on the same Docker VM and publishes ports 80, 81, and 443.
- A port forward exposes the home web server. The public hostname, forwarded ports, and exact proxy route are not yet documented.
- Technitium upstream DNS, DHCP scope details, and certificate handling are not yet documented.
- The three current Turing Pi CM4 nodes have DHCP reservations on the existing LAN. Their hostnames, reserved addresses, and reservation details are not yet documented.
- `dockerhost26` now reserves `10.240.0.0/16` as Docker's automatic address pool, allocating `/24` networks. This prevents new Docker bridges from consuming real `192.168.x.x` LAN/VLAN space. Existing networks retain their old subnets until individually recreated.

## Remote access

UniFi Teleport is the only remote-access mechanism. No other VPN or zero-trust service is currently documented. Never record Teleport enrollment material or credentials in this repository.
