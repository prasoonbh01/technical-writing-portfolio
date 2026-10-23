How to Configure an IPsec Site-to-Site VPN Tunnel with strongSwan
Audience: Network, cloud, and DevOps engineers Difficulty: Intermediate Time to complete: 30-45 minutes Tested with: Ubuntu 22.04 LTS, strongSwan 5.9.x (swanctl / charon-systemd)

1. Overview & Topology
A site-to-site IPsec VPN creates an encrypted tunnel between two networks over the public internet. Hosts in each network communicate using private IP addresses, with no VPN client software on the hosts themselves.
In this guide you will connect two sites, each with a Linux gateway running strongSwan:
IKEv2 negotiates keys and authenticates both gateways with a pre-shared key (PSK).
ESP in tunnel mode encrypts and authenticates the traffic between the two private subnets.
Topology
   Site A (HQ)                                          Site B (Branch)
 10.10.0.0/24                                           10.20.0.0/24

 +-----------+     +-----------------+   Internet   +-----------------+     +-----------+
 | Host A    |-----| Gateway A       |==============| Gateway B       |-----| Host B    |
 | 10.10.0.50|     | LAN: 10.10.0.1  |  IPsec/ESP   | LAN: 10.20.0.1  |     | 10.20.0.50|
 +-----------+     | WAN: 203.0.113.10|  tunnel      | WAN: 198.51.100.20|    +-----------+
                   +-----------------+              +-----------------+
Address plan
Item
Site A
Site B
Gateway public IP
203.0.113.10
198.51.100.20
Gateway LAN IP
10.10.0.1
10.20.0.1
Private subnet
10.10.0.0/24
10.20.0.0/24
Test host
10.10.0.50
10.20.0.50

Note: The public IPs above are from documentation ranges (RFC 5737). Replace every address in this guide with your own values.
Tunnel parameters
Parameter
Value
IKE version
IKEv2
Authentication
Pre-shared key
IKE (Phase 1) proposal
aes256gcm16-prfsha256-ecp256
ESP (Phase 2) proposal
aes256gcm16-ecp256 (with PFS)
Mode
Tunnel
Traffic selectors
10.10.0.0/24 <-> 10.20.0.0/24


2. Prerequisites
Systems
Two Linux gateways (physical, virtual, or cloud VMs) running Ubuntu 22.04 or similar, each with sudo access.
Each gateway has a reachable public IP (static, or a static NAT mapping to it).
One test host behind each gateway. The host's default route (or a route for the remote subnet) must point to its local gateway.
Network access (allow between the two gateway public IPs)
Protocol
Port
Purpose
UDP
500
IKE negotiation
UDP
4500
IKE/ESP with NAT traversal
ESP
IP protocol 50
Encrypted data (when no NAT is in the path)

Design requirements
The two private subnets must not overlap.
You know the correct date and time on both gateways (use NTP) so logs line up when troubleshooting.
Cloud-only requirements
AWS: disable Source/destination check on both gateway instances, and add a route in each private subnet's route table that sends the remote CIDR to the gateway's network interface.
Azure: enable IP forwarding on the gateway's NIC and add a user-defined route.
GCP: enable IP forwarding on the instance and add a custom static route.

3. Configuration Steps
Run each step on both gateways unless it says otherwise. Values that differ per site are marked Site A and Site B.
Step 1: Install strongSwan
sudo apt update
sudo apt install -y charon-systemd strongswan-swanctl
Step 2: Enable IP forwarding
echo "net.ipv4.ip_forward = 1" | sudo tee /etc/sysctl.d/99-vpn.conf
sudo sysctl --system
Confirm the setting:
sysctl net.ipv4.ip_forward
# net.ipv4.ip_forward = 1
Step 3: Generate a strong pre-shared key
Run this once and copy the output to both gateways:
openssl rand -base64 36
Store the key in a password manager. Never commit it to Git or paste it into a ticket.
Step 4: Create the tunnel configuration
Create /etc/swanctl/conf.d/site-to-site.conf.
Site A (Gateway A):
connections {
    site-a-to-site-b {
        version = 2
        local_addrs  = 203.0.113.10
        remote_addrs = 198.51.100.20
        proposals = aes256gcm16-prfsha256-ecp256

        dpd_delay = 30s
        rekey_time = 4h

        local {
            auth = psk
            id = 203.0.113.10
        }
        remote {
            auth = psk
            id = 198.51.100.20
        }

        children {
            lan-to-lan {
                local_ts  = 10.10.0.0/24
                remote_ts = 10.20.0.0/24
                mode = tunnel
                esp_proposals = aes256gcm16-ecp256
                start_action = start
                dpd_action = restart
            }
        }
    }
}

