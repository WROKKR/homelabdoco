# Installing the Turing Pi CLI in WSL

## Purpose

This document records how the `tpi` command-line client was brought into use under WSL, the failures encountered, and a clean path for repeating the installation.

It does not contain BMC passwords or authentication tokens. Replace example addresses with the BMC's current reserved IPv4 address.

## Result

The working environment was:

- WSL on an x86-64 Windows host
- `tpi 1.0.7`
- executable located at `/root/.cargo/bin/tpi`
- BMC addressed by reserved IPv4 address rather than `turingpi.local`

The installation was validated with:

```sh
/root/.cargo/bin/tpi --version
```

which returned:

```text
tpi 1.0.7
```

## What failed

### The APT repository line contained Markdown

The repository instruction was initially copied in this form:

```text
deb [https://firmware.turingpi.com/tpi/debian](https://firmware.turingpi.com/tpi/debian) ./
```

That is Markdown link syntax, not valid APT source syntax. APT consequently treated the bracketed text as part of the repository address, reported that the repository had no `Release` file, disabled it for security, and could not locate a package named `tpi`.

The underlying lesson is to copy the raw URL from rendered documentation rather than the Markdown representation of the link. Also remove any malformed entry before running `apt update` again.

### Debian's Cargo was too old for the resolved dependencies

Compiling `tpi 1.0.7` with Cargo 1.75.0 failed while processing `rand_pcg 0.10.2`:

```text
feature `edition2024` is required
```

The message appeared underneath several layers of errors, including:

```text
failed to download replaced source registry `crates-io`
failed to parse manifest
```

The decisive part was the manifest error, not connectivity. Cargo 1.75 predated stable support for Rust's 2024 edition, while the selected dependency required it. Repeating the download without changing the toolchain could not resolve this incompatibility.

### Cargo installation and rustup installation were confused

Commands were then attempted against:

```text
/root/.cargo/bin/rustup
/root/.cargo/bin/cargo
```

Neither file existed. The presence of `/root/.cargo/bin/tpi` did not imply that `rustup` or `cargo` had also been installed there. Cargo uses `$HOME/.cargo/bin` as an installation destination for application binaries even when Cargo itself came from the distribution and lives elsewhere.

Use these commands to establish the actual tool locations:

```sh
command -v rustup || true
command -v cargo || true
command -v tpi || true
cargo --version 2>/dev/null || true
```

Do not assume a tool is under `/root/.cargo/bin` merely because `tpi` is there.

## Repeatable installation path

For a fresh WSL installation, use a current Rust toolchain rather than Debian's old Cargo package:

```sh
apt-get update
apt-get install -y curl build-essential pkg-config libssl-dev
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
. "$HOME/.cargo/env"
rustup update stable
cargo --version
cargo install tpi
tpi --version
```

Run the entire sequence as the user who will operate `tpi`. Rustup is installed per user: installing it as an ordinary WSL user does not create `/root/.cargo/bin/rustup`, and installing it as root does not configure another user's shell.

If a shell opened before installation cannot find `tpi`, load the Cargo environment:

```sh
. "$HOME/.cargo/env"
```

or start a new shell. Verify the selected executable with:

```sh
command -v tpi
tpi --version
```

### Historical accuracy note

The retained terminal transcript proves that `tpi 1.0.7` ultimately existed at `/root/.cargo/bin/tpi`, but it does not include the exact successful installation command. Therefore, the sequence above is the repeatable installation procedure, not a claim that every command was used verbatim during the original session.

## Connecting to the Turing Pi

Running the bare command caused `tpi` to try its default BMC address, `turingpi.local`. WSL did not reliably resolve or reach that mDNS name, producing an error while contacting the authentication endpoint.

Use the BMC's DHCP reservation explicitly:

```sh
tpi --host 192.168.0.180 power status
```

The current address should be taken from the network inventory or router rather than copied permanently from this example.

Authentication is interactive unless credentials or a valid cached token are already available:

```text
User: root
Password:
```

Do not put the BMC password into documentation, shell history, scripts, or version control.

## CLI syntax differences

Older instructions used short options such as:

```text
tpi -u device -n 1
```

`tpi 1.0.7` rejected `-u` as an unexpected argument. The installed version uses subcommands, so its own help output is authoritative:

```sh
tpi --help
tpi power --help
tpi usb --help
```

Examples that worked with the installed client include:

```sh
tpi --host 192.168.0.180 power status
tpi --host 192.168.0.180 power on --node 1
tpi --host 192.168.0.180 power off
```

The leading `$` shown in many documentation examples is a shell prompt marker and must not be typed. Enter `tpi ...`, not `$ tpi ...`.

## Validation checklist

```sh
uname -m
command -v tpi
tpi --version
tpi --host 192.168.0.180 power status
```

Expected characteristics:

- WSL itself may report `x86_64`; this is valid because `tpi` runs on the administration computer, not on a compute module.
- `tpi --version` reports the installed client version.
- The BMC prompts for authentication when necessary.
- `power status` returns the state of Nodes 1 through 4.

## Troubleshooting decision path

1. If `apt update` shows square brackets or duplicated URLs, repair or remove the malformed source entry.
2. If compilation mentions `edition2024`, check `cargo --version`; do not keep retrying with Cargo 1.75.
3. If `/root/.cargo/bin/rustup` is missing, use `command -v rustup` before deciding whether rustup is installed.
4. If `tpi` is installed but not found, load `$HOME/.cargo/env` or call the verified executable path.
5. If `turingpi.local` fails, use the BMC's reserved IPv4 address.
6. If an option is rejected, consult the help for the installed `tpi` version rather than older examples.

