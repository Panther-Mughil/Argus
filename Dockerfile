# =============================================================================
# Argus CTF Container Image — argus-kali
# =============================================================================
# Replaces the current kali-forensics podman script (keys-ops/setup.sh).
# This Dockerfile bundles the full per-category CTF toolchain from
# docs/plans/kali-tool-research.md and provisions an SSH agent shell.
#
# The running shared container is still kali-forensics until this image
# fully replaces it. After migration, use "argus-kali" in place of
# "kali-forensics" in docker-compose or podman commands.
# =============================================================================

# ---- Base image: kalilinux/kali-rolling (latest pin) ------------------------
FROM kalilinux/kali-rolling:latest

LABEL org.opencontainers.image.title="Argus Kali CTF" \
      org.opencontainers.image.description="Full CTF toolchain for the Argus project" \
      org.opencontainers.image.source="https://github.com/argus/Argus"

# ---- Environment -----------------------------------------------------------
ENV DEBIAN_FRONTEND=noninteractive

# =============================================================================
# Full toolchain install (unprivileged — no loop mounts)
# Package inventory sourced from docs/plans/kali-tool-research.md
# =============================================================================
RUN apt-get update -qq \
 && apt-get install -y --no-install-recommends \
# --- Core / forensics base (preserves keys-ops/setup.sh set) ---------------
    sleuthkit \
    p7zip-full \
    binwalk \
    foremost \
    testdisk \
    libimage-exiftool-perl \
    file \
    binutils \
    xxd \
    unzip \
    grep \
    ripgrep \
    coreutils \
    tar \
    gzip \
    bzip2 \
    xz-utils \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    wget \
    jq \
    gawk \
    sed \
    netcat-openbsd \
    ncat \
    socat \
    sqlite3 \
    ca-certificates \
    dnsutils \
    whois \
    git \
    less \
# --- Pwn / RE -------------------------------------------------------------
    gdb \
    checksec \
    patchelf \
    radare2 \
    rizin \
    python3-pwntools \
    python3-ropgadget \
    default-jdk \
    upx-ucl \
# --- Web --------------------------------------------------------------------
    nmap \
    gobuster \
    dirb \
    ffuf \
    feroxbuster \
    sqlmap \
    nikto \
    whatweb \
    wfuzz \
    commix \
    python3-requests \
    seclists \
# --- Crypto ---------------------------------------------------------------
    john \
    hashcat \
    openssl \
    python3-pycryptodome \
    python3-sympy \
# --- Steganography / media ------------------------------------------------
    steghide \
    outguess \
    sox \
    ffmpeg \
    python3-pil \
    python3-numpy \
    ruby \
    zbar-tools \
    qrencode \
# --- Network (offline pcap) -----------------------------------------------
    tshark \
    tcpdump \
    tcpflow \
    python3-scapy \
    ngrep \
    wireshark-common \
# --- OSINT ----------------------------------------------------------------
    theharvester \
    recon-ng \
# --- Mobile / RE (static) -------------------------------------------------
    apktool \
    jadx \
    dex2jar \
# --- Programming languages ------------------------------------------------
    gcc \
    g++ \
    nodejs \
    npm \
    ruby \
    php \
    lua5.4 \
    golang \
    rustc \
    cargo \
# --- DB / cloud CLI -------------------------------------------------------
    default-mysql-client \
    postgresql-client \
    redis-tools \
    awscli \
    terraform \
    ghidra \
# --- Misc -----------------------------------------------------------------
    expect \
    pandoc \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# =============================================================================
# Pip packages (tools without an apt package, or preferred pip version)
# =============================================================================
RUN pip install --break-system-packages \
    pwntools \
    ropper \
    xortool \
    stegcracker \
    volatility3 \
    slither-analyzer \
    mythril \
    web3 \
    picklescan \
    dpkt \
    zsteg \
    2>/dev/null || true

# =============================================================================
# SSH provisioning — agent key-based login
# Mirrors keys-ops/setup.sh sshd directives
# =============================================================================
RUN apt-get update -qq \
 && apt-get install -y --no-install-recommends openssh-server \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Create runtime directories and SSH key dir
RUN mkdir -p /run/sshd /root/.ssh && chmod 700 /root/.ssh

# Generate host keys if missing (idempotent)
RUN test -f /etc/ssh/ssh_host_rsa_key || ssh-keygen -A

# sshd_config — mirrors every directive from keys-ops/setup.sh
RUN cat <<'EOF' > /etc/ssh/sshd_config
Port 22
PermitRootLogin prohibit-password
PubkeyAuthentication yes
PasswordAuthentication no
AllowTcpForwarding yes
PermitEmptyPasswords no
ChallengeResponseAuthentication no
UsePAM yes
X11Forwarding no
PrintMotd no
AcceptEnv LANG LC_*
Subsystem sftp /usr/lib/openssh/sftp-server
EOF

# authorized_keys intentionally left empty — ops script (keys-ops/setup.sh)
# injects the public key at runtime.  Reference line:
#   echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILd37oJ7GbuDuCpq8kEFz4xzdG+9uUlNhaBc/1u3Yrl5 argus@ctf" > /root/.ssh/authorized_keys
# (The ops team manages this; do NOT commit the key here.)

# =============================================================================
# Expose SSH
# =============================================================================
EXPOSE 22

# =============================================================================
# Entry point: start sshd (foreground), keep container alive
# =============================================================================
ENTRYPOINT ["/usr/sbin/sshd", "-D"]
CMD ["sleep", "infinity"]