secrets {
    ike-site-ab {
        id-a = 203.0.113.10
        id-b = 198.51.100.20
        secret = "PASTE_YOUR_PRE_SHARED_KEY_HERE"
    }
}
Site B (Gateway B) uses the same file with the local and remote values swapped:
connections {
    site-b-to-site-a {
        version = 2
        local_addrs  = 198.51.100.20
        remote_addrs = 203.0.113.10
        proposals = aes256gcm16-prfsha256-ecp256

        dpd_delay = 30s
        rekey_time = 4h

        local {
            auth = psk
            id = 198.51.100.20
        }
        remote {
            auth = psk
            id = 203.0.113.10
        }

        children {
            lan-to-lan {
                local_ts  = 10.20.0.0/24
                remote_ts = 10.10.0.0/24
                mode = tunnel
                esp_proposals = aes256gcm16-ecp256
                start_action = start
                dpd_action = restart
            }
        }
    }
}

secrets {
    ike-site-ab {
        id-a = 198.51.100.20
        id-b = 203.0.113.10
        secret = "PASTE_YOUR_PRE_SHARED_KEY_HERE"
    }
}
Lock down the file because it contains the PSK:
sudo chmod 600 /etc/swanctl/conf.d/site-to-site.conf
Behind NAT (typical in cloud): If the gateway's public IP is a 1:1 NAT mapping and the OS only sees a private address (for example 10.0.1.5), set local_addrs to the private address and keep local.id set to the public IP. The remote gateway's remote_addrs and remote.id still use the public IP.
Step 5: Open the firewall
Allow IKE, NAT-T, and ESP from the peer gateway, and let forwarded traffic pass between the subnets. With ufw:
# On Gateway A (use 203.0.113.10 as the source on Gateway B)
sudo ufw allow from 198.51.100.20 to any port 500 proto udp
sudo ufw allow from 198.51.100.20 to any port 4500 proto udp
sudo ufw allow from 198.51.100.20 proto esp
If the gateway also masquerades (NATs) outbound LAN traffic, exempt VPN traffic from NAT, or packets will be rewritten before they are encrypted and will not match the tunnel:
# On Gateway A
sudo iptables -t nat -I POSTROUTING 1 -s 10.10.0.0/24 -d 10.20.0.0/24 -j ACCEPT

# On Gateway B
sudo iptables -t nat -I POSTROUTING 1 -s 10.20.0.0/24 -d 10.10.0.0/24 -j ACCEPT
Clamp TCP MSS to avoid fragmentation problems inside the tunnel:
sudo iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
Persist the rules with iptables-persistent (or your configuration management tool), otherwise they disappear on reboot.
Step 6: Load the configuration and start the tunnel
sudo systemctl enable --now strongswan
sudo swanctl --load-all
sudo swanctl --initiate --child lan-to-lan
Because of start_action = start, the tunnel will also come up automatically after a restart.

4. Verification Commands
4.1 Check the security associations
sudo swanctl --list-sas
Look for ESTABLISHED on the IKE SA and INSTALLED, TUNNEL on the child SA. The output below is illustrative; your SPIs, timers, and counters will differ.
site-a-to-site-b: #1, ESTABLISHED, IKEv2, 3f1c...
  local  '203.0.113.10' @ 203.0.113.10[4500]
  remote '198.51.100.20' @ 198.51.100.20[4500]
  AES_GCM_16-256/PRF_HMAC_SHA2_256/ECP_256
  established 94s ago, rekeying in 14201s
  lan-to-lan: #1, reqid 1, INSTALLED, TUNNEL, ESP:AES_GCM_16-256/ECP_256
    installed 94s ago, rekeying in 3180s
    local  10.10.0.0/24
    remote 10.20.0.0/24
