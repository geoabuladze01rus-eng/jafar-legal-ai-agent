# JAFAR encrypted command relay

This directory contains only public relay material.

`jafar-command-public.pem` is intentionally public.

The corresponding private key must remain only on the owner's Mac:

`~/.jafar-command-bridge/private.pem`

Production editorial payloads must never be committed in plaintext.
Commands are hybrid-encrypted before entering the relay queue.