4.2 Check the kernel policies
ip xfrm policy
ip xfrm state
You should see policies for 10.10.0.0/24 <-> 10.20.0.0/24 with proto esp and mode tunnel.
4.3 Ping across the tunnel
From Gateway A, source the ping from the LAN interface so it matches the traffic selector:
ping -c 4 -I 10.10.0.1 10.20.0.1
From Host A to Host B (the real end-to-end test):
ping -c 4 10.20.0.50
4.4 Confirm traffic is actually encrypted
On a gateway, watch the WAN interface (replace eth0) while the ping runs:
sudo tcpdump -ni eth0 'esp or udp port 4500'
You should see ESP packets (or UDP 4500 when NAT-T is active) and no clear-text ICMP between the private subnets.
4.5 Read the logs
sudo journalctl -u strongswan -n 50 --no-pager
4.6 Verification checklist
IKE SA shows ESTABLISHED on both gateways
Child SA shows INSTALLED, TUNNEL
Gateway-to-gateway ping over the LAN addresses succeeds
Host-to-host ping succeeds in both directions
tcpdump on the WAN interface shows ESP, not plain ICMP

5. Common Troubleshooting Pitfalls
Work through these in order. They are listed from most to least common.
#
Symptom
Likely cause
Fix
1
IKE SA never appears; no reply from the peer
UDP 500/4500 blocked by a cloud security group, NACL, or host firewall
Allow UDP 500 and 4500 (and ESP) between the two gateway public IPs. Check both directions.
2
Log shows AUTHENTICATION_FAILED
PSK differs between sites, or the id values do not match what the peer expects
Re-paste the key (watch for trailing spaces or newlines). Make local.id on one side equal remote.id on the other.
3
Log shows NO_PROPOSAL_CHOSEN
IKE or ESP algorithms differ between the gateways
Use identical proposals and esp_proposals on both ends.
4
Log shows TS_UNACCEPTABLE
Traffic selectors are not mirror images
Site A local_ts must equal Site B remote_ts, and vice versa.
5
Tunnel is ESTABLISHED, but pings fail
Missing return route, IP forwarding disabled, or cloud source/destination check still on
Run sysctl net.ipv4.ip_forward. Confirm hosts route the remote subnet via the gateway. Add the cloud route table entries from the Prerequisites.
6
Gateway-to-gateway works, but hosts cannot ping
Outbound NAT (masquerade) rewrites VPN traffic before encryption
Add the iptables -t nat ... -j ACCEPT exemption from Step 5.
7
Small pings work; large transfers or SSH hang
MTU / fragmentation inside the tunnel
Apply the MSS clamp from Step 5. Test with ping -M do -s 1372 <remote-ip> and lower the size until it passes.
8
Works, then drops after a few hours
Mismatched rekey timers or a firewall dropping idle UDP mappings
Keep dpd_delay set, use the same rekey_time on both sides, and keep dpd_action = restart.
9
Cloud gateway cannot bind or negotiate
Public IP is a NAT mapping, but local_addrs uses the public IP
Use the instance's private IP in local_addrs and the public IP in local.id.
10
Traffic only works from one side
Overlapping subnets, or one side's tunnel is not initiated
Re-plan CIDRs so they do not overlap. Run swanctl --initiate on the side that is down.

Handy debugging commands
# Raise logging detail temporarily (edit, then restart)
sudo nano /etc/strongswan.d/charon-logging.conf

# Reload configuration without dropping other tunnels
sudo swanctl --load-all

# Tear down and rebuild one tunnel
sudo swanctl --terminate --child lan-to-lan
sudo swanctl --initiate --child lan-to-lan

# Watch IKE handshake traffic live
sudo tcpdump -ni eth0 'udp port 500 or udp port 4500'
Information to collect before asking for help
The output of sudo swanctl --list-sas from both gateways
The relevant journalctl -u strongswan lines from both gateways
ip route and ip xfrm policy output, with the PSK removed
A statement of which firewall layers sit between the gateways (host firewall, security group, NACL, upstream device)

6. Security Hardening Notes
Prefer certificate-based authentication over a PSK for production deployments or more than a handful of tunnels.
Keep the PSK long and random, and rotate it on a schedule.
Use modern algorithms (AEAD ciphers such as AES-GCM) and enable PFS, as shown here.
Restrict UDP 500/4500 and ESP to the peer's IP rather than 0.0.0.0/0.
Monitor tunnel state and alert when the child SA disappears.

7. Clean Up
If you built this in a cloud lab, delete the VMs, elastic/public IPs, and route table entries when you finish to avoid ongoing charges.

8. Next Steps
Add a second child SA to carry another pair of subnets.
Automate the configuration with Ansible or Terraform and keep the PSK in a secrets manager.
Add a second tunnel and a routing protocol (BGP) for redundancy.
Read the official strongSwan swanctl documentation.

Author: [Your Name] | Technical Writer, Networking, Cloud & DevOps | [Portfolio link] | [Email]
